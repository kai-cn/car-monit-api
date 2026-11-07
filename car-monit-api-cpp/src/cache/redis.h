#pragma once
// Redis 客户端（hiredis 1.5）。
//
// Java 侧：Spring Data Redis (Lettuce) + RuoYi RedisCache/RedisUtil，
// 序列化器为 FastJson2JsonRedisSerializer（字符串存 JSON）。C++ 侧保持
// 同样的键名与 JSON 值，不做额外前缀，保证与 Java 版本互通。
//
// 历史：迁移初期自行实现 RESP2（含半包读、SCAN、重连 fd 泄漏等修复）。
// 本轮（P3）改为 hiredis：连接/命令超时由库处理，TLS 由 hiredis_ssl 提供；
// 对外仍保持 Redis 类的命令接口。
struct redisContext;
struct redisSSLContext;

#include <mutex>
#include <optional>
#include <string>
#include <vector>

namespace cm::cache {

class Redis {
public:
  static Redis& instance();

  // tls=true 时使用 hiredis_ssl（OpenSSL）。cacert 为空则使用系统默认 CA；
  // cert/key 需成对提供（客户端证书认证）。
  bool connect(const std::string& host, int port, const std::string& password, int database,
               int timeout_ms, bool tls = false, const std::string& cacert = "",
               const std::string& cert = "", const std::string& key = "");
  bool connected();
  void close();

  // 原始命令：返回第一条回复（数组以 JSON 数组形式返回；nil 返回 nullopt）。
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
  ~Redis();
  Redis(const Redis&) = delete;
  Redis& operator=(const Redis&) = delete;

  // 以下两个函数要求调用方已持有 mu_（避免在持锁路径再次加锁造成自锁）。
  bool ensure();
  bool connect_locked(const std::string& host, int port, const std::string& password, int database,
                      int timeout_ms, bool tls, const std::string& cacert, const std::string& cert,
                      const std::string& key);
  void close_unlocked();
  std::optional<std::string> cmd_locked(const std::vector<std::string>& args);

  std::mutex mu_;
  ::redisContext* ctx_ = nullptr;
  ::redisSSLContext* ssl_ctx_ = nullptr;
  std::string host_;
  std::string password_;
  std::string tls_cacert_;
  std::string tls_cert_;
  std::string tls_key_;
  int port_ = 6379;
  int database_ = 0;
  int timeout_ms_ = 3000;
  bool tls_ = false;
  bool ready_ = false;
};

} // namespace cm::cache
