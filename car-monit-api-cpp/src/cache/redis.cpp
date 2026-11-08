#include "cache/redis.h"

#include "common/error.h"
#include "common/json.h"
#include "common/logging.h"

#ifdef _WIN32
#include <winsock2.h>
#endif
#include <hiredis.h>
#include <hiredis_ssl.h>

#include <cstring>

namespace cm::cache {
namespace {

std::string reply_text(const redisReply* r) {
  if (r == nullptr) return {};
  switch (r->type) {
    case REDIS_REPLY_STRING:
    case REDIS_REPLY_STATUS:
    case REDIS_REPLY_ERROR:
      return std::string(r->str ? r->str : "", r->len);
    case REDIS_REPLY_INTEGER:
      return std::to_string(r->integer);
    case REDIS_REPLY_DOUBLE:
      return std::to_string(r->dval);
    case REDIS_REPLY_BOOL:
      return r->integer ? "1" : "0";
    case REDIS_REPLY_NIL:
      return {};
    default:
      return std::string(r->str ? r->str : "", r->len);
  }
}

Json reply_to_json(const redisReply* r) {
  if (r == nullptr || r->type == REDIS_REPLY_NIL) return Json(nullptr);
  if (r->type == REDIS_REPLY_ARRAY) {
    Json arr = Json::array();
    for (std::size_t i = 0; i < r->elements; ++i) arr.push_back(reply_to_json(r->element[i]));
    return arr;
  }
  return Json(reply_text(r));
}

} // namespace

Redis& Redis::instance() {
  static Redis r;
  return r;
}

Redis::~Redis() { close_unlocked(); }

void Redis::close_unlocked() {
  if (ctx_ != nullptr) {
    redisFree(ctx_);
    ctx_ = nullptr;
  }
  if (ssl_ctx_ != nullptr) {
    redisFreeSSLContext(ssl_ctx_);
    ssl_ctx_ = nullptr;
  }
  ready_ = false;
}

void Redis::close() {
  std::lock_guard<std::mutex> lock(mu_);
  close_unlocked();
}

bool Redis::connected() {
  std::lock_guard<std::mutex> lock(mu_);
  return ready_ && ctx_ != nullptr && ctx_->err == 0;
}

bool Redis::connect(const std::string& host, int port, const std::string& password, int database,
                    int timeout_ms, bool tls, const std::string& cacert, const std::string& cert,
                    const std::string& key) {
  std::lock_guard<std::mutex> lock(mu_);
  return connect_locked(host, port, password, database, timeout_ms, tls, cacert, cert, key);
}

bool Redis::connect_locked(const std::string& host, int port, const std::string& password,
                           int database, int timeout_ms, bool tls, const std::string& cacert,
                           const std::string& cert, const std::string& key) {
  close_unlocked();
  host_ = host;
  port_ = port;
  password_ = password;
  database_ = database;
  timeout_ms_ = timeout_ms > 0 ? timeout_ms : 3000;
  tls_ = tls;
  tls_cacert_ = cacert;
  tls_cert_ = cert;
  tls_key_ = key;

  timeval tv{};
  tv.tv_sec = timeout_ms_ / 1000;
  tv.tv_usec = (timeout_ms_ % 1000) * 1000;

  redisOptions options{};
  REDIS_OPTIONS_SET_TCP(&options, host.c_str(), port);
  options.connect_timeout = &tv;
  options.command_timeout = &tv;
  ctx_ = redisConnectWithOptions(&options);
  if (ctx_ == nullptr || ctx_->err != 0) {
    CM_LOG_WARN("cache.redis") << "连接失败 " << host << ":" << port
                               << " err=" << (ctx_ ? ctx_->errstr : "redisConnectWithOptions");
    close_unlocked();
    return false;
  }

  if (tls_) {
    static const bool ssl_inited = [] {
      redisInitOpenSSL();
      return true;
    }();
    (void)ssl_inited;
    redisSSLContextError ssl_error = REDIS_SSL_CTX_NONE;
    ssl_ctx_ = redisCreateSSLContext(cacert.empty() ? nullptr : cacert.c_str(), nullptr,
                                     cert.empty() ? nullptr : cert.c_str(),
                                     key.empty() ? nullptr : key.c_str(), host.c_str(), &ssl_error);
    if (ssl_ctx_ == nullptr) {
      CM_LOG_WARN("cache.redis") << "TLS 上下文创建失败: " << redisSSLContextGetError(ssl_error);
      close_unlocked();
      return false;
    }
    if (redisInitiateSSLWithContext(ctx_, ssl_ctx_) != REDIS_OK) {
      CM_LOG_WARN("cache.redis") << "TLS 握手失败: "
                                << (ctx_->errstr[0] ? ctx_->errstr : "unknown");
      close_unlocked();
      return false;
    }
  }

  auto check_reply = [&](redisReply* reply) -> bool {
    if (reply == nullptr) {
      CM_LOG_WARN("cache.redis") << "初始化命令失败: "
                                << (ctx_->errstr[0] ? ctx_->errstr : "unknown");
      return false;
    }
    const bool ok = reply->type != REDIS_REPLY_ERROR;
    if (!ok) CM_LOG_WARN("cache.redis") << "Redis 命令失败: " << reply_text(reply);
    freeReplyObject(reply);
    return ok;
  };
  if (!password_.empty() &&
      !check_reply(static_cast<redisReply*>(redisCommand(ctx_, "AUTH %s", password_.c_str())))) {
    close_unlocked();
    return false;
  }
  if (database_ > 0 &&
      !check_reply(static_cast<redisReply*>(redisCommand(ctx_, "SELECT %d", database_)))) {
    close_unlocked();
    return false;
  }
  ready_ = true;
  return true;
}

bool Redis::ensure() {
  // mu_ 已由调用方持有；connect_locked 也要求持锁，不会重复加锁/自锁。
  if (ready_ && ctx_ != nullptr && ctx_->err == 0) return true;
  if (host_.empty()) return false;
  return connect_locked(host_, port_, password_, database_, timeout_ms_, tls_, tls_cacert_,
                        tls_cert_, tls_key_);
}

std::optional<std::string> Redis::cmd(const std::vector<std::string>& args) {
  std::lock_guard<std::mutex> lock(mu_);
  return cmd_locked(args);
}

std::optional<std::string> Redis::cmd_locked(const std::vector<std::string>& args) {
  if (!ensure()) throw RedisError("Redis 未连接");
  std::vector<const char*> argv;
  std::vector<size_t> argvlen;
  argv.reserve(args.size());
  argvlen.reserve(args.size());
  for (const auto& a : args) {
    argv.push_back(a.c_str());
    argvlen.push_back(a.size());
  }
  redisReply* reply = static_cast<redisReply*>(
      redisCommandArgv(ctx_, static_cast<int>(argv.size()), argv.data(), argvlen.data()));
  if (reply == nullptr) {
    std::string err = ctx_ && ctx_->errstr[0] ? ctx_->errstr : "unknown";
    close_unlocked();
    throw RedisError("Redis 读取响应失败: " + err);
  }
  struct ReplyGuard {
    redisReply* r;
    ~ReplyGuard() { freeReplyObject(r); }
  } guard{reply};

  if (reply->type == REDIS_REPLY_ERROR) throw RedisError(reply_text(reply));
  if (reply->type == REDIS_REPLY_NIL) return std::nullopt;
  if (reply->type == REDIS_REPLY_ARRAY) return reply_to_json(reply).dump();
  return reply_text(reply);
}

std::optional<std::string> Redis::get(const std::string& key) {
  try {
    return cmd({"GET", key});
  } catch (const std::exception& e) {
    CM_LOG_WARN("cache.redis") << "GET " << key << " 失败: " << e.what();
    return std::nullopt;
  }
}

bool Redis::set(const std::string& key, const std::string& value) {
  try {
    return cmd({"SET", key, value}).has_value();
  } catch (const std::exception& e) {
    CM_LOG_WARN("cache.redis") << "SET " << key << " 失败: " << e.what();
    return false;
  }
}

bool Redis::setex(const std::string& key, const std::string& value, long long ttl_seconds) {
  try {
    if (ttl_seconds <= 0) return set(key, value);
    return cmd({"SETEX", key, std::to_string(ttl_seconds), value}).has_value();
  } catch (...) {
    return false;
  }
}

bool Redis::del(const std::string& key) {
  try {
    auto r = cmd({"DEL", key});
    return r && std::stoll(*r) > 0;
  } catch (...) {
    return false;
  }
}

bool Redis::exists(const std::string& key) {
  try {
    auto r = cmd({"EXISTS", key});
    return r && std::stoll(*r) > 0;
  } catch (...) {
    return false;
  }
}

long long Redis::ttl(const std::string& key) {
  try {
    auto r = cmd({"TTL", key});
    return r ? std::stoll(*r) : -2;
  } catch (...) {
    return -2;
  }
}

long long Redis::incr(const std::string& key) {
  try {
    auto r = cmd({"INCR", key});
    return r ? std::stoll(*r) : 0;
  } catch (...) {
    return 0;
  }
}

long long Redis::decr(const std::string& key) {
  try {
    auto r = cmd({"DECR", key});
    return r ? std::stoll(*r) : 0;
  } catch (...) {
    return 0;
  }
}

std::vector<std::string> Redis::keys(const std::string& pattern) {
  // KEYS 是 O(整个键空间) 的阻塞命令，改用 SCAN 增量遍历。
  // SCAN 可能对存活整个扫描期的键返回重复，调用方按需去重。
  std::vector<std::string> out;
  try {
    long long cursor = 0;
    do {
      auto r = cmd({"SCAN", std::to_string(cursor), "MATCH", pattern, "COUNT", "200"});
      if (!r) return out;
      auto j = Json::parse(*r); // [cursor, [key...]]
      if (!j.is_array() || j.size() < 2 || !j[1].is_array()) return out;
      cursor = std::stoll(j[0].get<std::string>());
      for (const auto& v : j[1]) out.push_back(v.get<std::string>());
    } while (cursor != 0);
  } catch (...) {
  }
  return out;
}

std::vector<std::string> Redis::lrange(const std::string& key, long long start, long long stop) {
  std::vector<std::string> out;
  try {
    auto r = cmd({"LRANGE", key, std::to_string(start), std::to_string(stop)});
    if (!r) return out;
    auto j = Json::parse(*r);
    for (const auto& v : j) out.push_back(v.get<std::string>());
  } catch (...) {
  }
  return out;
}

long long Redis::rpush(const std::string& key, const std::string& value) {
  try {
    auto r = cmd({"RPUSH", key, value});
    return r ? std::stoll(*r) : 0;
  } catch (...) {
    return 0;
  }
}

long long Redis::lrem(const std::string& key, long long count, const std::string& value) {
  try {
    auto r = cmd({"LREM", key, std::to_string(count), value});
    return r ? std::stoll(*r) : 0;
  } catch (...) {
    return 0;
  }
}

bool Redis::sadd(const std::string& key, const std::string& member) {
  try {
    return cmd({"SADD", key, member}).has_value();
  } catch (...) {
    return false;
  }
}

std::vector<std::string> Redis::smembers(const std::string& key) {
  std::vector<std::string> out;
  try {
    auto r = cmd({"SMEMBERS", key});
    if (!r) return out;
    auto j = Json::parse(*r);
    for (const auto& v : j) out.push_back(v.get<std::string>());
  } catch (...) {
  }
  return out;
}

std::optional<std::string> Redis::hget(const std::string& key, const std::string& field) {
  try {
    return cmd({"HGET", key, field});
  } catch (...) {
    return std::nullopt;
  }
}

bool Redis::hset(const std::string& key, const std::string& field, const std::string& value) {
  try {
    return cmd({"HSET", key, field, value}).has_value();
  } catch (...) {
    return false;
  }
}

bool Redis::expire(const std::string& key, long long seconds) {
  try {
    auto r = cmd({"EXPIRE", key, std::to_string(seconds)});
    return r && std::stoll(*r) > 0;
  } catch (...) {
    return false;
  }
}

bool Redis::flushdb() {
  try {
    return cmd({"FLUSHDB"}).has_value();
  } catch (...) {
    return false;
  }
}

bool Redis::set_json(const std::string& key, const std::string& json, long long ttl_seconds) {
  if (ttl_seconds > 0) return setex(key, json, ttl_seconds);
  return set(key, json);
}

} // namespace cm::cache
