#pragma once
// 固定大小后台工作线程池（有界队列）。
//
// 用途：替代"每请求 std::thread(...).detach()"的无界线程创建（审阅 §4.2 #15）：
// 导出/全量同步/修复同步接口被反复调用时会线程爆炸，且 detached 线程在进程
// 退出时不被等待。Java 侧这些操作跑在固定大小的线程池上，这里对齐该模型，
// 并把队列做成有界——满时 submit 返回 false，调用方立即返回错误而不是无限积压。
#include <functional>

namespace cm {

class WorkerPool {
public:
  // workers：常驻工作线程数；queue_capacity：待执行任务上限。
  WorkerPool(int workers, int queue_capacity);
  ~WorkerPool();
  WorkerPool(const WorkerPool&) = delete;
  WorkerPool& operator=(const WorkerPool&) = delete;

  // 队列已满或已 shutdown 时返回 false。
  bool submit(std::function<void()> task);

  // 运行指标（/metrics）：待执行队列深度、正在执行的任务数、队列容量。
  std::size_t pending() const;
  int active() const;
  int capacity() const;

  // 停止接收新任务，等待队列中与正在执行的任务全部结束后 join 全部 worker。
  void shutdown();

private:
  struct Impl;
  Impl* impl_;
};

// 进程级后台池：导出任务 / 全量与修复同步（4 worker / 128 队列深度）。
WorkerPool& background_pool();

} // namespace cm
