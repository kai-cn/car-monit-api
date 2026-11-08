#include "cluster/leader.h"

#include "cache/redis.h"
#include "common/logging.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <exception>
#include <random>
#include <string>
#include <thread>

#ifdef _WIN32
#include <process.h>
#else
#include <unistd.h>
#endif

namespace cm::cluster {
namespace {

// 续期/释放必须"先比对 owner 再操作"，避免锁过期后被其他实例抢到又被误删。
const char* kRenewScript =
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('pexpire', KEYS[1], ARGV[2]) else return 0 end";
const char* kReleaseScript =
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end";

long current_pid() {
#ifdef _WIN32
  return static_cast<long>(_getpid());
#else
  return static_cast<long>(::getpid());
#endif
}

std::string make_owner() {
  std::random_device rd;
  const std::uint64_t salt = static_cast<std::uint64_t>(rd()) << 32 | rd();
  return std::to_string(current_pid()) + "-" + std::to_string(salt);
}

enum class AcquireResult { Acquired, Held, Unavailable };
enum class RenewResult { Renewed, Lost, Unavailable };

} // namespace

struct LeaderElector::Impl {
  std::atomic<bool> running{false};
  std::atomic<bool> leader{false};
  std::atomic<bool> enabled{false};
  std::atomic<bool> fail_open{false};

  std::string key;
  std::string owner;
  int ttl_ms = 30000;
  int renew_ms = 10000;
  std::thread thread;

  AcquireResult try_acquire() {
    try {
      auto reply = cache::Redis::instance().cmd(
          {"SET", key, owner, "NX", "PX", std::to_string(ttl_ms)});
      if (reply && *reply == "OK") return AcquireResult::Acquired;
      return AcquireResult::Held; // nil = 已被其他实例持有
    } catch (const std::exception&) {
      return AcquireResult::Unavailable;
    }
  }

  RenewResult renew() {
    try {
      auto reply = cache::Redis::instance().cmd(
          {"EVAL", kRenewScript, "1", key, owner, std::to_string(ttl_ms)});
      if (!reply) return RenewResult::Lost;
      return *reply == "1" ? RenewResult::Renewed : RenewResult::Lost;
    } catch (const std::exception&) {
      return RenewResult::Unavailable;
    }
  }

  void release() {
    try {
      cache::Redis::instance().cmd({"EVAL", kReleaseScript, "1", key, owner});
    } catch (const std::exception&) {
      // 释放失败不阻塞停机：锁会在 TTL 后自动过期。
    }
  }

  bool sleep_while_running(int ms) {
    for (int waited = 0; waited < ms && running.load(); waited += 100) {
      std::this_thread::sleep_for(std::chrono::milliseconds(std::min(100, ms - waited)));
    }
    return running.load();
  }

  void leader_loop() {
    while (sleep_while_running(renew_ms)) {
      if (leader.load()) {
        const RenewResult r = renew();
        if (r == RenewResult::Lost) {
          leader.store(false);
          CM_LOG_WARN("cluster") << "分布式锁已失效/被接管，停止调度与同步: key=" << key;
        } else if (r == RenewResult::Unavailable && !fail_open.load()) {
          leader.store(false);
          CM_LOG_ERROR("cluster")
              << "Redis 不可用，fail-closed：暂停调度与同步（HTTP 继续服务）: key=" << key;
        }
        continue;
      }
      if (try_acquire() == AcquireResult::Acquired) {
        leader.store(true);
        CM_LOG_INFO("cluster") << "已接管分布式锁，开始执行调度与同步: key=" << key
                               << ", owner=" << owner;
      }
    }
  }
};

LeaderElector::LeaderElector() : impl_(std::make_unique<Impl>()) {}
LeaderElector::~LeaderElector() { stop(); }

LeaderElector& LeaderElector::instance() {
  static LeaderElector elector;
  return elector;
}

void LeaderElector::start(const LeaderOptions& options, const std::string& owner) {
  stop();
  auto& d = *impl_;
  d.enabled.store(options.enabled);
  if (!options.enabled) {
    d.leader.store(true);
    CM_LOG_INFO("cluster") << "Leader 选举未启用：按单实例模式运行，调度与同步照常执行";
    return;
  }

  d.key = options.key.empty() ? "car-monit:leader" : options.key;
  d.ttl_ms = std::max(1000, options.ttl_ms);
  d.renew_ms = std::max(200, options.renew_ms);
  if (d.renew_ms >= d.ttl_ms) d.renew_ms = d.ttl_ms / 2;
  d.fail_open.store(options.fail_open);
  d.owner = owner.empty() ? make_owner() : owner;
  d.running.store(true);

  const AcquireResult initial = d.try_acquire();
  if (initial == AcquireResult::Acquired) {
    d.leader.store(true);
    CM_LOG_INFO("cluster") << "已获得分布式锁: key=" << d.key << ", owner=" << d.owner
                           << ", ttl-ms=" << d.ttl_ms;
  } else if (initial == AcquireResult::Held) {
    d.leader.store(false);
    CM_LOG_INFO("cluster") << "分布式锁被其他实例持有，当前实例降级为只读（不执行调度/同步）";
  } else if (d.fail_open.load()) {
    d.leader.store(true);
    CM_LOG_WARN("cluster") << "Redis 不可用，fail-open：降级为单实例调度（多实例下可能重复执行）";
  } else {
    d.leader.store(false);
    CM_LOG_ERROR("cluster")
        << "Redis 不可用，fail-closed：暂停调度与同步（HTTP 继续服务），等待 Redis 恢复";
  }

  d.thread = std::thread([&d] { d.leader_loop(); });
}

void LeaderElector::stop() {
  auto& d = *impl_;
  const bool was_running = d.running.exchange(false);
  if (was_running && d.thread.joinable()) d.thread.join();
  if (was_running && d.enabled.load() && !d.owner.empty()) d.release();
  d.leader.store(false);
}

bool LeaderElector::is_leader() const { return impl_->leader.load(); }

bool LeaderElector::enabled() const { return impl_->enabled.load(); }

} // namespace cm::cluster
