#pragma once
// Redis 客户端（RESP2）。
//
// Java 侧：Spring Data Redis (Lettuce) + RuoYi RedisCache/RedisUtil，
// 序列化器为 FastJson2JsonRedisSerializer（字符串存 JSON）。C++ 侧保持
// 同样的键名与 JSON 值，不做额外前缀，保证与 Java 版本互通。
#include <mutex>
#include <optional>
#include <string>
#include <vector>

namespace cm::cache {

class Redis {
public:
  static Redis& instance();

  bool connect(const std::string& host, int port, const std::string& password, int database,
               int timeout_ms);
  bool connected();
  void close();

  // 原始命令：返回第一条回复（数组以 JSON 数组形式返回）。
  std::optional<std::string> cmd(const std::vector<std::string>& args);

  // RedisCache 语义
  std::optional<std::string> get(const std::string& key);
  bool set(const std::string& key, const std::string& value);
  bool setex(const std::string& key, const std::string& value, long long ttl_seconds);
  bool del(const std::string& key);
  bool exists(const std::string& key);
  long long ttl(const std::string& key);
  long long incr(const std::string& key);
  long long decr(const std::string& key);
  std::vector<std::string> keys(const std::string& pattern);
  std::vector<std::string> lrange(const std::string& key, long long start, long long stop);
  long long rpush(const std::string& key, const std::string& value);
  // LREM key count value
  long long lrem(const std::string& key, long long count, const std::string& value);
  // SET / SMEMBERS
  bool sadd(const std::string& key, const std::string& member);
  std::vector<std::string> smembers(const std::string& key);
  std::optional<std::string> hget(const std::string& key, const std::string& field);
  bool hset(const std::string& key, const std::string& field, const std::string& value);
  bool expire(const std::string& key, long long seconds);
  bool flushdb();

  // JSON 对象缓存（对应 RedisCache.setCacheObject/getCacheObject）
  bool set_json(const std::string& key, const std::string& json, long long ttl_seconds = 0);

private:
  Redis() = default;
  bool ensure();
  bool send_command(const std::vector<std::string>& args);
  bool read_reply(std::string& out, char& type);
  bool read_line(std::string& out);
  void close_unlocked();

  std::mutex mu_;
  intptr_t sock_ = -1;
  std::string host_;
  int port_ = 6379;
  std::string password_;
  int database_ = 0;
  int timeout_ms_ = 3000;
  bool ready_ = false;
};

} // namespace cm::cache
