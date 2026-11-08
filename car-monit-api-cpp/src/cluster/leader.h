#pragma once
// 多实例单活选主（Redis 分布式锁）。
//
// 背景：调度器（TrackTask/DataFlowTask/对账）与 SnapshotFlowSync 的全量/增量
// 同步在 Java 侧由单实例执行；C++ 侧原先每个进程各自启动，多实例部署会重复
// 触发。这里用 Redis SET NX PX + 定期续期实现 leader 选举：
//   - 只有 leader 执行调度与同步，follower 仅提供 HTTP 只读/写入接口；
//   - 进程崩溃后锁随 TTL 自动过期，standby 在下一个续期周期接管；
//   - 锁获取失败不影响 HTTP 启动与请求处理。
//
// Redis 不可用时的行为由 fail_open 决定（见 docs/DECISIONS.md D-017）：
//   - false（默认，fail-closed）：暂停调度/同步，等待 Redis 恢复后重新抢锁；
//   - true：降级为单实例模式继续调度（多实例同时失联时可能重复执行）。
#include <memory>
#include <string>

namespace cm::cluster {

struct LeaderOptions {
  bool enabled = true;
  std::string key = "car-monit:leader";
  int ttl_ms = 30000;
  int renew_ms = 10000;
  bool fail_open = false;
};

class LeaderElector {
public:
  LeaderElector();
  ~LeaderElector();
  LeaderElector(const LeaderElector&) = delete;
  LeaderElector& operator=(const LeaderElector&) = delete;

  static LeaderElector& instance();

  // 同步尝试抢锁并启动续期线程；返回后可通过 is_leader() 判断当前状态。
  // owner 为空时自动生成（pid + 随机数），用于防止误删他实例的锁。
  void start(const LeaderOptions& options, const std::string& owner = "");
  // 停止续期线程并释放自己的锁（仅当锁仍属于本实例）。
  void stop();

  bool is_leader() const;
  bool enabled() const;

private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace cm::cluster
