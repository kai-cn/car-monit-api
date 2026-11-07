#include "handler/handlers.h"

#include "common/datetime.h"
#include "common/logging.h"
#include "config/config.h"
#include "service/ops.h"

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <functional>
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

struct WallClock {
  int year = 1970, month = 1, day = 1, hour = 0, minute = 0, second = 0, wday = 0;
};

// Quartz cron 使用 JVM 默认时区（+08:00）解释时间。
WallClock wall_now() {
  auto tp = timeutil::now() + std::chrono::minutes(timeutil::kJavaZoneOffsetMinutes);
  std::time_t t = std::time_t(timeutil::to_millis(tp) / 1000);
  std::tm tm{};
#ifdef _WIN32
  gmtime_s(&tm, &t);
#else
  gmtime_r(&t, &tm);
#endif
  WallClock w;
  w.year = tm.tm_year + 1900;
  w.month = tm.tm_mon + 1;
  w.day = tm.tm_mday;
  w.hour = tm.tm_hour;
  w.minute = tm.tm_min;
  w.second = tm.tm_sec;
  w.wday = tm.tm_wday; // 0=Sunday
  return w;
}

bool match_token(const std::string& tok, int v, int lo) {
  if (tok == "*" || tok == "?") return true;
  auto slash = tok.find('/');
  int step = 1, base = lo;
  std::string head = tok;
  if (slash != std::string::npos) {
    head = tok.substr(0, slash);
    step = std::atoi(tok.substr(slash + 1).c_str());
    if (step <= 0) step = 1;
  }
  if (head == "*" || head == "?") {
    // 通配 + 步长
    return (v - base) % step == 0;
  }
  auto dash = head.find('-');
  if (dash != std::string::npos) {
    int a = std::atoi(head.substr(0, dash).c_str());
    int b = std::atoi(head.substr(dash + 1).c_str());
    return v >= a && v <= b && (v - a) % step == 0;
  }
  return v == std::atoi(head.c_str());
}

bool match_field(const std::string& field, int v, int lo) {
  // 逗号分隔的多值
  std::size_t start = 0;
  while (start <= field.size()) {
    auto pos = field.find(',', start);
    std::string tok = field.substr(start, pos == std::string::npos ? std::string::npos : pos - start);
    if (match_token(tok, v, lo)) return true;
    if (pos == std::string::npos) break;
    start = pos + 1;
  }
  return false;
}

// Quartz 六段/七段 cron：秒 分 时 日 月 周 [年]
bool cron_match(const std::string& expr, const WallClock& w) {
  std::vector<std::string> f;
  std::size_t start = 0;
  while (start <= expr.size()) {
    auto pos = expr.find(' ', start);
    std::string tok = expr.substr(start, pos == std::string::npos ? std::string::npos : pos - start);
    if (!tok.empty()) f.push_back(tok);
    if (pos == std::string::npos) break;
    start = pos + 1;
  }
  if (f.size() < 6) return false;
  int dow = w.wday; // Quartz: 0/7=Sunday ... 6=Saturday，与 tm_wday 一致
  return match_field(f[0], w.second, 0) && match_field(f[1], w.minute, 0) &&
         match_field(f[2], w.hour, 0) && match_field(f[3], w.day, 1) &&
         match_field(f[4], w.month, 1) && match_field(f[5], dow, 0);
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

void launch(Job& job) {
  if (job.running.exchange(true)) return;
  std::thread worker([&job]() {
    try {
      job.fn();
    } catch (const std::exception& e) {
      CM_LOG_ERROR("scheduler") << "任务执行异常: " << job.name << ": " << e.what();
    } catch (...) {
      CM_LOG_ERROR("scheduler") << "任务执行异常: " << job.name << ": <unknown>";
    }
    job.running = false;
  });
  worker.detach();
}

} // namespace

void start_schedulers() {
  auto& cfg = config::Config::instance();
  std::vector<std::unique_ptr<Job>> jobs;

  auto add_cron = [&](const std::string& name, const std::string& expr,
                      std::function<void()> fn) {
    auto job = std::make_unique<Job>();
    job->name = name;
    job->cron = expr;
    job->fn = std::move(fn);
    jobs.push_back(std::move(job));
  };
  auto add_fixed = [&](const std::string& name, long long interval_ms, std::function<void()> fn) {
    auto job = std::make_unique<Job>();
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
  add_fixed("dataLossDetection", static_cast<long long>(cfg.detection.interval_minutes) * 60000LL,
            [] { service::ops::data_loss_detection_tick(); });
  add_fixed("reliabilityCompensation",
            static_cast<long long>(cfg.reliability.compensation_interval_seconds) * 1000LL,
            [] { service::ops::reliability_compensation_tick(); });
  add_fixed("checkOfflineDevices", 300000LL, [] { service::ops::device_offline_check_tick(); });
  add_fixed("delayStatsReport", 600000LL, [] { service::ops::delay_stats_report_tick(); });
  // ---- GaussDB ↔ ES 对账（默认关闭） ----
  add_cron("gaussEsConsistency", cfg.consistency.cron,
           [] { service::ops::gauss_es_consistency_tick(); });

  std::thread loop([jobs = std::move(jobs)]() mutable {
    CM_LOG_INFO("scheduler") << "定时任务调度线程启动，任务数=" << jobs.size();
    while (true) {
      const long long now = steady_now_ms();
      const WallClock w = wall_now();
      const long long sec = timeutil::to_millis(timeutil::now()) / 1000;
      for (auto& j : jobs) {
        if (j->fixed_rate) {
          if (now >= j->next_due_ms) {
            launch(*j);
            j->next_due_ms = now + j->interval_ms;
          }
        } else if (j->last_match != sec && cron_match(j->cron, w)) {
          j->last_match = sec;
          launch(*j);
        }
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
  });
  loop.detach();
}

} // namespace cm::handler
