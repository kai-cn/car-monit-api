#pragma once
// Kafka 生产者（librdkafka C API），对应 Java 的 KafkaProducerConfig +
// KafkaProducerService + DataReliabilityService#sendReliableMessage。
//
// 线协议对齐要点：
//   * key   = dataId（StringSerializer，UTF-8 原文）
//   * value = JSON（Spring Kafka JsonSerializer；ReliableMessageWrapper 字段顺序
//             messageId/dataId/checksum/operationType/data/timestamp/version）
//   * 额外消息头 __TypeId__，与 Spring Kafka JsonSerializer 默认行为一致
//   * 异步发送 + delivery 回调；失败指数退避重试，超过次数进入死信
#include "common/json.h"

#include <memory>
#include <optional>
#include <string>

namespace cm::mq {

// Java DataReliabilityService.scheduleTimeoutCheck 的超时判定（纯逻辑，可单测）：
// 消息发出 reliability.message-timeout-ms 后读取 Redis 状态，
// 缺失（键过期）或非 CONFIRMED 均视为超时，需推入 reliability:timeout:queue
// 供补偿任务处理；仅 CONFIRMED 不超时。
bool reliability_timed_out(const std::optional<std::string>& status);


class KafkaProducer {
public:
  static KafkaProducer& instance();

  // 创建生产者并启动 poll/DB 重试线程；broker 不可达不会导致启动失败。
  // start_db_retry=false 时只启动 poll 线程（测试/诊断用）。
  bool start(bool start_db_retry = true);
  void stop();
  bool started() const;

  // KafkaTemplate.send(topic, key, value)：异步发送，key 为空时取 JSON 的 dataId。
  // message_id 用于可靠性状态回写；record_id 对应 kafka_message_record.id。
  bool send(const std::string& topic, const std::string& key, const std::string& payload,
            const std::string& message_id = "", const std::string& record_id = "",
            const std::string& type_id = "");

  // 同步发送，仅用于诊断/无 broker 失败路径测试。
  bool send_sync(const std::string& topic, const std::string& key, const std::string& payload,
                 int timeout_ms, std::string* error, long long* offset);

  // DataReliabilityService#sendReliableMessage：包装 + Redis 状态 + Kafka 投递。
  std::string send_reliable_message(const Json& data, const std::string& data_id,
                                    const std::string& topic);

  // KafkaProducerService#sendSnapshotFlowData：可靠性投递 + 丢失检测上报。
  std::string send_snapshot_flow_data(const Json& data, const std::string& data_id,
                                      const std::string& topic = "");

  std::string last_error() const;

private:
  KafkaProducer();
  ~KafkaProducer();
  KafkaProducer(const KafkaProducer&) = delete;
  KafkaProducer& operator=(const KafkaProducer&) = delete;

  struct Impl;
  std::unique_ptr<Impl> impl_;
};

// KafkaTemplate.send(topic, key, payload) 的降级入口：
// 默认走真实 Kafka；kafka.enabled=false 或 kafka.fallback-redis=true 时写入
// Redis 队列 mq:pending:<topic>，由原有补偿逻辑消费。
bool deliver(const std::string& topic, const std::string& payload);

} // namespace cm::mq
