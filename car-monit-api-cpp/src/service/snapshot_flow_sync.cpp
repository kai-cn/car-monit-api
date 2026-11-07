#include "service/snapshot_flow_sync.h"

#include "cache/redis.h"
#include "common/datetime.h"
#include "common/json.h"
#include "common/logging.h"
#include "config/config.h"
#include "db/dao.h"
#include "db/pg.h"
#include "meta/entities_generated.h"
#include "mq/kafka_producer.h"

#include <cctype>
#include <chrono>
#include <cstdio>
#include <ctime>
#include <optional>
#include <string>
#include <thread>
#include <vector>

// 一比一复刻 pro-business-api 的
// com.ruoyi.base.service.impl.SnapshotFlowSyncService（下文行号即该文件行号）：
//   * 33-40 行：batch-size 默认 1000、full-sync-enabled 默认 true、interval 默认 60000ms
//   * 47-56 行：固定 2 线程池；fullSync 受开关控制，incrementalSync 始终启动
//   * 63-111 行：fullSync 按 big_id 升序、gt(上次ID)、LIMIT batchSize、批间 sleep(100ms)
//   * 118-175 行：incrementalSync 按 snapshottime、gt(上次)/le(当前)、LIMIT batchSize，
//                 每轮 sleep(interval)，异常同样 sleep(interval) 后继续
namespace cm::service {
namespace {

// Java: 42-43 行 LAST_SYNC_TIME_KEY / LAST_SYNC_ID_KEY。
const char* kLastSyncIdKey = "snapshot_flow:last_sync_id";
const char* kLastSyncTimeKey = "snapshot_flow:last_sync_time";

// Java RedisTemplate 的 value 序列化器是 FastJson2JsonRedisSerializer(WriteClassName)，
// 实测：String -> "abc"，Date -> new Date(1234567890123)。
std::string encode_json_string(const std::string& s) { return Json(s).dump(); }

std::string encode_json_date(long long millis) {
  char buf[64];
  std::snprintf(buf, sizeof(buf), "new Date(%lld)", static_cast<long long>(millis));
  return std::string(buf);
}

std::string decode_json_string(const std::string& raw) {
  if (raw.size() >= 2 && raw.front() == '"' && raw.back() == '"') {
    try {
      return Json::parse(raw).get<std::string>();
    } catch (...) {
      return raw.substr(1, raw.size() - 2);
    }
  }
  return raw;
}

// 兼容 new Date(123) / 纯 millis / "yyyy-MM-dd HH:mm:ss" 三种历史值。
std::optional<long long> decode_json_date(const std::string& raw) {
  std::string s = raw;
  if (s.size() >= 10 && s.rfind("new Date(", 0) == 0 && s.back() == ')')
    s = s.substr(9, s.size() - 10);
  if (!s.empty() && (std::isdigit(static_cast<unsigned char>(s[0])) || s[0] == '-')) {
    try {
      return std::stoll(s);
    } catch (...) {
      return std::nullopt;
    }
  }
  if (auto tp = timeutil::parse_naive(decode_json_string(s)) )
    return timeutil::to_millis(*tp);
  return std::nullopt;
}

// pgjdbc 的 setTimestamp 用 JVM 默认时区（Asia/Shanghai）把 java.util.Date
// 转成 timestamp without time zone，保留毫秒。
std::string sql_timestamp_ms(long long millis) {
  const long long local_ms = millis + 480LL * 60 * 1000;
  std::time_t t = static_cast<std::time_t>(local_ms / 1000);
  std::tm tm{};
#ifdef _WIN32
  gmtime_s(&tm, &t);
#else
  gmtime_r(&t, &tm);
#endif
  const int frac = static_cast<int>(((millis % 1000) + 1000) % 1000);
  char buf[64];
  std::snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d.%03d", tm.tm_year + 1900,
                tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec, frac);
  return std::string(buf);
}

// fastjson2 对 java.util.Date / java.sql.Timestamp 的默认序列化（实测 fastjson2 2.0.43）：
//   nanos == 0 -> 数字（epoch millis）
//   nanos != 0 -> "yyyy-MM-dd HH:mm:ss.SSS"（JVM 默认时区 +08:00）
Json fastjson2_date(const std::string& db_text) {
  auto tp = timeutil::from_db_text(db_text);
  if (!tp) return Json(db_text);
  const long long millis = timeutil::to_millis(*tp);
  if (millis % 1000 == 0) return Json(millis);
  return Json(sql_timestamp_ms(millis));
}

// MyBatis-Plus selectList 选出的列：@TableField(exist=false) 的字段不参与查询。
std::string columns_of(const meta::EntityMeta& m) {
  std::string out;
  for (const auto& f : m.fields) {
    if (f.column.empty()) continue;
    if (!out.empty()) out += ",";
    out += f.column;
  }
  return out;
}

// 实体 -> Kafka 消息体里的 data：字段按声明顺序，null 字段不输出（fastjson2 默认行为）。
Json row_to_json(const meta::EntityMeta& m, const db::PgResult& r, std::size_t row) {
  Json j = Json::object();
  for (const auto& f : m.fields) {
    if (f.column.empty()) continue;
    auto raw = r.get(row, f.column);
    if (!raw || raw->empty()) continue;
    switch (f.type) {
      case meta::FType::Str:
        j[f.json] = *raw;
        break;
      case meta::FType::Int:
      case meta::FType::JavaLong:
        try {
          j[f.json] = std::stoll(*raw);
        } catch (...) {
          j[f.json] = *raw;
        }
        break;
      case meta::FType::Double:
      case meta::FType::Decimal:
        j[f.json] = json_raw_decimal(*raw);
        break;
      case meta::FType::Timestamp:
      case meta::FType::DateTime:
      case meta::FType::Day:
        j[f.json] = fastjson2_date(*raw);
        break;
      case meta::FType::Json:
        try {
          j[f.json] = Json::parse(*raw);
        } catch (...) {
          j[f.json] = *raw;
        }
        break;
    }
  }
  return j;
}

std::string big_id_of(const db::PgResult& r, std::size_t row) {
  auto v = r.get(row, "big_id");
  return v ? *v : std::string();
}

// Java: fullSync()（63-111 行）。
void full_sync(const meta::EntityMeta& m, int batch_size, const std::string& topic) {
  CM_LOG_INFO("sync") << "开始全量同步数据";
  try {
    auto& redis = cache::Redis::instance();
    std::string last_sync_id;
    if (auto v = redis.get(kLastSyncIdKey)) last_sync_id = decode_json_string(*v);

    const std::string cols = columns_of(m);
    while (true) {
      std::string sql = "SELECT " + cols + " FROM " + m.table;
      if (!last_sync_id.empty()) sql += " WHERE big_id > " + repo::quote(last_sync_id);
      sql += " ORDER BY big_id ASC LIMIT " + std::to_string(batch_size);

      db::PgResult result = db::PgPool::instance().query(sql);
      if (result.empty()) {
        CM_LOG_INFO("sync") << "全量同步完成";
        break;
      }

      for (std::size_t i = 0; i < result.size(); ++i) {
        const std::string id = big_id_of(result, i);
        mq::KafkaProducer::instance().send_snapshot_flow_data(row_to_json(m, result, i), id, topic);
        last_sync_id = id;
      }

      redis.set(kLastSyncIdKey, encode_json_string(last_sync_id));
      CM_LOG_INFO("sync") << "已同步 " << result.size() << " 条数据，当前进度: " << last_sync_id;

      // Java 106 行固定 sleep(100ms)。
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
  } catch (const std::exception& e) {
    // Java 108-110 行：异常只记录，不重试，线程退出。
    CM_LOG_ERROR("sync") << "全量同步异常: " << e.what();
  }
}

// Java: incrementalSync()（118-175 行）。
void incremental_sync(const meta::EntityMeta& m, int batch_size, long long interval_ms,
                      const std::string& topic) {
  CM_LOG_INFO("sync") << "开始增量同步数据";
  auto& redis = cache::Redis::instance();
  const std::string cols = columns_of(m);
  while (true) {
    try {
      std::optional<long long> last_sync_ms;
      if (auto v = redis.get(kLastSyncTimeKey)) last_sync_ms = decode_json_date(*v);
      const long long current_ms = timeutil::to_millis(timeutil::now());
      // Java 128-130 行：首次从 1 天前开始。
      if (!last_sync_ms) last_sync_ms = current_ms - 24LL * 3600 * 1000;

      std::string sql = "SELECT " + cols + " FROM " + m.table + " WHERE snapshottime > TIMESTAMP '" +
                        sql_timestamp_ms(*last_sync_ms) + "' AND snapshottime <= TIMESTAMP '" +
                        sql_timestamp_ms(current_ms) + "' ORDER BY snapshottime ASC LIMIT " +
                        std::to_string(batch_size);

      db::PgResult result = db::PgPool::instance().query(sql);
      if (!result.empty()) {
        for (std::size_t i = 0; i < result.size(); ++i) {
          mq::KafkaProducer::instance().send_snapshot_flow_data(row_to_json(m, result, i),
                                                               big_id_of(result, i), topic);
          // Java 153-155 行：游标取最后一条的 snapshottime。
          if (auto st = result.get(i, "snapshottime")) {
            if (auto tp = timeutil::from_db_text(*st)) last_sync_ms = timeutil::to_millis(*tp);
          }
        }
        redis.set(kLastSyncTimeKey, encode_json_date(*last_sync_ms));
        CM_LOG_INFO("sync") << "增量同步 " << result.size() << " 条数据，同步时间: "
                            << sql_timestamp_ms(*last_sync_ms);
      }

      // Java 164 行：每轮结束等待 interval。
      std::this_thread::sleep_for(std::chrono::milliseconds(interval_ms));
    } catch (const std::exception& e) {
      // Java 165-173 行：异常后同样等待 interval 再继续。
      CM_LOG_ERROR("sync") << "增量同步异常: " << e.what();
      std::this_thread::sleep_for(std::chrono::milliseconds(interval_ms));
    }
  }
}

} // namespace

void start_snapshot_flow_sync() {
  auto& cfg = config::Config::instance();
  const meta::EntityMeta& m = meta::odsRtSzdnSnapshotFlowAddcode;
  const int batch_size = cfg.sync.batch_size;
  const long long interval_ms = cfg.sync.incremental_sync_interval;
  const std::string topic = cfg.kafka.snapshot_flow_topic;

  if (cfg.sync.full_sync_enabled) {
    std::thread([m, batch_size, topic] { full_sync(m, batch_size, topic); }).detach();
  } else {
    CM_LOG_INFO("sync") << "全量同步已关闭（sync.full-sync-enabled=false）";
  }
  std::thread([m, batch_size, interval_ms, topic] {
    incremental_sync(m, batch_size, interval_ms, topic);
  }).detach();
  CM_LOG_INFO("sync") << "SnapshotFlowSyncService 已启动: batch-size=" << batch_size
                      << ", interval-ms=" << interval_ms
                      << ", full-sync=" << (cfg.sync.full_sync_enabled ? "true" : "false");
}

} // namespace cm::service
