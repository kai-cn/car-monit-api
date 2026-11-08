#include "handler/handlers.h"

#include "common/datetime.h"
#include "common/logging.h"
#include "common/worker_pool.h"
#include "cluster/leader.h"
#include "config/config.h"
#include "scheduler/cron.h"
#include "service/ops.h"

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace cm::service {
// 由 service/track.cpp 实现（1:1 对应 TrackTask / DataFlowTask）。
void sync_base_info();
void sync_current_track();
void sync_histroy_track();
void process_pending_queue();
void sync_gantry_capture_data();
void sync_ods_szdn_gantry();
} // namespace cm::service

namespace cm::handler {
namespace {

using Clock = std::chrono::steady_clock;

// Spring cron 使用 JVM 默认时区（+08:00）解释时间。
scheduler::WallTime wall_now() {
  auto tp = timeutil::now() + std::chrono::minutes(timeutil::kJavaZoneOffsetMinutes);
  std::time_t t = std::time_t(timeutil::to_millis(tp) / 1000);
  std::tm tm{};
#ifdef _WIN32
  gmtime_s(&tm, &t);
#else
  gmtime_r(&t, &tm);
#endif
  scheduler::WallTime w;
  w.year = tm.tm_year + 1900;
  w.month = tm.tm_mon + 1;
  w.day = tm.tm_mday;
  w.hour = tm.tm_hour;
  w.minute = tm.tm_min;
  w.second = tm.tm_sec;
  w.wday = tm.tm_wday; // 0=Sunday（cron_match 内部转 Spring 1-7 口径）
  return w;
}

struct Job {
  std::string name;
  bool fixed_rate = false;
  long long interval_ms = 0;
  std::string cron;
  std::function<void()> fn;
  long long next_due_ms = 0;   // steady_clock 毫秒（fixedRate）
  long long last_match = -1;   // 上一次 cron 触发的秒（避免同一秒重复）
  std::atomic<bool> running{false};
};

long long steady_now_ms() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now().time_since_epoch())
      .count();
}

// 调度任务执行池（Java ThreadPoolTaskScheduler 默认单线程的受控等价物；
// 2 worker + 每任务原子防重入）。优雅停机时由 stop_schedulers() join 回收，
// 替代原先的 detached 线程（审阅 §5.1 #11）。
cm::WorkerPool& sched_pool() {
  static cm::WorkerPool pool(2, 64);
  return pool;
}

void launch(const std::shared_ptr<Job>& job) {
  if (job->running.exchange(true)) return;
  if (!sched_pool().submit([job]() {
        try {
          job->fn();
        } catch (const std::exception& e) {
          CM_LOG_ERROR("scheduler") << "任务执行异常: " << job->name << ": " << e.what();
        } catch (...) {
          CM_LOG_ERROR("scheduler") << "任务执行异常: " << job->name << ": <unknown>";
        }
        job->running = false;
      })) {
    // 池满：本轮放弃（不视为任务失败），下个触发周期自然重试。
    job->running = false;
    CM_LOG_WARN("scheduler") << "调度任务队列已满，本轮跳过: " << job->name;
  }
}

// 优雅停机状态：调度循环线程与执行池都可停止并 join。
std::atomic<bool> g_running{true};
std::thread g_loop;

} // namespace

void start_schedulers() {
  if (g_loop.joinable()) return; // 已在运行，幂等
  auto& cfg = config::Config::instance();
  std::vector<std::shared_ptr<Job>> jobs;

  auto add_cron = [&](const std::string& name, const std::string& expr,
                      std::function<void()> fn) {
    // 非法表达式在 Spring 侧会导致启动失败；这里告警并保留任务（永不触发）。
    if (!scheduler::cron_validate(expr)) {
      CM_LOG_WARN("scheduler") << "cron 表达式不合法（任务将永不触发）: " << name << " -> "
                                << expr << "（Spring 要求恰好 6 个字段：秒 分 时 日 月 周）";
    }
    auto job = std::make_shared<Job>();
    job->name = name;
    job->cron = expr;
    job->fn = std::move(fn);
    jobs.push_back(std::move(job));
  };
  auto add_fixed = [&](const std::string& name, long long interval_ms, std::function<void()> fn) {
    auto job = std::make_shared<Job>();
    job->name = name;
    job->fixed_rate = true;
    job->interval_ms = interval_ms > 0 ? interval_ms : 60000;
    job->next_due_ms = steady_now_ms(); // Spring fixedRate 首次立即执行
    job->fn = std::move(fn);
    jobs.push_back(std::move(job));
  };

  // ---- TrackTask ----
  add_cron("syncBaseInfo", "0 0 0 * * ?", [] { service::sync_base_info(); });
  add_cron("syncCurrentTrack", "0 0/3 * * * ?", [] { service::sync_current_track(); });
  add_cron("syncHistroyTrack", "0 0 4 * * ?", [] { service::sync_histroy_track(); });
  // ---- DataFlowTask ----
  add_cron("processPendingQueue", "0 */1 * * * ?", [] { service::process_pending_queue(); });
  add_cron("syncGantryCaptureData", "0 */5 * * * ?", [] { service::sync_gantry_capture_data(); });
  // ---- 可靠性/监控 ----
  // Java: @Scheduled(fixedRateString = "${detection.interval-minutes:30}000") ——
  // 占位符展开后与字面量 "000" 拼接，默认 30 -> "30000"ms = 30 秒（配置键名叫
  // minutes，实际语义是秒）。这里乘 1000 复刻该行为，修复原先 *60000（30 分钟）
  // 导致丢失检测周期放大 60 倍的问题（审阅报告 §3.3 R5）。
  add_fixed("dataLossDetection", static_cast<long long>(cfg.detection.interval_minutes) * 1000LL,
            [] { service::ops::data_loss_detection_tick(); });
  add_fixed("reliabilityCompensation",
            static_cast<long long>(cfg.reliability.compensation_interval_seconds) * 1000LL,
            [] { service::ops::reliability_compensation_tick(); });
  add_fixed("checkOfflineDevices", 300000LL, [] { service::ops::device_offline_check_tick(); });
  add_fixed("delayStatsReport", 600000LL, [] { service::ops::delay_stats_report_tick(); });
  // ---- GaussDB ↔ ES 对账（默认关闭） ----
  add_cron("gaussEsConsistency", cfg.consistency.cron,
           [] { service::ops::gauss_es_consistency_tick(); });

  g_running.store(true);
  g_loop = std::thread([jobs = std::move(jobs)]() mutable {
    CM_LOG_INFO("scheduler") << "定时任务调度线程启动，任务数=" << jobs.size();
    while (g_running.load()) {
      const long long now = steady_now_ms();
      const scheduler::WallTime w = wall_now();
      const long long sec = timeutil::to_millis(timeutil::now()) / 1000;
      // 多实例单活：非 leader 只推进时间游标、不执行任务，避免多实例重复触发。
      const bool leader = cluster::LeaderElector::instance().is_leader();
      for (auto& j : jobs) {
        if (j->fixed_rate) {
          if (now >= j->next_due_ms) {
            if (leader) launch(j);
            j->next_due_ms = now + j->interval_ms;
          }
        } else if (j->last_match != sec && scheduler::cron_match(j->cron, w)) {
          j->last_match = sec;
          if (leader) launch(j);
        }
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
    CM_LOG_INFO("scheduler") << "定时任务调度线程已停止";
  });
  // 不再 detach：由 stop_schedulers() 停止并 join（优雅停机）。
}

void stop_schedulers() {
  if (!g_running.exchange(false)) return; // 未启动或已停止：幂等 no-op
  if (g_loop.joinable()) g_loop.join();
  sched_pool().shutdown();
}

} // namespace cm::handler
