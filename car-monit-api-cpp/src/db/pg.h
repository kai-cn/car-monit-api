#pragma once
// PostgreSQL / GaussDB 客户端。
//
// 为什么不用 libpq：工程只允许 vendored 依赖（third_party 中仅 httplib 与
// nlohmann），因此这里直接实现 wire protocol v3 的最小子集：
//   * 启动包 + 参数（client_encoding=UTF8 / DateStyle=ISO / extra_float_digits=3）
//   * 认证：AuthenticationCleartextPassword(3)、MD5(5)、SCRAM-SHA-256(10/11/12)
//   * 简单查询协议（Query 消息），只取文本格式结果
//   * 错误响应映射为 cm::DbError(sqlstate, message)
//
// Java 侧对应 Druid + pgjdbc。池语义保持一致：初始 min-idle、上限 maxActive、
// 借出超时 maxWait。
#include <condition_variable>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

namespace cm::db {

// 口令认证算法选择。openGauss 的 password_encryption_type 决定服务端下发
// AuthenticationMD5Password(5) 还是 AuthenticationSASL(10)：
//   0 = md5 + sha256，1 = 仅 md5，2 = 仅 sha256，3 = 仅 sm3（本工程不支持 sm3）
// 注意 openGauss 的 sha256 与 PostgreSQL 的 SCRAM-SHA-256 不同：
//   openGauss: SaltedPassword = SHA256(SHA256(password) || salt)
//   PostgreSQL: SaltedPassword = PBKDF2-HMAC-SHA256(password, salt, i)
enum class PgAuthMode { Auto, Md5, OpenGaussSha256, ScramSha256 };

PgAuthMode parse_auth_mode(const std::string& mode);

// 服务端 MD5 认证响应：md5(md5(password + user) + salt)。
std::string pg_md5_auth_response(const std::string& password, const std::string& user,
                                 const std::string& salt4);

// openGauss sha256 的 SaltedPassword（32 字节）。
std::vector<uint8_t> opengauss_salted_password(const std::string& password,
                                               const std::vector<uint8_t>& salt);

// RFC 5802 交换结果（SaltedPassword 由调用方按所选算法派生）。
struct ScramProof {
  std::string client_final;         // c=biws,r=<nonce>,p=<client proof>
  std::string client_proof_b64;     // p= 的值
  std::string server_signature_b64; // 期望的 ServerSignature
};

ScramProof compute_scram_proof(const std::vector<uint8_t>& salted_password,
                               const std::string& client_first_bare,
                               const std::string& server_first,
                               const std::string& combined_nonce);

struct PgField {
  std::string name;
  int type_oid = 0;
  int format = 0;
};

struct PgResult {
  std::vector<std::string> columns;
  std::vector<std::vector<std::optional<std::string>>> rows;
  std::vector<PgField> fields;

  bool empty() const { return rows.empty(); }
  std::size_t size() const { return rows.size(); }
  std::optional<std::string> get(std::size_t row, const std::string& column) const;
};

class PgConn {
public:
  PgConn() = default;
  ~PgConn();
  PgConn(const PgConn&) = delete;
  PgConn& operator=(const PgConn&) = delete;

  // auth_mode: auto / md5 / opengauss-sha256 / scram-sha-256。
  // 认证失败（28P01/28000）后不再换算法重试：任何一次认证失败都会进入进程级
  // 熔断（见 auth_guard.h），避免连续失败登录触发账号锁定。
  bool connect(const std::string& host, int port, const std::string& user,
               const std::string& password, const std::string& database, int timeout_ms,
               const std::string& auth_mode = "auto");
  void close();
  bool alive() const { return sock_ >= 0 && ready_; }

  PgResult query(const std::string& sql);
  // 返回 CommandComplete 中受影响行数（0 表示未提供）。
  long long execute(const std::string& sql);
  std::string version();

private:
  bool connect_once(const std::string& host, int port, const std::string& user,
                    const std::string& password, const std::string& database, int timeout_ms);
  bool startup(const std::string& user, const std::string& password,
               const std::string& database);
  bool send_startup(const std::string& user, const std::string& database);
  bool process_auth(const std::string& user, const std::string& password, int timeout_ms);
  bool send_message(char type, const std::string& body);
  bool send_password(const std::string& password);
  bool send_sasl_initial(const std::string& mechanism, const std::string& data);
  bool send_sasl_continue(const std::string& data);
  bool read_bytes(void* dst, std::size_t n);
  bool write_bytes(const void* src, std::size_t n);
  // 读取一条后端消息；返回消息类型，body 输出。
  char read_message(std::string& body, std::string& err_code, std::string& err_msg);
  void drain_until_ready();

  intptr_t sock_ = -1;
  bool ready_ = false;
  PgAuthMode auth_mode_ = PgAuthMode::Auto;
  bool sasl_requested_ = false; // 服务端下发 AuthenticationSASL
  bool auth_failed_ = false;    // 收到 28P01（口令/算法不匹配）
  bool account_locked_ = false; // 收到 28000（账号被锁定）
  bool use_og_sha256_ = true;   // SASL 时使用 openGauss 派生（否则标准 PBKDF2）
  std::string server_signature_b64_;
};

class PgPool {
public:
  static PgPool& instance();

  // connect_timeout_ms：TCP 建连 + 认证超时；max_wait_ms：借出连接等待超时
  // （Druid maxWait）。两者语义不同，此前混用同一值。
  void init(const std::string& host, int port, const std::string& user,
            const std::string& password, const std::string& database, int max_conns,
            int min_idle, int connect_timeout_ms, const std::string& auth_mode = "auto",
            int max_wait_ms = 60000);
  void shutdown();

  PgResult query(const std::string& sql);
  long long execute(const std::string& sql);
  // 事务：Java 侧 @Transactional 保护的成组写操作使用。
  long long execute_in_tx(const std::vector<std::string>& sqls);
  // 多语句事务（含查询），按顺序执行；任何一条失败回滚并抛出 DbError。
  std::vector<PgResult> transaction(const std::vector<std::pair<std::string, bool>>& stmts);
  bool available();

private:
  PgPool() = default;

  struct ConnSlot {
    std::unique_ptr<PgConn> conn;
    bool in_use = false;
    bool reserved = false;  // 锁外建连的占位标记
    long long reserve_gen = 0; // 预留时的池代数（shutdown/re-init 防串槽）
  };
  struct Borrowed {
    std::size_t index = std::string::npos;
    PgConn* raw = nullptr;
  };

  // 借出连接：锁内取空闲/预留新槽，锁外建连（不持 mu_ 执行 connect，
  // DB 不可达时不再把全站请求串行阻塞在池锁上）。
  Borrowed acquire();
  void release(std::size_t index, bool broken);
  void note_connect_result_locked(bool ok); // mu_ 持有下调用

  std::mutex mu_;
  std::condition_variable cv_;
  std::vector<ConnSlot> slots_;
  std::string host_, user_, password_, database_, auth_mode_ = "auto";
  int port_ = 5432, max_ = 20, min_ = 5, timeout_ms_ = 10000, wait_ms_ = 60000;
  long long generation_ = 0;
  // 网络故障熔断：连续 kConnectFailureThreshold 次建连失败进入 kConnectCooldownMs
  // 冷却，冷却期内 acquire 直接抛错，避免每次请求都等满 connect 超时。
  int consecutive_connect_failures_ = 0;
  long long breaker_until_epoch_ms_ = 0;
  bool inited_ = false;

  static constexpr int kConnectFailureThreshold = 3;
  static constexpr long long kConnectCooldownMs = 30000;
};

} // namespace cm::db
