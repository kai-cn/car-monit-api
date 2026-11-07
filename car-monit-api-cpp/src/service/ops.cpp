#include "service/ops.h"

#include "cache/redis.h"
#include "common/datetime.h"
#include "common/json.h"
#include "common/logging.h"
#include "common/utils.h"
#include "config/config.h"
#include "db/dao.h"
#include "db/pg.h"
#include "mq/kafka_producer.h"

#include <algorithm>
#include <set>
#include <vector>

namespace cm::service::ops {
namespace {

using cm::cache::Redis;

constexpr const char* kReportedMsgPrefix = "detection:reported:";
constexpr const char* kReportPrefix = "detection:report:";
constexpr const char* kDeviceCountPrefix = "detection:device:count:";

constexpr const char* kMsgStatusPrefix = "reliability:msg:status:";
constexpr const char* kMsgContentPrefix = "reliability:msg:content:";
constexpr const char* kTimeoutQueue = "reliability:timeout:queue";
constexpr const char* kDeviceHeartbeatPrefix = "reliability:device:heartbeat:";

constexpr const char* kDeviceDelayPrefix = "monitoring:delay:device:";
constexpr const char* kMessageDelayPrefix = "monitoring:delay:message:";
constexpr const char* kProcessDelayPrefix = "monitoring:delay:process:";
constexpr const char* kE2eDelayPrefix = "monitoring:delay:e2e:";

// DateUtils.formatDate(date) -> yyyyMMdd（JVM 默认时区 +08:00）
std::string format_date_compact(timeutil::TimePoint tp) {
  std::string s = timeutil::format_naive_plus8(tp); // yyyy-MM-dd HH:mm:ss
  std::string d = s.substr(0, 10);
  d.erase(std::remove(d.begin(), d.end(), '-'), d.end());
  return d;
}

// DateUtils.formatHour(date) -> yyyyMMddHH
std::string format_hour_compact(timeutil::TimePoint tp) {
  std::string s = timeutil::format_naive_plus8(tp);
  std::string d = s.substr(0, 10);
  d.erase(std::remove(d.begin(), d.end(), '-'), d.end());
  return d + s.substr(11, 2);
}

// 数据库 timestamp without time zone 使用 +08:00 墙钟文本。
std::string db_time(timeutil::TimePoint tp) { return timeutil::format_naive_plus8(tp); }

void send_alert(const std::string& type, const std::string& message) {
  // Java 的 sendAlert 只记录 error 日志（“TODO: 集成告警系统”），此处保持相同行为。
  CM_LOG_ERROR("alert") << "[" << type << "] " << message;
}

// KafkaTemplate.send(topic, key, payload) 的 C++ 等价入口。
// 默认走 librdkafka（真实 Kafka）；kafka.enabled=false 或 kafka.fallback-redis=true
// 时退回 Redis 列表 mq:pending:<topic>（降级路径，默认关闭）。
void mq_deliver(const std::string& topic, const std::string& payload) {
  auto& cfg = config::Config::instance();
  const std::string topic_name = topic.empty() ? cfg.kafka.snapshot_flow_topic : topic;
  mq::deliver(topic_name, payload);
}

// DataReliabilityService#retrySend：读取待发送内容并重新投递到 Kafka。
void retry_send(const std::string& message_id) {
  auto& redis = Redis::instance();
  auto content = redis.get(std::string(kMsgContentPrefix) + message_id);
  if (!content) {
    CM_LOG_ERROR("reliability") << "重发失败：消息内容已过期: messageId=" << message_id;
    return;
  }
  std::string topic;
  try {
    Json j = Json::parse(*content);
    topic = j.value("topic", "");
  } catch (...) {
  }
  redis.set(std::string(kMsgStatusPrefix) + message_id, "PENDING");
  mq_deliver(topic, *content);
  CM_LOG_INFO("reliability") << "重发消息: messageId=" << message_id;
}

// DataReliabilityService#resendMessage
void resend_message(const std::string& message_id) {
  auto& redis = Redis::instance();
  auto content = redis.get(std::string(kMsgContentPrefix) + message_id);
  if (!content) {
    CM_LOG_ERROR("reliability") << "重发失败：消息内容已过期: messageId=" << message_id;
    return;
  }
  redis.set(std::string(kMsgStatusPrefix) + message_id, "PENDING");
  std::string topic;
  try {
    Json j = Json::parse(*content);
    topic = j.value("topic", "");
  } catch (...) {
  }
  mq_deliver(topic, *content);
  CM_LOG_INFO("reliability") << "重发消息: messageId=" << message_id;
}

void accumulate(const std::string& prefix, std::vector<long long>& out) {
  auto& redis = Redis::instance();
  const std::string today = format_date_compact(timeutil::now());
  for (const auto& key : redis.keys(prefix + "*:" + today)) {
    for (const auto& v : redis.lrange(key, 0, -1)) {
      try {
        out.push_back(std::stoll(v));
      } catch (...) {
      }
    }
  }
}

long long avg_of(const std::vector<long long>& v) {
  if (v.empty()) return 0;
  long long sum = 0;
  for (auto x : v) sum += x;
  return sum / static_cast<long long>(v.size());
}
long long max_of(const std::vector<long long>& v) {
  return v.empty() ? 0 : *std::max_element(v.begin(), v.end());
}

} // namespace

void record_reported_message(const std::string& message_id, const std::string& device_id,
                             long long timestamp_ms) {
  auto& redis = Redis::instance();
  const std::string hour_key =
      std::string(kReportedMsgPrefix) + format_hour_compact(timeutil::from_millis(timestamp_ms));
  redis.sadd(hour_key, message_id);
  redis.expire(hour_key, 48 * 3600);
  if (!device_id.empty()) {
    const std::string count_key = std::string(kDeviceCountPrefix) + device_id + ":" +
                                  format_date_compact(timeutil::from_millis(timestamp_ms));
    redis.incr(count_key);
    redis.expire(count_key, 48 * 3600);
  }
}

void update_device_heartbeat(const std::string& device_id) {
  Redis::instance().setex(std::string(kDeviceHeartbeatPrefix) + device_id,
                          std::to_string(timeutil::to_millis(timeutil::now())), 300);
}

void data_loss_detection_tick() {
  auto& cfg = config::Config::instance();
  const int window_minutes = cfg.detection.window_size_minutes;
  const double threshold = cfg.detection.loss_threshold_percent;

  timeutil::TimePoint end = timeutil::now();
  timeutil::TimePoint start = timeutil::add_minutes(end, -window_minutes);

  CM_LOG_INFO("detection") << "开始检测，时间窗口: " << db_time(start) << " ~ " << db_time(end);

  // 1. 上报消息 ID（按小时分桶）
  std::set<std::string> reported;
  for (auto cur = start; cur <= end; cur = timeutil::add_hours(cur, 1)) {
    const std::string hour_key = std::string(kReportedMsgPrefix) + format_hour_compact(cur);
    for (const auto& id : Redis::instance().smembers(hour_key)) reported.insert(id);
  }

  // 2. 数据库同一窗口的记录（LambdaQueryWrapper between snapshottime）
  db::PgParams params;
  auto res = db::PgPool::instance().query(
      "SELECT big_id FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode WHERE snapshottime BETWEEN " +
          repo::bind_param(params, db_time(start)) + " AND " + repo::bind_param(params, db_time(end)),
      params);
  std::vector<std::string> stored_ids;
  for (std::size_t i = 0; i < res.rows.size(); ++i) {
    auto v = res.get(i, 0);
    if (v) stored_ids.push_back(*v);
  }

  std::set<std::string> stored(stored_ids.begin(), stored_ids.end());
  std::set<std::string> lost;
  for (const auto& id : reported)
    if (!stored.count(id)) lost.insert(id);

  std::set<std::string> duplicates;
  std::set<std::string> seen;
  for (const auto& id : stored_ids) {
    if (!seen.insert(id).second) duplicates.insert(id);
  }

  const double loss_rate =
      reported.empty() ? 0.0 : double(lost.size()) / double(reported.size()) * 100.0;

  CM_LOG_INFO("detection") << "检测完成: 上报=" << reported.size() << ", 存储=" << stored.size()
                           << ", 丢失=" << lost.size() << ", 重复=" << duplicates.size()
                           << ", 丢失率=" << loss_rate << "%";

  // 3. 报告（Redis，7 天）
  const std::string report_id = utils::uuid32().substr(0, 8);
  Json report = Json::object();
  report["reportId"] = report_id;
  // fastjson 默认把 Date 序列化为毫秒时间戳，这里保持同样的形式。
  report["startTime"] = timeutil::to_millis(start);
  report["endTime"] = timeutil::to_millis(end);
  report["reportedCount"] = static_cast<long long>(reported.size());
  report["storedCount"] = static_cast<long long>(stored.size());
  report["lostCount"] = static_cast<long long>(lost.size());
  report["duplicateCount"] = static_cast<long long>(duplicates.size());
  report["lossRate"] = loss_rate;
  report["generatedTime"] = timeutil::to_millis(timeutil::now());
  Redis::instance().set_json(std::string(kReportPrefix) + report_id, report.dump(), 7 * 24 * 3600);

  if (loss_rate > threshold) {
    send_alert("DATA_LOSS",
               "数据丢失率超过阈值！时间窗口: " + db_time(start) + " ~ " + db_time(end) +
                   ", 上报: " + std::to_string(reported.size()) + ", 存储: " +
                   std::to_string(stored.size()) + ", 丢失: " + std::to_string(lost.size()) +
                   ", 丢失率: " + std::to_string(loss_rate) + "%");
  }
}

void reliability_compensation_tick() {
  auto& redis = Redis::instance();
  auto ids = redis.lrange(kTimeoutQueue, 0, 50);
  if (ids.empty()) return;
  CM_LOG_INFO("reliability") << "补偿任务处理: " << ids.size() << " 条超时消息";
  for (const auto& id : ids) {
    redis.lrem(kTimeoutQueue, 1, id);
    auto status = redis.get(std::string(kMsgStatusPrefix) + id);
    if (status && *status == "PENDING") {
      retry_send(id);
    } else if (status && *status == "SENT") {
      resend_message(id);
    } else if (status && (*status == "CONFIRMED" || *status == "DEAD")) {
      // 无需处理
    } else {
      CM_LOG_WARN("reliability") << "未知状态: messageId=" << id
                                 << ", status=" << (status ? *status : "<null>");
    }
  }
}

void device_offline_check_tick() {
  auto& redis = Redis::instance();
  auto keys = redis.keys(std::string(kDeviceHeartbeatPrefix) + "*");
  if (keys.empty()) return;
  const long long now = timeutil::to_millis(timeutil::now());
  const long long offline_threshold = 5 * 60 * 1000;
  const std::string prefix = kDeviceHeartbeatPrefix;
  for (const auto& key : keys) {
    auto v = redis.get(key);
    if (!v) continue;
    long long heartbeat = 0;
    try {
      heartbeat = std::stoll(*v);
    } catch (...) {
      continue;
    }
    const std::string device_id = key.substr(prefix.size());
    if (now - heartbeat > offline_threshold) {
      CM_LOG_WARN("reliability") << "设备离线: deviceId=" << device_id
                                 << ", 上次心跳: " << (now - heartbeat) / 1000 << "s 前";
      send_alert("DEVICE_OFFLINE", "设备离线: " + device_id);
    }
  }
}

void delay_stats_report_tick() {
  std::vector<long long> device, message, process, e2e;
  accumulate(kDeviceDelayPrefix, device);
  accumulate(kMessageDelayPrefix, message);
  accumulate(kProcessDelayPrefix, process);
  accumulate(kE2eDelayPrefix, e2e);
  CM_LOG_INFO("monitoring") << "设备上报: avg=" << avg_of(device) << "ms, max=" << max_of(device)
                            << "ms | 消息传输: avg=" << avg_of(message)
                            << "ms, max=" << max_of(message) << "ms | 数据处理: avg="
                            << avg_of(process) << "ms, max=" << max_of(process)
                            << "ms | 端到端: avg=" << avg_of(e2e) << "ms, max=" << max_of(e2e)
                            << "ms";
}

void gauss_es_consistency_tick() {
  auto& cfg = config::Config::instance();
  if (!cfg.consistency.reconcile_enabled) {
    // Java 的定时方法在开关关闭时直接 return（默认 false）。
    return;
  }
  // 一致性对账依赖 ES/优化模块（GaussEsConsistencyService + LargeScaleDataSyncService），
  // 由 scheduler 直接调用 service::optimization::consistency_tick()。
}

} // namespace cm::service::ops
