#pragma once
// PostgreSQL / GaussDB 客户端（基于 libpqxx + libpq）。
//
// 历史：迁移初期为保证“仅 vendored 头文件”直接实现了 wire protocol v3 的最小子集，
// 并自带 MD5 / openGauss SHA256 / SCRAM 派生。该实现维护成本高、参数绑定缺失，
// 且认证派生一旦与 openGauss 行为不一致就会触发失败登录锁定。
//
// 本轮（P2）改为 libpqxx（下层 libpq）：
//   * 认证、TLS、协议细节交给 libpq；
//   * 对外保留 PgResult / PgPool 等接口，业务层查询代码不需要感知实现变化；
//   * 新增参数绑定（$1..$n）与语句超时，消除用户输入拼接 SQL 的主要面。
//
// 与 Java Druid + pgjdbc 对齐：maxActive 上限、maxWait 借出超时、connectTimeout
// 建连超时；连接池仍采用懒建连（启动不主动连库，避免 DB 未就绪时反复失败登录）。
#include <condition_variable>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace cm::db {

// SQL 参数：nullopt 绑定为 NULL，其余按文本形式绑定（服务端按列类型解析）。
using PgParams = std::vector<std::optional<std::string>>;

struct PgField {
  std::string name;
  int type_oid = 0;
  int format = 0;
};

struct PgResult {
  std::vector<std::string> columns;
  std::vector<std::vector<std::optional<std::string>>> rows;
  std::vector<PgField> fields;
  // 非查询语句（INSERT/UPDATE/DELETE）的受影响行数；查询语句为 0。
  long long affected = 0;

  bool empty() const { return rows.empty(); }
  std::size_t size() const { return rows.size(); }
  std::optional<std::string> get(std::size_t row, const std::string& column) const;
};

// 单条物理连接的参数。字段与 libpq conninfo 对齐。
struct PgConnOptions {
  std::string host = "127.0.0.1";
  int port = 5432;
  std::string user;
  std::string password;
  std::string database;
  // libpq sslmode：disable / allow / prefer / require / verify-ca / verify-full。
  // 默认 prefer（与 libpq 默认一致）；生产环境建议 require，内网可配 verify-full。
  std::string sslmode = "prefer";
  // verify-ca / verify-full 时使用（为空则用系统默认 CA）。
  std::string sslrootcert;
  // 建连超时（connectTimeout，毫秒；libpq 以秒为单位，向上取整）。
  int connect_timeout_ms = 10000;
  // 语句超时（0 = 不设置）。防止单条慢 SQL 长期占用连接。
  int statement_timeout_ms = 30000;
};

// 构造 libpq conninfo（key=value，值做单引号转义）。纯函数，便于单测。
std::string build_conninfo(const PgConnOptions& options);

// 把 libpq 建连失败文本归类为 SQLSTATE：
//   28P01 口令被拒 / 28000 账号锁定或认证规格不允许 / 08001 其他连接失败。
// libpq 建连失败不返回 PGresult，只能依据错误文本归类；该函数可脱离连接测试。
std::string classify_connect_error(const std::string& message);

class PgConn {
public:
  PgConn();
  ~PgConn();
  PgConn(const PgConn&) = delete;
  PgConn& operator=(const PgConn&) = delete;

  // 建立物理连接并完成认证。失败返回 false（认证类失败已由 AuthGuard 记录，
  // 具体 SQLSTATE 可通过 last_sqlstate() 读取，供调用方构造错误信息）。
  bool connect(const PgConnOptions& options);
  void close();
  bool alive() const;
  const std::string& last_sqlstate() const;

  PgResult query(const std::string& sql);
  PgResult query(const std::string& sql, const PgParams& params);
  long long execute(const std::string& sql);
  long long execute(const std::string& sql, const PgParams& params);
  std::string version();
  // 事务：逐条执行，失败整体回滚。second=true 表示需要返回结果集。
  std::vector<PgResult> transaction(
      const std::vector<std::pair<std::string, bool>>& stmts);

private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
  std::string last_sqlstate_;
};

class PgPool {
public:
  static PgPool& instance();

  // max_wait_ms 为借出连接等待超时（Druid maxWait）。
  void init(const PgConnOptions& options, int max_conns, int min_idle,
            int max_wait_ms = 60000);
  void shutdown();

  PgResult query(const std::string& sql);
  PgResult query(const std::string& sql, const PgParams& params);
  long long execute(const std::string& sql);
  long long execute(const std::string& sql, const PgParams& params);
  std::vector<PgResult> transaction(
      const std::vector<std::pair<std::string, bool>>& stmts);
  // 事务：Java 侧 @Transactional 保护的成组写操作使用；返回受影响行数之和。
  long long execute_in_tx(const std::vector<std::string>& sqls);
  bool available();
  // 健康检查用：当前池内处于可用状态的物理连接数（锁内统计，不主动建连）。
  int live_connections();
  // 池上限（供 /metrics 与单测断言；不主动建连）。
  int max_connections();

private:
  PgPool() = default;

  struct ConnSlot {
    std::unique_ptr<PgConn> conn;
    bool in_use = false;
    bool reserved = false;     // 锁外建连的占位标记
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
  PgConnOptions options_;
  int max_ = 20, min_ = 5, wait_ms_ = 60000;
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
