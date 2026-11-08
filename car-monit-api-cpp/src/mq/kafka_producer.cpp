#include "mq/kafka_producer.h"

#include "cache/redis.h"
#include "common/crypto.h"
#include "common/datetime.h"
#include "common/logging.h"
#include "common/utils.h"
#include "config/config.h"
#include "db/dao.h"
#include "db/pg.h"
#include "service/ops.h"

#if defined(CM_WITH_KAFKA)
#if __has_include(<librdkafka/rdkafka.h>)
#include <librdkafka/rdkafka.h>
#elif __has_include(<rdkafka.h>)
#include <rdkafka.h>
#endif
#endif

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <map>
#include <mutex>
#include <thread>
#include <vector>

namespace cm::mq {
namespace {

using cache::Redis;

constexpr const char* kMsgStatusPrefix = "reliability:msg:status:";
constexpr const char* kMsgContentPrefix = "reliability:msg:content:";
// Java DataReliabilityService.TIMEOUT_QUEUE（同 service/ops.cpp 的超时队列键）。
constexpr const char* kTimeoutQueue = "reliability:timeout:queue";
// Spring Kafka JsonSerializer 默认写入的 value 类型头。
constexpr const char* kWrapTypeId =
    "com.ruoyi.base.service.impl.DataReliabilityService$ReliableMessageWrapper";
constexpr const char* kJsonObjectTypeId = "com.alibaba.fastjson2.JSONObject";

std::string now_db_time() { return timeutil::format_naive_plus8(timeutil::now()); }

// Java String.hashCode（UTF-16 code unit 加权求和，int 溢出回绕）。
int java_string_hash(const std::string& s) {
  uint32_t h = 0;
  std::size_t i = 0;
  while (i < s.size()) {
    unsigned char c = static_cast<unsigned char>(s[i]);
    uint32_t cu = 0;
    if (c < 0x80) {
      cu = c;
      ++i;
    } else if ((c & 0xE0) == 0xC0 && i + 1 < s.size()) {
      cu = (uint32_t(c & 0x1F) << 6) | (uint32_t(static_cast<unsigned char>(s[i + 1]) & 0x3F));
      i += 2;
    } else if ((c & 0xF0) == 0xE0 && i + 2 < s.size()) {
      cu = (uint32_t(c & 0x0F) << 12) |
           (uint32_t(static_cast<unsigned char>(s[i + 1]) & 0x3F) << 6) |
           uint32_t(static_cast<unsigned char>(s[i + 2]) & 0x3F);
      i += 3;
    } else if ((c & 0xF8) == 0xF0 && i + 3 < s.size()) {
      uint32_t cp = (uint32_t(c & 0x07) << 18) |
                    (uint32_t(static_cast<unsigned char>(s[i + 1]) & 0x3F) << 12) |
                    (uint32_t(static_cast<unsigned char>(s[i + 2]) & 0x3F) << 6) |
                    uint32_t(static_cast<unsigned char>(s[i + 3]) & 0x3F);
      cp -= 0x10000;
      h = 31u * h + (0xD800u | (cp >> 10));
      cu = 0xDC00u | (cp & 0x3FFu);
      i += 4;
    } else {
      cu = c;
      ++i;
    }
    h = 31u * h + cu;
  }
  return static_cast<int>(h);
}

std::string generate_message_id(const std::string& data_id) {
  static std::mutex mu;
  static std::uint64_t counter = 0;
  std::uint64_t nano = 0;
  {
    std::lock_guard<std::mutex> lock(mu);
    nano = ++counter;
  }
  long long now_ms = timeutil::to_millis(timeutil::now());
  std::string uuid8 = utils::uuid32().substr(0, 8);
  return std::to_string(now_ms) + "-" + std::to_string(nano % 1000000) + "-" + uuid8 + "-" +
         std::to_string(java_string_hash(data_id));
}

std::string data_id_from_payload(const std::string& payload) {
  try {
    Json j = Json::parse(payload);
    if (j.is_object()) {
      for (const char* key : {"dataId", "bigId", "id", "uuid"}) {
        auto it = j.find(key);
        if (it != j.end() && !it->is_null()) return json_string(*it, "");
      }
    }
  } catch (...) {
  }
  return "";
}

std::string message_id_from_payload(const std::string& payload) {
  try {
    Json j = Json::parse(payload);
    if (j.is_object()) {
      auto it = j.find("messageId");
      if (it != j.end() && !it->is_null()) return json_string(*it, "");
    }
  } catch (...) {
  }
  return "";
}

std::string extract_device_id(const Json& data) {
  if (!data.is_object()) return "unknown";
  for (const char* field : {"deviceId", "deviceid", "device_ip", "deviceIp", "gantrycode", "gantryId"}) {
    auto it = data.find(field);
    if (it != data.end() && !it->is_null()) return json_string(*it, "");
  }
  return "unknown";
}

// ---- kafka_message_record 落库（对应 KafkaMessageRecordMapper.xml）----

void db_update_status(const std::string& id, int status, bool with_send_time) {
  if (id.empty()) return;
  try {
    db::PgParams params;
    std::string sql = "UPDATE jl_data01.kafka_message_record SET status = " +
                      repo::bind_param(params, std::to_string(status));
    if (with_send_time) sql += ", send_time = " + repo::bind_param(params, now_db_time());
    sql += " WHERE id = " + repo::bind_param(params, id);
    db::PgPool::instance().execute(sql, params);
  } catch (const std::exception& e) {
    CM_LOG_WARN("kafka") << "更新 kafka_message_record 失败: id=" << id << ", error=" << e.what();
  }
}

void db_increment_retry(const std::string& id, const std::string& error) {
  if (id.empty()) return;
  try {
    db::PgParams params;
    db::PgPool::instance().execute(
        "UPDATE jl_data01.kafka_message_record SET retry_count = retry_count + 1, "
        "error_msg = " +
            repo::bind_param(params, error) + ", status = 2 WHERE id = " +
            repo::bind_param(params, id),
        params);
  } catch (const std::exception& e) {
    CM_LOG_WARN("kafka") << "累加 kafka_message_record 重试次数失败: id=" << id
                         << ", error=" << e.what();
  }
}

void db_insert_dead_letter(const std::string& data_id, const std::string& topic,
                           const std::string& message_json, int retry_count) {
  try {
    db::PgParams params;
    std::string sql =
        "INSERT INTO jl_data01.kafka_message_record "
        "(id, data_id, topic, message_json, status, retry_count, create_time) VALUES (" +
        repo::bind_param(params, utils::uuid32()) + ", " + repo::bind_param(params, data_id) +
        ", " + repo::bind_param(params, topic) + ", " + repo::bind_param(params, message_json) +
        ", 3, " + std::to_string(retry_count) + ", " + repo::bind_param(params, now_db_time()) +
        ")";
    db::PgPool::instance().execute(sql, params);
  } catch (const std::exception& e) {
    CM_LOG_ERROR("kafka") << "写入死信 kafka_message_record 失败: dataId=" << data_id
                          << ", error=" << e.what();
  }
}

} // namespace

// Java scheduleTimeoutCheck：sleep(messageTimeoutMs) 后读 Redis 状态，
// status != CONFIRMED（含键已过期/null）即超时。
bool reliability_timed_out(const std::optional<std::string>& status) {
  return !status || *status != "CONFIRMED";
}

struct KafkaProducer::Impl {
  struct DeliveryCtx {
    Impl* owner = nullptr;
    std::string topic;
    std::string key;
    std::string data_id;
    std::string message_id;
    std::string record_id;
    std::string payload;
    // 同步发送的等待状态
    bool sync = false;
    std::mutex mu;
    std::condition_variable cv;
    bool done = false;
    bool ok = false;
    bool abandoned = false;
    long long offset = -1;
    std::string error;
  };

#if defined(CM_WITH_KAFKA)
  rd_kafka_t* rk = nullptr;
#endif
  std::atomic<bool> running{false};
  std::atomic<bool> db_retry{false};
  std::mutex start_mu;
  std::thread poll_thread;
  std::thread db_thread;

  struct ScheduledRetry {
    std::chrono::steady_clock::time_point due;
    std::string topic;
    std::string key;
    std::string payload;
    int retry = 0;
  };
  std::mutex retry_mu;
  std::map<std::string, ScheduledRetry> retries;
  std::map<std::string, int> retry_counts;

  std::mutex err_mu;
  std::string last_error;

  // Java DataReliabilityService#scheduleTimeoutCheck / handleMessageTimeout：
  // 可靠消息发出后 reliability.message-timeout-ms 内未达 CONFIRMED，即把
  // messageId 推入 reliability:timeout:queue，由 ops::reliability_compensation_tick
  // 补偿（审阅报告 §3.3 R9：此前只写 PENDING、无人入队，补偿任务永远读到空列表）。
  struct TimeoutCheck {
    std::chrono::steady_clock::time_point due;
    std::string message_id;
  };
  std::mutex timeout_mu;
  std::map<std::string, TimeoutCheck> timeout_checks; // key = messageId
  std::mutex timeout_thread_mu;
  std::thread timeout_thread;
  std::atomic<bool> timeout_running{false};

  void schedule_timeout_check(const std::string& message_id);
  void process_due_timeouts();
  void ensure_timeout_thread();

  void set_error(const std::string& error) {
    std::lock_guard<std::mutex> lock(err_mu);
    last_error = error;
  }

  std::string get_error() {
    std::lock_guard<std::mutex> lock(err_mu);
    return last_error;
  }

  static void delivery_cb(rd_kafka_t*, const rd_kafka_message_t* msg, void* opaque);
  void on_delivery(DeliveryCtx* ctx, const rd_kafka_message_t* msg);
  void handle_send_failure(const DeliveryCtx& ctx, const std::string& error);
  void process_due_retries();

#if defined(CM_WITH_KAFKA)
  bool init_producer();
#endif
};

#if defined(CM_WITH_KAFKA)
namespace {

void set_conf(rd_kafka_conf_t* conf, const char* key, const std::string& value) {
  char errstr[256];
  if (rd_kafka_conf_set(conf, key, value.c_str(), errstr, sizeof(errstr)) != RD_KAFKA_CONF_OK) {
    CM_LOG_WARN("kafka") << "Kafka 配置项无效: " << key << "=" << value << " (" << errstr << ")";
  }
}

} // namespace

bool KafkaProducer::Impl::init_producer() {
  auto& cfg = config::Config::instance();
  rd_kafka_conf_t* conf = rd_kafka_conf_new();

  set_conf(conf, "bootstrap.servers", cfg.kafka.bootstrap_servers);
  set_conf(conf, "client.id", cfg.kafka.client_id);
  set_conf(conf, "acks", cfg.kafka.acks);
  set_conf(conf, "retries", std::to_string(cfg.kafka.retries));
  set_conf(conf, "enable.idempotence", cfg.kafka.enable_idempotence ? "true" : "false");
  set_conf(conf, "max.in.flight.requests.per.connection",
           std::to_string(cfg.kafka.max_in_flight));
  set_conf(conf, "batch.size", std::to_string(cfg.kafka.batch_size));
  set_conf(conf, "linger.ms", std::to_string(cfg.kafka.linger_ms));
  // Kafka 的 buffer.memory（字节）对应 librdkafka 的 queue.buffering.max.kbytes（KB）。
  set_conf(conf, "queue.buffering.max.kbytes", std::to_string(cfg.kafka.buffer_memory / 1024));
  set_conf(conf, "compression.type", cfg.kafka.compression_type);
  set_conf(conf, "delivery.timeout.ms", std::to_string(cfg.kafka.delivery_timeout_ms));
  set_conf(conf, "request.timeout.ms", std::to_string(cfg.kafka.request_timeout_ms));

  rd_kafka_conf_set_dr_msg_cb(conf, &KafkaProducer::Impl::delivery_cb);

  char errstr[512];
  rk = rd_kafka_new(RD_KAFKA_PRODUCER, conf, errstr, sizeof(errstr));
  if (!rk) {
    set_error(std::string("创建 Kafka 生产者失败: ") + errstr);
    CM_LOG_ERROR("kafka") << get_error();
    return false;
  }
  return true;
}
#endif

void KafkaProducer::Impl::delivery_cb(rd_kafka_t*, const rd_kafka_message_t* msg,
                                      void* opaque) {
  auto* ctx = static_cast<DeliveryCtx*>(opaque);
  if (!ctx || !ctx->owner) return;
  // C ABI 回调绝不能向外抛异常（librdkafka 内部线程无法捕获 C++ 异常，
  // 逃逸会直接 std::terminate）。on_delivery 内部已按同步/异步路径分别兜底，
  // 这里再加一层防线，只记录不重抛。
  try {
    ctx->owner->on_delivery(ctx, msg);
  } catch (const std::exception& e) {
    CM_LOG_ERROR("kafka") << "[Kafka生产者] delivery 回调异常: " << e.what();
  } catch (...) {
    CM_LOG_ERROR("kafka") << "[Kafka生产者] delivery 回调异常: <unknown>";
  }
}

void KafkaProducer::Impl::on_delivery(DeliveryCtx* ctx, const rd_kafka_message_t* msg) {
  bool ok = msg->err == 0;
  long long offset = ok ? static_cast<long long>(msg->offset) : -1;
  std::string error;
#if defined(CM_WITH_KAFKA)
  if (!ok) error = rd_kafka_message_errstr(msg);
#else
  if (!ok) error = "Kafka 未编译进来";
#endif

  if (ok) {
    CM_LOG_INFO("kafka") << "[Kafka生产者] 消息发送成功: dataId=" << ctx->data_id
                         << ", topic=" << ctx->topic << ", offset=" << offset;
  } else {
    CM_LOG_ERROR("kafka") << "[Kafka生产者] 消息发送失败: dataId=" << ctx->data_id
                          << ", topic=" << ctx->topic << ", error=" << error;
  }

  if (ctx->sync) {
    bool abandoned = false;
    {
      std::lock_guard<std::mutex> lock(ctx->mu);
      if (ctx->abandoned) {
        abandoned = true;
      } else {
        ctx->done = true;
        ctx->ok = ok;
        ctx->offset = offset;
        ctx->error = error;
      }
    }
    ctx->cv.notify_all();
    if (abandoned) delete ctx;  // 调用方已超时放弃
    return;
  }

  // 异步路径：回调里会写 Redis / DB / 死信，任何异常若逃出 C 回调都会终止进程；
  // 单独兜底并保证 ctx 一定释放（调用方不再持有异步 ctx）。
  try {
    if (ok) {
      if (!ctx->message_id.empty()) {
        Redis::instance().set(std::string(kMsgStatusPrefix) + ctx->message_id, "SENT");
        CM_LOG_DEBUG("kafka") << "[可靠性服务] Kafka确认消息: messageId=" << ctx->message_id
                              << ", offset=" << offset;
      }
      if (!ctx->record_id.empty()) {
        db_update_status(ctx->record_id, 1, true);
        // Java 侧此处传的是 dataId（而非 messageId），这里保持一致。
        Redis::instance().set(std::string(kMsgStatusPrefix) + ctx->data_id, "SENT");
      }
    } else {
      if (!ctx->record_id.empty()) db_increment_retry(ctx->record_id, error);
      if (!ctx->message_id.empty()) handle_send_failure(*ctx, error);
    }
  } catch (const std::exception& e) {
    CM_LOG_ERROR("kafka") << "[可靠性服务] 送达状态落库/告警异常: " << e.what();
  } catch (...) {
    CM_LOG_ERROR("kafka") << "[可靠性服务] 送达状态落库/告警异常: <unknown>";
  }
  delete ctx;
}

void KafkaProducer::Impl::handle_send_failure(const DeliveryCtx& ctx, const std::string& error) {
  auto& cfg = config::Config::instance();
  int retry = 0;
  {
    std::lock_guard<std::mutex> lock(retry_mu);
    retry = ++retry_counts[ctx.message_id];
  }
  CM_LOG_WARN("kafka") << "[可靠性服务] 消息发送失败: messageId=" << ctx.message_id
                       << ", retryCount=" << retry << ", error=" << error;

  if (retry < cfg.reliability.max_retry_count) {
    // Java：delay = 2^retryCount * 1000ms
    long long delay_ms = 1000LL << retry;
    std::lock_guard<std::mutex> lock(retry_mu);
    retries[ctx.message_id] = ScheduledRetry{
        std::chrono::steady_clock::now() + std::chrono::milliseconds(delay_ms), ctx.topic,
        ctx.key, ctx.payload, retry};
    return;
  }

  Redis::instance().set(std::string(kMsgStatusPrefix) + ctx.message_id, "DEAD");
  auto content = Redis::instance().get(std::string(kMsgContentPrefix) + ctx.message_id);
  db_insert_dead_letter(ctx.data_id, ctx.topic, content ? *content : ctx.payload, retry);
  CM_LOG_ERROR("kafka") << "[可靠性服务] 消息进入死信队列: messageId=" << ctx.message_id
                        << ", dataId=" << ctx.data_id << ", error=" << error;
  CM_LOG_ERROR("alert") << "[DEAD_LETTER] 消息进入死信队列: " << ctx.message_id
                        << ", 错误: " << error;
}

void KafkaProducer::Impl::process_due_retries() {
  std::vector<std::pair<std::string, ScheduledRetry>> due;
  {
    std::lock_guard<std::mutex> lock(retry_mu);
    auto now = std::chrono::steady_clock::now();
    for (auto it = retries.begin(); it != retries.end();) {
      if (it->second.due <= now) {
        due.emplace_back(it->first, it->second);
        it = retries.erase(it);
      } else {
        ++it;
      }
    }
  }
  for (auto& item : due) {
    CM_LOG_INFO("kafka") << "[可靠性服务] 重试消息: messageId=" << item.first
                         << ", retryCount=" << item.second.retry;
    KafkaProducer::instance().send(item.second.topic, item.second.key, item.second.payload,
                                   item.first, "", kWrapTypeId);
  }
}

// Java scheduleTimeoutCheck：记录到期时间，由超时线程统一检查
//（Java 是每消息提交一个 sleep 任务，这里等价改为扫描到期表）。
void KafkaProducer::Impl::schedule_timeout_check(const std::string& message_id) {
  auto& cfg = config::Config::instance();
  {
    std::lock_guard<std::mutex> lock(timeout_mu);
    timeout_checks[message_id] = TimeoutCheck{
        std::chrono::steady_clock::now() +
            std::chrono::milliseconds(cfg.reliability.message_timeout_ms),
        message_id};
  }
  ensure_timeout_thread();
}

// Java scheduleTimeoutCheck 的检查体 + handleMessageTimeout：
// 到期后读取 Redis 状态，非 CONFIRMED 即推入超时队列并发告警。
void KafkaProducer::Impl::process_due_timeouts() {
  std::vector<std::string> due;
  {
    std::lock_guard<std::mutex> lock(timeout_mu);
    auto now = std::chrono::steady_clock::now();
    for (auto it = timeout_checks.begin(); it != timeout_checks.end();) {
      if (it->second.due <= now) {
        due.push_back(std::move(it->second.message_id));
        it = timeout_checks.erase(it);
      } else {
        ++it;
      }
    }
  }
  for (const auto& id : due) {
    auto status = Redis::instance().get(std::string(kMsgStatusPrefix) + id);
    if (!reliability_timed_out(status)) continue;
    Redis::instance().rpush(kTimeoutQueue, id);
    CM_LOG_WARN("reliability") << "[可靠性服务] 消息超时: messageId=" << id
                               << ", 当前状态=" << (status ? *status : "<null>");
    CM_LOG_WARN("alert") << "[MESSAGE_TIMEOUT] 消息超时未确认: " << id
                         << ", 状态: " << (status ? *status : "<null>");
  }
}

// 超时检查线程独立于 Kafka 生产者生命周期（kafka.enabled=false 的 Redis 降级
// 模式下 sendReliableMessage 依然需要超时检测，与 Java retryExecutor 常驻一致）。
void KafkaProducer::Impl::ensure_timeout_thread() {
  std::lock_guard<std::mutex> lock(timeout_thread_mu);
  if (timeout_running.load()) return;
  timeout_running.store(true);
  timeout_thread = std::thread([this] {
    while (timeout_running.load()) {
      // 超时检查会读 Redis，异常逃出线程会 terminate 进程，这里兜底记录。
      try {
        process_due_timeouts();
      } catch (const std::exception& e) {
        CM_LOG_ERROR("kafka") << "[可靠性服务] 超时检查异常: " << e.what();
      } catch (...) {
        CM_LOG_ERROR("kafka") << "[可靠性服务] 超时检查异常: <unknown>";
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
  });
}

KafkaProducer::KafkaProducer() : impl_(std::make_unique<Impl>()) {}
KafkaProducer::~KafkaProducer() { stop(); }

KafkaProducer& KafkaProducer::instance() {
  static KafkaProducer producer;
  return producer;
}

bool KafkaProducer::start(bool start_db_retry) {
  auto& cfg = config::Config::instance();
  if (!cfg.kafka.enabled) {
    CM_LOG_INFO("kafka") << "Kafka 已关闭（kafka.enabled=false），使用 Redis 降级队列";
    return false;
  }
  std::lock_guard<std::mutex> lock(impl_->start_mu);
  if (impl_->running.load()) {
    if (start_db_retry) impl_->db_retry.store(true);
    return true;
  }
#if defined(CM_WITH_KAFKA)
  if (!impl_->rk && !impl_->init_producer()) return false;
  impl_->running.store(true);
  impl_->db_retry.store(start_db_retry && !cfg.kafka.fallback_redis);
  impl_->poll_thread = std::thread([this] {
    while (impl_->running.load()) {
      // 轮询线程同时负责重试扫描，异常若逃出会 terminate 进程，这里兜底记录。
      try {
#if defined(CM_WITH_KAFKA)
        rd_kafka_poll(impl_->rk, 100);
#else
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
#endif
        impl_->process_due_retries();
      } catch (const std::exception& e) {
        CM_LOG_ERROR("kafka") << "[Kafka生产者] 轮询/重试线程异常: " << e.what();
      } catch (...) {
        CM_LOG_ERROR("kafka") << "[Kafka生产者] 轮询/重试线程异常: <unknown>";
      }
    }
  });
  if (impl_->db_retry.load()) {
    impl_->db_thread = std::thread([this] {
      auto& cfg = config::Config::instance();
      while (impl_->running.load()) {
        bool failed = false;
        try {
          // KafkaProducerService#startRetryTask：status IN (0,2) 且 retry_count < max
          auto res = db::PgPool::instance().query(
              "SELECT id, data_id, topic, message_json, retry_count "
              "FROM jl_data01.kafka_message_record "
              "WHERE status IN (0, 2) AND retry_count < " +
              std::to_string(cfg.kafka.max_retry_count) +
              " ORDER BY create_time ASC LIMIT 100");
          if (!res.empty()) CM_LOG_INFO("kafka") << "[Kafka生产者] 开始重试 " << res.size()
                                                 << " 条消息";
          for (std::size_t i = 0; i < res.size(); ++i) {
            auto id = res.get(i, "id");
            auto data_id = res.get(i, "data_id");
            auto topic = res.get(i, "topic");
            auto message_json = res.get(i, "message_json");
            if (!id || !topic || !message_json) continue;
            send(*topic, data_id ? *data_id : "", *message_json, "", *id, kJsonObjectTypeId);
          }
        } catch (const std::exception& e) {
          failed = true;
          CM_LOG_ERROR("kafka") << "[Kafka生产者] 重试任务异常: " << e.what();
        }
        // 正常 30s；异常时 Java 侧休眠 60s 后继续
        int sleep_ms = failed ? cfg.kafka.retry_error_interval_ms : cfg.kafka.retry_interval_ms;
        for (int waited = 0; waited < sleep_ms && impl_->running.load(); waited += 100)
          std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
    });
  }
  CM_LOG_INFO("kafka") << "Kafka 生产者启动: bootstrap=" << cfg.kafka.bootstrap_servers
                       << ", client.id=" << cfg.kafka.client_id;
  return true;
#else
  impl_->set_error("构建时未启用 CM_WITH_KAFKA");
  CM_LOG_WARN("kafka") << "Kafka 未编译进来（CM_WITH_KAFKA=OFF），使用 Redis 降级队列";
  return false;
#endif
}

void KafkaProducer::stop() {
  std::lock_guard<std::mutex> lock(impl_->start_mu);
  // 超时检测线程与 Kafka 生产者生命周期解耦（降级模式也会启动），两条路径都要回收。
  {
    std::lock_guard<std::mutex> tlock(impl_->timeout_thread_mu);
    impl_->timeout_running.store(false);
  }
  if (impl_->timeout_thread.joinable()) impl_->timeout_thread.join();
  if (!impl_->running.exchange(false)) {
#if defined(CM_WITH_KAFKA)
    if (impl_->rk) {
      rd_kafka_destroy(impl_->rk);
      impl_->rk = nullptr;
    }
#endif
    return;
  }
  if (impl_->poll_thread.joinable()) impl_->poll_thread.join();
  if (impl_->db_thread.joinable()) impl_->db_thread.join();
#if defined(CM_WITH_KAFKA)
  if (impl_->rk) {
    rd_kafka_flush(impl_->rk, 5000);
    rd_kafka_destroy(impl_->rk);
    impl_->rk = nullptr;
  }
#endif
  CM_LOG_INFO("kafka") << "Kafka 生产者已停止";
}

bool KafkaProducer::started() const { return impl_->running.load(); }

bool KafkaProducer::send(const std::string& topic, const std::string& key,
                         const std::string& payload, const std::string& message_id,
                         const std::string& record_id, const std::string& type_id) {
#if defined(CM_WITH_KAFKA)
  if (!impl_->rk) {
    if (!started() && !start(false)) return false;
    if (!impl_->rk) return false;
  }
  std::string actual_key = key.empty() ? data_id_from_payload(payload) : key;
  auto* ctx = new Impl::DeliveryCtx;
  ctx->owner = impl_.get();
  ctx->topic = topic;
  ctx->key = actual_key;
  ctx->data_id = actual_key;
  ctx->message_id = message_id;
  ctx->record_id = record_id;
  ctx->payload = payload;

  rd_kafka_headers_t* headers = nullptr;
  if (!type_id.empty()) {
    headers = rd_kafka_headers_new(1);
    rd_kafka_header_add(headers, "__TypeId__", -1, type_id.c_str(), -1);
  }
  // RD_KAFKA_V_VALUE 的类型检查要求 void*；MSG_F_COPY 只做只读拷贝，const_cast 安全。
#if defined(RD_KAFKA_V_HEADERS)
  rd_kafka_resp_err_t err = rd_kafka_producev(
      impl_->rk, RD_KAFKA_V_TOPIC(topic.c_str()),
      RD_KAFKA_V_KEY(actual_key.data(), actual_key.size()),
      RD_KAFKA_V_VALUE(const_cast<char*>(payload.data()), payload.size()),
      RD_KAFKA_V_MSGFLAGS(RD_KAFKA_MSG_F_COPY),
      RD_KAFKA_V_OPAQUE(ctx), RD_KAFKA_V_HEADERS(headers), RD_KAFKA_V_END);
#else
  rd_kafka_resp_err_t err =
      rd_kafka_producev(impl_->rk, RD_KAFKA_V_TOPIC(topic.c_str()),
                        RD_KAFKA_V_KEY(actual_key.data(), actual_key.size()),
                        RD_KAFKA_V_VALUE(const_cast<char*>(payload.data()), payload.size()),
                        RD_KAFKA_V_MSGFLAGS(RD_KAFKA_MSG_F_COPY), RD_KAFKA_V_OPAQUE(ctx),
                        RD_KAFKA_V_END);
#endif
  if (err != RD_KAFKA_RESP_ERR_NO_ERROR) {
    if (headers) rd_kafka_headers_destroy(headers);
    delete ctx;
    impl_->set_error(rd_kafka_err2str(err));
    CM_LOG_ERROR("kafka") << "[Kafka生产者] 消息入队失败: dataId=" << actual_key
                          << ", error=" << rd_kafka_err2str(err);
    return false;
  }
  return true;
#else
    (void)topic;
    (void)key;
    (void)payload;
    (void)message_id;
    (void)record_id;
    (void)type_id;
    return false;
#endif
}

bool KafkaProducer::send_sync(const std::string& topic, const std::string& key,
                              const std::string& payload, int timeout_ms, std::string* error,
                              long long* offset) {
#if defined(CM_WITH_KAFKA)
  if (!started()) start(false);
  if (!impl_->rk) {
    if (error) *error = impl_->get_error();
    return false;
  }
  auto* ctx = new Impl::DeliveryCtx;
  ctx->owner = impl_.get();
  ctx->sync = true;
  ctx->topic = topic;
  ctx->key = key;
  ctx->data_id = key;
  ctx->payload = payload;

  std::unique_ptr<Impl::DeliveryCtx> guard(ctx);
  rd_kafka_resp_err_t err = rd_kafka_producev(
      impl_->rk, RD_KAFKA_V_TOPIC(topic.c_str()),
      RD_KAFKA_V_KEY(key.data(), key.size()),
      RD_KAFKA_V_VALUE(const_cast<char*>(payload.data()), payload.size()),
      RD_KAFKA_V_MSGFLAGS(RD_KAFKA_MSG_F_COPY), RD_KAFKA_V_OPAQUE(ctx), RD_KAFKA_V_END);
  if (err != RD_KAFKA_RESP_ERR_NO_ERROR) {
    if (error) *error = rd_kafka_err2str(err);
    return false;
  }

  std::unique_lock<std::mutex> lock(ctx->mu);
  bool done = ctx->cv.wait_for(lock, std::chrono::milliseconds(timeout_ms),
                               [&] { return ctx->done; });
  if (!done) {
    // 生产消息已入队，delivery 回调可能稍后到达；标记放弃，由回调负责释放。
    ctx->abandoned = true;
    lock.unlock();
    guard.release();
    if (error) *error = "等待 Kafka delivery 回调超时（" + std::to_string(timeout_ms) + "ms）";
    return false;
  }
  if (error) *error = ctx->error;
  if (offset) *offset = ctx->offset;
  return ctx->ok;
#else
  (void)topic;
  (void)key;
  (void)payload;
  (void)timeout_ms;
  if (error) *error = "构建时未启用 CM_WITH_KAFKA";
  (void)offset;
  return false;
#endif
}

std::string KafkaProducer::send_reliable_message(const Json& data, const std::string& data_id,
                                                 const std::string& topic) {
  auto& cfg = config::Config::instance();
  std::string actual_topic = topic.empty() ? cfg.kafka.snapshot_flow_topic : topic;
  std::string message_id = generate_message_id(data_id);
  std::string checksum = crypto::md5_hex(json_dump(data));

  Json wrapper = Json::object();
  wrapper["messageId"] = message_id;
  wrapper["dataId"] = data_id;
  wrapper["checksum"] = checksum;
  wrapper["operationType"] = "INSERT";
  wrapper["data"] = data;
  wrapper["timestamp"] = timeutil::to_millis(timeutil::now());
  wrapper["version"] = 1;
  std::string message_json = json_dump(wrapper);

  auto& redis = Redis::instance();
  redis.setex(std::string(kMsgContentPrefix) + message_id, message_json, 24 * 3600);
  redis.setex(std::string(kMsgStatusPrefix) + message_id, "PENDING", 24 * 3600);
  CM_LOG_INFO("reliability") << "[可靠性服务] 发送可靠消息: messageId=" << message_id
                             << ", dataId=" << data_id << ", topic=" << actual_topic;

  deliver(actual_topic, message_json);
  // Java sendReliableMessage 第 8 步：scheduleTimeoutCheck(messageId)。
  impl_->schedule_timeout_check(message_id);
  return message_id;
}

std::string KafkaProducer::send_snapshot_flow_data(const Json& data, const std::string& data_id,
                                                   const std::string& topic) {
  std::string message_id = send_reliable_message(data, data_id, topic);
  service::ops::record_reported_message(message_id, extract_device_id(data),
                                        timeutil::to_millis(timeutil::now()));
  CM_LOG_INFO("kafka") << "[Kafka生产者] 发送消息: dataId=" << data_id
                       << ", messageId=" << message_id;
  return message_id;
}

std::string KafkaProducer::last_error() const { return impl_->get_error(); }

bool deliver(const std::string& topic, const std::string& payload) {
  auto& cfg = config::Config::instance();
  std::string actual_topic = topic.empty() ? cfg.kafka.snapshot_flow_topic : topic;
  if (!cfg.kafka.enabled || cfg.kafka.fallback_redis) {
    auto& redis = Redis::instance();
    const std::string key = "mq:pending:" + actual_topic;
    redis.rpush(key, payload);
    CM_LOG_INFO("mq") << "Kafka 降级(Redis 队列): topic=" << actual_topic
                      << ", bytes=" << payload.size();
    return true;
  }
  std::string message_id = message_id_from_payload(payload);
  std::string data_id = data_id_from_payload(payload);
  auto& producer = KafkaProducer::instance();
  if (!producer.started() && !producer.start()) {
    CM_LOG_ERROR("mq") << "Kafka 未启动且无法创建生产者: " << producer.last_error();
    return false;
  }
  bool ok = producer.send(actual_topic, data_id, payload, message_id, "", kWrapTypeId);
  if (!ok) CM_LOG_ERROR("mq") << "Kafka 消息入队失败: topic=" << actual_topic;
  return ok;
}

} // namespace cm::mq
