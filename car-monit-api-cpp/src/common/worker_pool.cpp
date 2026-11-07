#include "common/worker_pool.h"

#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>
#include <vector>

namespace cm {

struct WorkerPool::Impl {
  std::mutex mu;
  std::condition_variable cv_work;   // worker 等待新任务
  std::condition_variable cv_space;  // shutdown 时确认排空（可选）
  std::deque<std::function<void()>> queue;
  std::vector<std::thread> workers;
  int capacity = 128;
  bool stopped = false;

  void worker_loop() {
    while (true) {
      std::function<void()> task;
      {
        std::unique_lock<std::mutex> lock(mu);
        cv_work.wait(lock, [&] { return stopped || !queue.empty(); });
        if (queue.empty()) return; // stopped 且队列已排空
        task = std::move(queue.front());
        queue.pop_front();
      }
      task(); // 异常由任务自身负责（与 Java 线程池的 worker 捕获语义一致）
    }
  }
};

WorkerPool::WorkerPool(int workers, int queue_capacity) : impl_(new Impl) {
  impl_->capacity = queue_capacity > 0 ? queue_capacity : 1;
  const int n = workers > 0 ? workers : 1;
  impl_->workers.reserve(std::size_t(n));
  for (int i = 0; i < n; ++i) {
    impl_->workers.emplace_back([this] { impl_->worker_loop(); });
  }
}

WorkerPool::~WorkerPool() {
  shutdown();
  delete impl_;
}

bool WorkerPool::submit(std::function<void()> task) {
  {
    std::lock_guard<std::mutex> lock(impl_->mu);
    if (impl_->stopped) return false;
    if (int(impl_->queue.size()) >= impl_->capacity) return false;
    impl_->queue.push_back(std::move(task));
  }
  impl_->cv_work.notify_one();
  return true;
}

void WorkerPool::shutdown() {
  {
    std::lock_guard<std::mutex> lock(impl_->mu);
    if (impl_->stopped) return;
    impl_->stopped = true;
  }
  impl_->cv_work.notify_all();
  for (auto& t : impl_->workers) {
    if (t.joinable()) t.join();
  }
}

WorkerPool& background_pool() {
  // 4 worker / 128 队列：与 Java 侧导出/同步固定线程池的量级一致；
  // 超出即快速失败（error_body 503），避免无界积压。
  static WorkerPool pool(4, 128);
  return pool;
}

} // namespace cm
