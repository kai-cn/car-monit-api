#include "cache/redis.h"

#include "common/error.h"
#include "common/json.h"
#include "common/logging.h"

#include <algorithm>
#include <chrono>
#include <cstring>
#include <thread>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#endif

namespace cm::cache {
namespace {

#ifdef _WIN32
using sock_t = SOCKET;
constexpr intptr_t kInvalid = -1; // INVALID_SOCKET
void ensure_wsa() {
  static bool done = false;
  static std::mutex m;
  std::lock_guard<std::mutex> lock(m);
  if (!done) {
    WSADATA data;
    WSAStartup(MAKEWORD(2, 2), &data);
    done = true;
  }
}
#else
using sock_t = int;
constexpr intptr_t kInvalid = -1;
void ensure_wsa() {}
#endif

} // namespace

Redis& Redis::instance() {
  static Redis r;
  return r;
}

void Redis::close_unlocked() {
  if (sock_ != kInvalid) {
#ifdef _WIN32
    closesocket(sock_t(sock_));
#else
    ::close(int(sock_));
#endif
    sock_ = -1;
  }
  ready_ = false;
}

void Redis::close() {
  std::lock_guard<std::mutex> lock(mu_);
  close_unlocked();
}

bool Redis::connected() {
  std::lock_guard<std::mutex> lock(mu_);
  return ready_ && sock_ != kInvalid;
}

bool Redis::connect(const std::string& host, int port, const std::string& password,
                    int database, int timeout_ms) {
  std::lock_guard<std::mutex> lock(mu_);
  ensure_wsa();
  close_unlocked();
  host_ = host;
  port_ = port;
  password_ = password;
  database_ = database;
  timeout_ms_ = timeout_ms;

  sock_t s = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (static_cast<intptr_t>(s) == kInvalid) return false;
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(uint16_t(port));
  inet_pton(AF_INET, host.c_str(), &addr.sin_addr);
#ifdef _WIN32
  int timeout = timeout_ms;
  setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
  setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
#else
  // POSIX 同样设置收发超时（timeval 语义），避免 Linux 上 recv 无限阻塞。
  timeval tv{};
  tv.tv_sec = timeout_ms / 1000;
  tv.tv_usec = (timeout_ms % 1000) * 1000;
  setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
  setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#endif
  if (::connect(s, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
#ifdef _WIN32
    int err = WSAGetLastError();
#else
    int err = errno;
#endif
    CM_LOG_WARN("cache.redis") << "连接失败 " << host << ":" << port << " err=" << err;
#ifdef _WIN32
    closesocket(s);
#else
    ::close(s);
#endif
    return false;
  }
  sock_ = intptr_t(s);

  auto auth = [&](std::vector<std::string> args) -> bool {
    if (!send_command(args)) return false;
    std::string out;
    char type = 0;
    if (!read_reply(out, type)) return false;
    if (type == '-') {
      CM_LOG_WARN("cache.redis") << "Redis 命令失败: " << out;
      return false;
    }
    return true;
  };
  if (!password_.empty()) {
    if (!auth({"AUTH", password_})) {
      close_unlocked();
      return false;
    }
  }
  if (database_ > 0) {
    if (!auth({"SELECT", std::to_string(database_)})) {
      close_unlocked();
      return false;
    }
  }
  ready_ = true;
  return true;
}

bool Redis::ensure() {
  if (ready_ && sock_ != kInvalid) return true;
  if (host_.empty()) return false;
  intptr_t old = sock_;
  sock_ = -1;
  ready_ = false;
  (void)old;
  return connect(host_, port_, password_, database_, timeout_ms_);
}

bool Redis::send_command(const std::vector<std::string>& args) {
  std::string out;
  out.reserve(64);
  out += "*" + std::to_string(args.size()) + "\r\n";
  for (const auto& a : args) {
    out += "$" + std::to_string(a.size()) + "\r\n";
    out += a;
    out += "\r\n";
  }
#ifdef _WIN32
  int sent = ::send(sock_t(sock_), out.data(), int(out.size()), 0);
  return sent == int(out.size());
#else
  ssize_t sent = ::send(int(sock_), out.data(), out.size(), 0);
  return sent == ssize_t(out.size());
#endif
}

bool Redis::read_line(std::string& out) {
  out.clear();
  char c;
  while (true) {
#ifdef _WIN32
    int got = ::recv(sock_t(sock_), &c, 1, 0);
#else
    ssize_t got = ::recv(int(sock_), &c, 1, 0);
#endif
    if (got <= 0) return false;
    if (c == '\r') continue;
    if (c == '\n') return true;
    out.push_back(c);
  }
}

bool Redis::read_reply(std::string& out, char& type) {
  if (!read_line(out)) return false;
  if (out.empty()) return false;
  type = out[0];
  std::string payload = out.substr(1);
  switch (type) {
    case '+':
    case '-':
      out = payload;
      return true;
    case ':':
      out = payload;
      return true;
    case '$': {
      int len = std::atoi(payload.c_str());
      if (len < 0) {
        out.clear();
        return true;
      }
      out.assign(std::size_t(len), '\0');
#ifdef _WIN32
      int got = ::recv(sock_t(sock_), out.data(), len, 0);
      if (got != len) return false;
#else
      std::size_t left = std::size_t(len);
      char* p = out.data();
      while (left > 0) {
        ssize_t got = ::recv(int(sock_), p, left, 0);
        if (got <= 0) return false;
        p += got;
        left -= std::size_t(got);
      }
#endif
      std::string crlf;
      read_line(crlf);
      return true;
    }
    case '*': {
      int n = std::atoi(payload.c_str());
      Json arr = Json::array();
      for (int i = 0; i < n; ++i) {
        std::string item;
        char t2 = 0;
        if (!read_reply(item, t2)) return false;
        arr.push_back(item);
      }
      out = arr.dump();
      return true;
    }
    default:
      return false;
  }
}

std::optional<std::string> Redis::cmd(const std::vector<std::string>& args) {
  std::lock_guard<std::mutex> lock(mu_);
  if (!ensure()) throw RedisError("Redis 未连接");
  if (!send_command(args)) {
    ready_ = false;
    throw RedisError("Redis 发送命令失败");
  }
  std::string out;
  char type = 0;
  if (!read_reply(out, type)) {
    ready_ = false;
    throw RedisError("Redis 读取响应失败");
  }
  if (type == '-') throw RedisError(out);
  if (type == '$') return out.empty() ? std::nullopt : std::optional<std::string>(out);
  return out;
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
  std::vector<std::string> out;
  try {
    auto r = cmd({"KEYS", pattern});
    if (!r) return out;
    auto j = Json::parse(*r);
    for (const auto& v : j) out.push_back(v.get<std::string>());
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
