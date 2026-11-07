#include "db/pg.h"

#include "common/crypto.h"
#include "common/error.h"
#include "common/logging.h"
#include "common/utils.h"
#include "db/auth_guard.h"

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <thread>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <cerrno>
#include <fcntl.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
#endif

namespace cm::db {
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
int last_error() { return WSAGetLastError(); }
#else
using sock_t = int;
constexpr intptr_t kInvalid = -1;
void ensure_wsa() {}
int last_error() { return errno; }
#endif

uint32_t be32(const std::string& s, std::size_t off) {
  return (uint32_t(uint8_t(s[off])) << 24) | (uint32_t(uint8_t(s[off + 1])) << 16) |
         (uint32_t(uint8_t(s[off + 2])) << 8) | uint32_t(uint8_t(s[off + 3]));
}

uint16_t be16(const std::string& s, std::size_t off) {
  return uint16_t((uint16_t(uint8_t(s[off])) << 8) | uint16_t(uint8_t(s[off + 1])));
}

void put32(std::string& out, uint32_t v) {
  out.push_back(char((v >> 24) & 0xFF));
  out.push_back(char((v >> 16) & 0xFF));
  out.push_back(char((v >> 8) & 0xFF));
  out.push_back(char(v & 0xFF));
}

std::string pg_error_fields(const std::string& body, std::string& code) {
  std::string msg;
  std::size_t i = 0;
  while (i < body.size() && body[i] != 0) {
    char field = body[i++];
    std::size_t end = body.find('\0', i);
    if (end == std::string::npos) break;
    std::string value = body.substr(i, end - i);
    if (field == 'C') code = value;
    if (field == 'M') msg = value;
    if (field == 'D' && msg.empty()) msg = value;
    i = end + 1;
  }
  return msg;
}

std::vector<uint8_t> str_bytes(const std::string& s) {
  return std::vector<uint8_t>(s.begin(), s.end());
}

} // namespace

PgAuthMode parse_auth_mode(const std::string& mode) {
  std::string m = utils::to_lower(utils::trim(mode));
  if (m == "md5") return PgAuthMode::Md5;
  if (m == "opengauss-sha256" || m == "opengauss" || m == "sha256")
    return PgAuthMode::OpenGaussSha256;
  if (m == "scram-sha-256" || m == "scram" || m == "postgres")
    return PgAuthMode::ScramSha256;
  return PgAuthMode::Auto;
}

std::string pg_md5_auth_response(const std::string& password, const std::string& user,
                                 const std::string& salt4) {
  // pgjdbc / libpq 的两级摘要：md5( md5(password + user) + salt )，前缀 "md5"。
  std::string inner = "md5" + crypto::md5_hex(password + user);
  return "md5" + crypto::md5_hex(inner + salt4);
}

std::vector<uint8_t> opengauss_salted_password(const std::string& password,
                                               const std::vector<uint8_t>& salt) {
  // openGauss 专有：SHA256(SHA256(password) || salt)，不用 PBKDF2 迭代。
  std::vector<uint8_t> buf = crypto::sha256_raw(password);
  buf.insert(buf.end(), salt.begin(), salt.end());
  return crypto::sha256_raw(std::string(buf.begin(), buf.end()));
}

ScramProof compute_scram_proof(const std::vector<uint8_t>& salted_password,
                               const std::string& client_first_bare,
                               const std::string& server_first,
                               const std::string& combined_nonce) {
  ScramProof out;
  std::string client_final_wo_proof = "c=biws,r=" + combined_nonce;
  std::string auth_message =
      client_first_bare + "," + server_first + "," + client_final_wo_proof;

  std::vector<uint8_t> client_key =
      crypto::hmac_sha256(salted_password, str_bytes("Client Key"));
  std::vector<uint8_t> stored_key =
      crypto::sha256_raw(std::string(client_key.begin(), client_key.end()));
  std::vector<uint8_t> client_sig = crypto::hmac_sha256(stored_key, str_bytes(auth_message));
  std::vector<uint8_t> proof(client_key.size());
  for (std::size_t i = 0; i < proof.size(); ++i) proof[i] = client_key[i] ^ client_sig[i];

  out.client_proof_b64 = utils::base64_encode(std::string(proof.begin(), proof.end()));
  out.client_final = client_final_wo_proof + ",p=" + out.client_proof_b64;

  std::vector<uint8_t> server_key =
      crypto::hmac_sha256(salted_password, str_bytes("Server Key"));
  std::vector<uint8_t> server_sig = crypto::hmac_sha256(server_key, str_bytes(auth_message));
  out.server_signature_b64 = utils::base64_encode(std::string(server_sig.begin(), server_sig.end()));
  return out;
}

std::optional<std::string> PgResult::get(std::size_t row, const std::string& column) const {
  auto it = std::find(columns.begin(), columns.end(), column);
  if (it == columns.end()) return std::nullopt;
  std::size_t idx = std::size_t(it - columns.begin());
  if (row >= rows.size() || idx >= rows[row].size()) return std::nullopt;
  return rows[row][idx];
}

PgConn::~PgConn() { close(); }

void PgConn::close() {
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

bool PgConn::connect(const std::string& host, int port, const std::string& user,
                     const std::string& password, const std::string& database, int timeout_ms,
                     const std::string& auth_mode) {
  auth_mode_ = parse_auth_mode(auth_mode);
  auto& guard = AuthGuard::instance();
  // 所有物理连接都必须经过熔断器：熔断后直接返回，不创建 socket、不发送启动包。
  auto outcome = guard.attempt([&]() -> AuthGuard::Outcome {
    use_og_sha256_ = (auth_mode_ != PgAuthMode::ScramSha256);
    sasl_requested_ = false;
    auth_failed_ = false;
    account_locked_ = false;
    server_signature_b64_.clear();
    if (connect_once(host, port, user, password, database, timeout_ms))
      return AuthGuard::Outcome::Ok;
    close();
    ready_ = false;
    // 认证类错误立刻熔断；不再换算法重试（重试本身也是一次失败登录）。
    if (auth_failed_ || account_locked_) {
      guard.mark_auth_failure(account_locked_ ? "28000" : "28P01",
                              account_locked_ ? "账号被锁定" : "口令被拒绝");
      return AuthGuard::Outcome::AuthFailed;
    }
    return AuthGuard::Outcome::OtherError;
  });
  return outcome == AuthGuard::Outcome::Ok;
}

bool PgConn::connect_once(const std::string& host, int port, const std::string& user,
                          const std::string& password, const std::string& database,
                          int timeout_ms) {
  ensure_wsa();
  close();
  sock_t s = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (static_cast<intptr_t>(s) == kInvalid) {
    CM_LOG_ERROR("db.pg") << "socket() 失败: " << last_error();
    return false;
  }
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(uint16_t(port));
  if (inet_pton(AF_INET, host.c_str(), &addr.sin_addr) != 1) {
    addrinfo hints{};
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    addrinfo* res = nullptr;
    if (getaddrinfo(host.c_str(), nullptr, &hints, &res) != 0 || !res) {
      CM_LOG_ERROR("db.pg") << "无法解析主机: " << host;
      close();
      return false;
    }
    addr.sin_addr = reinterpret_cast<sockaddr_in*>(res->ai_addr)->sin_addr;
    freeaddrinfo(res);
  }

#ifdef _WIN32
  u_long nonblock = 1;
  ioctlsocket(s, FIONBIO, &nonblock);
#else
  fcntl(s, F_SETFL, O_NONBLOCK);
#endif
  int rc = ::connect(s, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
#ifdef _WIN32
  bool in_progress = (rc == SOCKET_ERROR && last_error() == WSAEWOULDBLOCK);
#else
  bool in_progress = (rc < 0 && errno == EINPROGRESS);
#endif
  if (in_progress) {
    fd_set set;
    FD_ZERO(&set);
    FD_SET(s, &set);
    timeval tv{timeout_ms / 1000, (timeout_ms % 1000) * 1000};
#ifdef _WIN32
    int sel = select(0, nullptr, &set, nullptr, &tv);
#else
    int sel = select(int(s) + 1, nullptr, &set, nullptr, &tv);
#endif
    if (sel <= 0) {
      CM_LOG_ERROR("db.pg") << "连接超时: " << host << ":" << port;
      close();
      return false;
    }
  } else if (rc < 0) {
    CM_LOG_ERROR("db.pg") << "connect 失败: " << host << ":" << port << " err=" << last_error();
    close();
    return false;
  }

#ifdef _WIN32
  u_long blocking = 0;
  ioctlsocket(s, FIONBIO, &blocking);
  int timeout = timeout_ms;
  setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
  setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
#else
  // POSIX：恢复阻塞模式并设置收发超时，与 Windows 分支同语义。
  // 此前只有 _WIN32 分支做恢复（审阅 §3.3 R6），Linux 上连接后 socket 仍是
  // 非阻塞，后续所有 recv/send 直接 EAGAIN 失败，DB 客户端整体不可用。
  int flags = fcntl(s, F_GETFL, 0);
  if (flags >= 0) fcntl(s, F_SETFL, flags & ~O_NONBLOCK);
  timeval tv{};
  tv.tv_sec = timeout_ms / 1000;
  tv.tv_usec = (timeout_ms % 1000) * 1000;
  setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
  setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#endif
  sock_ = intptr_t(s);
  return startup(user, password, database) && ready_;
}

bool PgConn::write_bytes(const void* src, std::size_t n) {
  const char* p = static_cast<const char*>(src);
  std::size_t left = n;
  while (left > 0) {
#ifdef _WIN32
    int chunk = int(std::min<std::size_t>(left, 1u << 30));
    int sent = ::send(sock_t(sock_), p, chunk, 0);
#else
    ssize_t sent = ::send(int(sock_), p, left, 0);
#endif
    if (sent <= 0) return false;
    p += sent;
    left -= std::size_t(sent);
  }
  return true;
}

bool PgConn::read_bytes(void* dst, std::size_t n) {
  char* p = static_cast<char*>(dst);
  std::size_t left = n;
  while (left > 0) {
#ifdef _WIN32
    int chunk = int(std::min<std::size_t>(left, 1u << 30));
    int got = ::recv(sock_t(sock_), p, chunk, 0);
#else
    ssize_t got = ::recv(int(sock_), p, left, 0);
#endif
    if (got <= 0) return false;
    p += got;
    left -= std::size_t(got);
  }
  return true;
}

bool PgConn::send_message(char type, const std::string& body) {
  std::string msg;
  msg.reserve(body.size() + 5);
  msg.push_back(type);
  put32(msg, uint32_t(body.size() + 4));
  msg += body;
  return write_bytes(msg.data(), msg.size());
}

bool PgConn::send_startup(const std::string& user, const std::string& database) {
  std::string body;
  put32(body, 196608); // 3.0
  auto add = [&body](const std::string& k, const std::string& v) {
    body += k;
    body.push_back('\0');
    body += v;
    body.push_back('\0');
  };
  add("user", user);
  add("database", database);
  add("client_encoding", "UTF8");
  add("DateStyle", "ISO");
  add("extra_float_digits", "3");
  add("application_name", "car-monit-api-cpp");
  body.push_back('\0');
  std::string framed;
  put32(framed, uint32_t(body.size() + 4));
  framed += body;
  return write_bytes(framed.data(), framed.size());
}

bool PgConn::send_password(const std::string& password) {
  std::string body = password;
  body.push_back('\0');
  return send_message('p', body);
}

bool PgConn::send_sasl_initial(const std::string& mechanism, const std::string& data) {
  std::string body = mechanism;
  body.push_back('\0');
  put32(body, uint32_t(data.size()));
  body += data;
  return send_message('p', body);
}

bool PgConn::send_sasl_continue(const std::string& data) {
  return send_message('p', data);
}

char PgConn::read_message(std::string& body, std::string& err_code, std::string& err_msg) {
  char type = 0;
  if (!read_bytes(&type, 1)) return 0;
  char lenbuf[4];
  if (!read_bytes(lenbuf, 4)) return 0;
  uint32_t len = (uint32_t(uint8_t(lenbuf[0])) << 24) | (uint32_t(uint8_t(lenbuf[1])) << 16) |
                 (uint32_t(uint8_t(lenbuf[2])) << 8) | uint32_t(uint8_t(lenbuf[3]));
  if (len < 4 || len > (1u << 24)) return 0;
  body.assign(len - 4, '\0');
  if (len > 4 && !read_bytes(body.data(), len - 4)) return 0;
  if (type == 'E') err_msg = pg_error_fields(body, err_code);
  return type;
}

void PgConn::drain_until_ready() {
  std::string body, code, msg;
  while (true) {
    char t = read_message(body, code, msg);
    if (t == 0 || t == 'Z') break;
    if (t == 'S') continue;
  }
}

bool PgConn::process_auth(const std::string& user, const std::string& password, int /*timeout_ms*/) {
  std::string body, code, msg;
  std::string scram_nonce;
  std::string client_first_bare;
  std::string server_first;
  std::vector<uint8_t> salt;

  while (true) {
    char t = read_message(body, code, msg);
    if (t == 0) return false;
    if (t == 'E') {
      throw DbError(code, msg);
    }
    if (t == 'S' || t == 'K') continue;
    if (t == 'Z') {
      ready_ = true;
      return true;
    }
    if (t != 'R') {
      // 认证阶段出现非 R 消息（Notice 等），继续。
      continue;
    }
    uint32_t auth_code = body.size() >= 4 ? be32(body, 0) : 0;
    CM_LOG_DEBUG("db.pg") << "认证消息 code=" << auth_code;
    switch (auth_code) {
      case 0:
        break; // AuthenticationOk
      case 3:
        if (!send_password(password)) return false;
        break;
      case 5: {
        if (body.size() < 8) return false;
        std::string salt4 = body.substr(4, 4);
        std::string outer = pg_md5_auth_response(password, user, salt4);
        // 只记录长度，不输出摘要本身（摘要可用于反推口令）。
        CM_LOG_DEBUG("db.pg") << "MD5 认证: user=" << user << " pwdlen=" << password.size()
                              << " resp_len=" << outer.size();
        if (!send_password(outer)) return false;
        break;
      }
      case 10: {
        // SASL：body[4:] 是机制列表（cstring\0 重复）
        sasl_requested_ = true;
        std::size_t i = 4;
        bool found = false;
        while (i < body.size() && body[i] != 0) {
          std::size_t end = body.find('\0', i);
          if (end == std::string::npos) break;
          if (body.substr(i, end - i) == "SCRAM-SHA-256") found = true;
          i = end + 1;
        }
        if (auth_mode_ == PgAuthMode::Md5) {
          CM_LOG_ERROR("db.pg") << "配置 auth-mode=md5，但服务端要求 SASL 认证";
          return false;
        }
        if (!found) {
          CM_LOG_ERROR("db.pg") << "服务端未提供 SCRAM-SHA-256 认证机制";
          return false;
        }
        scram_nonce = crypto::random_hex(18);
        client_first_bare = "n=,r=" + scram_nonce;
        std::string client_first = "n,,n=,r=" + scram_nonce;
        if (!send_sasl_initial("SCRAM-SHA-256", client_first)) return false;
        break;
      }
      case 11: {
        server_first = body.substr(4);
        // 解析 r=, s=, i=
        std::string combined_nonce, salt_b64;
        int iter = 0;
        std::size_t pos = 0;
        while (pos < server_first.size()) {
          std::size_t comma = server_first.find(',', pos);
          std::string part = server_first.substr(pos, comma == std::string::npos
                                                          ? std::string::npos
                                                          : comma - pos);
          if (part.rfind("r=", 0) == 0) combined_nonce = part.substr(2);
          if (part.rfind("s=", 0) == 0) salt_b64 = part.substr(2);
          if (part.rfind("i=", 0) == 0) iter = std::atoi(part.c_str() + 2);
          if (comma == std::string::npos) break;
          pos = comma + 1;
        }
        if (combined_nonce.empty() || salt_b64.empty()) return false;
        auto salt_opt = utils::base64_decode(salt_b64);
        if (!salt_opt) return false;
        salt.assign(salt_opt->begin(), salt_opt->end());

        // openGauss：SHA256(SHA256(password)||salt)；PostgreSQL：PBKDF2-HMAC-SHA256。
        std::vector<uint8_t> salted =
            use_og_sha256_
                ? opengauss_salted_password(password, salt)
                : crypto::pbkdf2_sha256(password, salt, iter > 0 ? iter : 4096, 32);
        CM_LOG_DEBUG("db.pg") << "SASL 派生="
                              << (use_og_sha256_ ? "openGauss-SHA256" : "PBKDF2-SCRAM-SHA-256")
                              << " salt_len=" << salt.size() << " iterations=" << iter;
        ScramProof proof =
            compute_scram_proof(salted, client_first_bare, server_first, combined_nonce);
        server_signature_b64_ = proof.server_signature_b64;
        if (!send_sasl_continue(proof.client_final)) return false;
        break;
      }
      case 12: {
        std::string server_final = body.substr(4);
        // 验证 ServerSignature（RFC 5802），失败也不影响连接建立，仅记录。
        if (server_final.rfind("v=", 0) == 0 && !server_signature_b64_.empty() &&
            server_signature_b64_ != server_final.substr(2))
          CM_LOG_WARN("db.pg") << "SCRAM 服务端签名校验不一致（继续连接）";
        break;
      }
      default:
        CM_LOG_ERROR("db.pg") << "不支持的认证方式: " << auth_code;
        return false;
    }
  }
}

bool PgConn::startup(const std::string& user, const std::string& password,
                     const std::string& database) {
  try {
    if (!send_startup(user, database)) return false;
    return process_auth(user, password, 0);
  } catch (const DbError& e) {
    std::string state = e.sqlstate();
    auth_failed_ = (state == "28P01");
    account_locked_ = (state == "28000");
    CM_LOG_ERROR("db.pg") << "启动失败 [" << state << "] " << e.message();
    if (account_locked_)
      CM_LOG_ERROR("db.pg")
          << "账号被锁定：需在 DB 侧执行 ALTER USER <user> ACCOUNT UNLOCK;（或等待 password_lock_time 到期）";
    else if (auth_failed_)
      CM_LOG_ERROR("db.pg")
          << "认证被拒：请核对 password、password_encryption_type 与 db.auth-mode 是否匹配";
    return false;
  } catch (const std::exception& e) {
    CM_LOG_ERROR("db.pg") << "启动异常: " << e.what();
    return false;
  }
}

PgResult PgConn::query(const std::string& sql) {
  PgResult result;
  if (!alive()) throw DbError("08003", "数据库连接已关闭");
  std::string body;
  body.reserve(sql.size() + 1);
  body += sql;
  body.push_back('\0');
  if (!send_message('Q', body)) throw DbError("08006", "发送查询失败");

  std::string msg_body, code, err_msg;
  std::string pending_code, pending_msg;
  while (true) {
    char t = read_message(msg_body, code, err_msg);
    if (t == 0) {
      ready_ = false;
      throw DbError("08006", "读取响应失败");
    }
    if (t == 'E') {
      pending_code = code;
      pending_msg = err_msg;
      continue;
    }
    if (t == 'T') {
      result.columns.clear();
      result.fields.clear();
      uint16_t n = be16(msg_body, 0);
      std::size_t pos = 2;
      for (uint16_t i = 0; i < n; ++i) {
        std::size_t end = msg_body.find('\0', pos);
        PgField f;
        f.name = msg_body.substr(pos, end - pos);
        pos = end + 1;
        f.type_oid = int(be32(msg_body, pos + 6));
        pos += 18;
        result.columns.push_back(f.name);
        result.fields.push_back(f);
      }
    } else if (t == 'D') {
      uint16_t n = be16(msg_body, 0);
      std::size_t pos = 2;
      std::vector<std::optional<std::string>> row;
      row.reserve(n);
      for (uint16_t i = 0; i < n; ++i) {
        int32_t len = int32_t(be32(msg_body, pos));
        pos += 4;
        if (len < 0) {
          row.emplace_back(std::nullopt);
        } else {
          row.emplace_back(msg_body.substr(pos, std::size_t(len)));
          pos += std::size_t(len);
        }
      }
      result.rows.push_back(std::move(row));
    } else if (t == 'Z') {
      ready_ = true;
      break;
    }
  }
  if (!pending_msg.empty() || !pending_code.empty())
    throw DbError(pending_code.empty() ? "42601" : pending_code, pending_msg);
  return result;
}

long long PgConn::execute(const std::string& sql) {
  if (!alive()) throw DbError("08003", "数据库连接已关闭");
  std::string body = sql;
  body.push_back('\0');
  if (!send_message('Q', body)) throw DbError("08006", "发送语句失败");

  long long affected = 0;
  std::string msg_body, code, err_msg, pending_code, pending_msg;
  while (true) {
    char t = read_message(msg_body, code, err_msg);
    if (t == 0) {
      ready_ = false;
      throw DbError("08006", "读取响应失败");
    }
    if (t == 'E') {
      pending_code = code;
      pending_msg = err_msg;
      continue;
    }
    if (t == 'C') {
      std::string tag = msg_body;
      // INSERT 0 n / UPDATE n / DELETE n
      std::size_t sp = tag.rfind(' ');
      if (sp != std::string::npos) {
        try { affected = std::stoll(tag.substr(sp + 1)); } catch (...) {}
      }
    }
    if (t == 'Z') {
      ready_ = true;
      break;
    }
  }
  if (!pending_msg.empty() || !pending_code.empty())
    throw DbError(pending_code.empty() ? "42601" : pending_code, pending_msg);
  return affected;
}

std::string PgConn::version() {
  try {
    auto r = query("SELECT version()");
    if (!r.rows.empty() && r.rows[0][0]) return *r.rows[0][0];
  } catch (...) {
  }
  return "";
}

// ---------------- PgPool ----------------

PgPool& PgPool::instance() {
  static PgPool pool;
  return pool;
}

void PgPool::init(const std::string& host, int port, const std::string& user,
                  const std::string& password, const std::string& database, int max_conns,
                  int min_idle, int connect_timeout_ms, const std::string& auth_mode,
                  int max_wait_ms) {
  std::lock_guard<std::mutex> lock(mu_);
  // 二次防线：即便调用方没做启动校验，口令不合法时也不初始化连接池（不发起连接）。
  auto check = check_password(password);
  if (!check.ok) {
    CM_LOG_ERROR("db.pg") << "拒绝初始化连接池：" << check.problem;
    inited_ = false;
    return;
  }
  host_ = host;
  port_ = port;
  user_ = user;
  password_ = password;
  database_ = database;
  auth_mode_ = auth_mode;
  max_ = max_conns > 0 ? max_conns : 20;
  min_ = min_idle > 0 ? min_idle : 5;
  timeout_ms_ = connect_timeout_ms > 0 ? connect_timeout_ms : 10000;
  wait_ms_ = max_wait_ms > 0 ? max_wait_ms : 60000;
  slots_.clear();
  ++generation_;
  consecutive_connect_failures_ = 0;
  breaker_until_epoch_ms_ = 0;
  inited_ = true;
}

void PgPool::shutdown() {
  std::lock_guard<std::mutex> lock(mu_);
  for (auto& slot : slots_) slot.conn.reset();
  slots_.clear();
  ++generation_;
  inited_ = false;
  cv_.notify_all();
}

bool PgPool::available() { return inited_; }

void PgPool::note_connect_result_locked(bool ok) {
  if (ok) {
    consecutive_connect_failures_ = 0;
    breaker_until_epoch_ms_ = 0;
    return;
  }
  if (++consecutive_connect_failures_ >= kConnectFailureThreshold) {
    breaker_until_epoch_ms_ =
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count() +
        kConnectCooldownMs;
    consecutive_connect_failures_ = 0;
    CM_LOG_ERROR("db.pg") << "连续 " << kConnectFailureThreshold
                          << " 次建连失败，进入 " << kConnectCooldownMs / 1000
                          << "s 熔断冷却（认证失败由 AuthGuard 单独熔断）";
  }
}

PgPool::Borrowed PgPool::acquire() {
  std::unique_lock<std::mutex> lock(mu_);
  if (!inited_) throw DbError("08003", "数据库连接池未初始化");
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(wait_ms_);
  while (true) {
    // 网络故障熔断：冷却期内快速失败，不再每次请求都等满建连超时。
    if (breaker_until_epoch_ms_ > 0) {
      long long now = std::chrono::duration_cast<std::chrono::milliseconds>(
                          std::chrono::system_clock::now().time_since_epoch())
                          .count();
      if (now < breaker_until_epoch_ms_) {
        throw DbError("08001", "数据库连接连续失败，熔断冷却中（约 " +
                                   std::to_string((breaker_until_epoch_ms_ - now + 999) / 1000) +
                                   "s 后允许重试）");
      }
      breaker_until_epoch_ms_ = 0; // 冷却结束，放行一次探测
    }
    // 1) 锁内取空闲健康连接。
    for (std::size_t i = 0; i < slots_.size(); ++i) {
      if (!slots_[i].in_use && !slots_[i].reserved && slots_[i].conn && slots_[i].conn->alive()) {
        slots_[i].in_use = true;
        return Borrowed{i, slots_[i].conn.get()};
      }
    }
    // 2) 未达上限：优先复用空槽，否则追加新槽做预留，然后锁外建连。
    //    修复（审阅 §3.3 R8）：原实现在持锁状态下 connect（最长等满建连超时），
    //    DB 抖动时 16 个 HTTP 线程全部串行阻塞在池锁上形成级联雪崩。
    std::size_t reserved_index = std::string::npos;
    for (std::size_t i = 0; i < slots_.size(); ++i) {
      if (!slots_[i].in_use && !slots_[i].reserved && !slots_[i].conn) {
        slots_[i].reserved = true;
        slots_[i].reserve_gen = generation_;
        reserved_index = i;
        break;
      }
    }
    if (reserved_index == std::string::npos && slots_.size() < std::size_t(max_)) {
      ConnSlot slot;
      slot.reserved = true;
      slot.reserve_gen = generation_;
      slots_.push_back(std::move(slot));
      reserved_index = slots_.size() - 1;
    }
    if (reserved_index != std::string::npos) {
      const long long gen = generation_;
      // 锁外建连：连接参数先拷贝到栈上，避免与 init()/shutdown() 竞争。
      const std::string host = host_, user = user_, password = password_;
      const std::string database = database_, auth_mode = auth_mode_;
      const int port = port_, connect_timeout = timeout_ms_;
      lock.unlock();
      auto conn = std::make_unique<PgConn>();
      const bool ok = conn->connect(host, port, user, password, database, connect_timeout, auth_mode);
      lock.lock();
      // 池在锁外建连期间被 shutdown/re-init：丢弃本连接（gen 不匹配）。
      if (!inited_ || reserved_index >= slots_.size() ||
          !slots_[reserved_index].reserved || slots_[reserved_index].reserve_gen != gen) {
        cv_.notify_all();
        throw DbError("08003", "数据库连接池已关闭");
      }
      note_connect_result_locked(ok);
      if (!ok) {
        // 回收占位（保留空槽供下次复用，槽位总数不增长）。
        slots_[reserved_index].reserved = false;
        cv_.notify_all();
        throw DbError("08001", "无法连接数据库 " + host_ + ":" + std::to_string(port_));
      }
      slots_[reserved_index].conn = std::move(conn);
      slots_[reserved_index].reserved = false;
      slots_[reserved_index].in_use = true;
      return Borrowed{reserved_index, slots_[reserved_index].conn.get()};
    }
    // 3) 达到上限：条件变量等待空闲（maxWait 超时），替代原 10ms 轮询。
    if (cv_.wait_until(lock, deadline) == std::cv_status::timeout) {
      for (std::size_t i = 0; i < slots_.size(); ++i) {
        if (!slots_[i].in_use && !slots_[i].reserved && slots_[i].conn && slots_[i].conn->alive()) {
          slots_[i].in_use = true;
          return Borrowed{i, slots_[i].conn.get()};
        }
      }
      throw DbError("08001", "等待数据库连接超时（maxWait=" + std::to_string(wait_ms_) + "ms）");
    }
  }
}

void PgPool::release(std::size_t index, bool broken) {
  {
    std::lock_guard<std::mutex> guard(mu_);
    if (index < slots_.size()) {
      if (broken) slots_[index].conn.reset(); // 空槽保留复用
      slots_[index].in_use = false;
    }
  }
  cv_.notify_all();
}

PgResult PgPool::query(const std::string& sql) {
  Borrowed b = acquire();
  try {
    PgResult result = b.raw->query(sql);
    release(b.index, false);
    return result;
  } catch (const DbError& e) {
    release(b.index, e.sqlstate().rfind("08", 0) == 0);
    throw;
  } catch (...) {
    // 修复（审阅 §4.2 #5）：非 DbError 异常此前不会归还槽位，连接被永久占用。
    release(b.index, true);
    throw;
  }
}

long long PgPool::execute(const std::string& sql) {
  Borrowed b = acquire();
  try {
    long long affected = b.raw->execute(sql);
    release(b.index, false);
    return affected;
  } catch (const DbError& e) {
    release(b.index, e.sqlstate().rfind("08", 0) == 0);
    throw;
  } catch (...) {
    release(b.index, true);
    throw;
  }
}

long long PgPool::execute_in_tx(const std::vector<std::string>& sqls) {
  std::vector<std::pair<std::string, bool>> stmts;
  stmts.reserve(sqls.size());
  for (const auto& s : sqls) stmts.emplace_back(s, false);
  auto results = transaction(stmts);
  long long total = 0;
  for (const auto& r : results) total += static_cast<long long>(r.rows.size());
  return total;
}

std::vector<PgResult> PgPool::transaction(
    const std::vector<std::pair<std::string, bool>>& stmts) {
  Borrowed b = acquire();
  bool broken = false;
  std::vector<PgResult> out;
  try {
    b.raw->execute("BEGIN");
    for (const auto& st : stmts) {
      if (st.second) {
        out.push_back(b.raw->query(st.first));
      } else {
        b.raw->execute(st.first);
        out.emplace_back();
      }
    }
    b.raw->execute("COMMIT");
    release(b.index, false);
    return out;
  } catch (const DbError& e) {
    broken = e.sqlstate().rfind("08", 0) == 0;
    try {
      b.raw->execute("ROLLBACK");
    } catch (...) {
      broken = true; // 回滚也失败，连接状态不可信
    }
    release(b.index, broken);
    throw;
  } catch (...) {
    try {
      b.raw->execute("ROLLBACK");
    } catch (...) {
    }
    release(b.index, true);
    throw;
  }
}

} // namespace cm::db
