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

} // namespace

void set_level(Level level) { g_level = level; }
Level level() { return g_level; }

void set_file(const std::string& path) {
  std::lock_guard<std::mutex> lock(g_mutex);
  try {
    std::filesystem::path p(path);
    if (p.has_parent_path()) std::filesystem::create_directories(p.parent_path());
  } catch (...) {
  }
  g_file.open(path, std::ios::app);
  g_file_open = g_file.is_open();
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
  }
}

} // namespace cm::log
