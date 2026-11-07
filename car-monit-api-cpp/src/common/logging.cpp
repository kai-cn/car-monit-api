#include "common/logging.h"

#include "common/datetime.h"

#include <cstdio>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <thread>

namespace cm::log {
namespace {

std::mutex g_mutex;
Level g_level = Level::Info;
std::ofstream g_file;
bool g_file_open = false;
std::string g_path;
// 按大小轮转（审阅 §4.1：原实现文件无限增长，磁盘写满导致进程异常）。
long long g_max_bytes = 50LL * 1024 * 1024; // 0 = 不轮转
int g_keep_files = 5;
long long g_written = 0;

char level_char(Level l) {
  switch (l) {
    case Level::Trace: return 'T';
    case Level::Debug: return 'D';
    case Level::Info: return 'I';
    case Level::Warn: return 'W';
    case Level::Error: return 'E';
  }
  return 'I';
}

// 关闭当前文件并把 log -> log.1 -> log.2 ... 链式重命名，超出保留数的删除。
void rotate_locked() {
  if (!g_file_open) return;
  g_file.close();
  g_file_open = false;
  if (g_path.empty() || g_keep_files <= 0) return;
  namespace fs = std::filesystem;
  try {
    fs::path oldest = fs::path(g_path).parent_path() /
                      (fs::path(g_path).filename().string() + "." + std::to_string(g_keep_files));
    std::error_code ec;
    if (fs::exists(oldest)) fs::remove(oldest, ec);
    for (int i = g_keep_files - 1; i >= 1; --i) {
      fs::path from = fs::path(g_path).parent_path() /
                      (fs::path(g_path).filename().string() + "." + std::to_string(i));
      fs::path to = fs::path(g_path).parent_path() /
                    (fs::path(g_path).filename().string() + "." + std::to_string(i + 1));
      if (fs::exists(from)) fs::rename(from, to, ec);
    }
    fs::path first = fs::path(g_path).parent_path() /
                     (fs::path(g_path).filename().string() + ".1");
    fs::rename(g_path, first, ec);
  } catch (...) {
    // 轮转失败不影响主流程：重新以追加模式打开原文件继续写。
  }
  g_file.open(g_path, std::ios::app);
  g_file_open = g_file.is_open();
  g_written = 0;
}

} // namespace

void set_level(Level level) { g_level = level; }
Level level() { return g_level; }

void set_rotation(long long max_bytes, int keep_files) {
  std::lock_guard<std::mutex> lock(g_mutex);
  g_max_bytes = max_bytes > 0 ? max_bytes : 0; // 0 = 关闭轮转
  g_keep_files = keep_files > 0 ? keep_files : 1;
}

void set_file(const std::string& path) {
  std::lock_guard<std::mutex> lock(g_mutex);
  try {
    std::filesystem::path p(path);
    if (p.has_parent_path()) std::filesystem::create_directories(p.parent_path());
  } catch (...) {
  }
  if (g_file_open) g_file.close();
  g_path = path;
  g_file.open(path, std::ios::app);
  g_file_open = g_file.is_open();
  try {
    g_written = g_file_open ? static_cast<long long>(std::filesystem::file_size(path)) : 0;
  } catch (...) {
    g_written = 0;
  }
}

std::string thread_name() {
  return std::to_string(std::hash<std::thread::id>{}(std::this_thread::get_id()) % 100000);
}

void write(Level lvl, const std::string& logger, const std::string& msg) {
  if (static_cast<int>(lvl) < static_cast<int>(g_level)) return;
  std::string stamp = timeutil::format_naive_plus8(timeutil::now());
  std::string millis_stamp;
  {
    using namespace std::chrono;
    auto now = system_clock::now().time_since_epoch();
    long long ms = duration_cast<milliseconds>(now).count();
    long long tod = ms % 1000;
    char buf[8];
    std::snprintf(buf, sizeof(buf), "%03lld", tod);
    millis_stamp = stamp + "." + buf;
  }
  std::string line = millis_stamp + " [" + thread_name() + "] " +
                     std::string(1, level_char(lvl)) +
                     "     " + logger + " - " + msg + "\n";
  std::lock_guard<std::mutex> lock(g_mutex);
  std::fputs(line.c_str(), stdout);
  std::fflush(stdout);
  if (g_file_open) {
    g_file << line;
    g_file.flush();
    g_written += static_cast<long long>(line.size());
    if (g_max_bytes > 0 && g_written >= g_max_bytes) rotate_locked();
  }
}

} // namespace cm::log
