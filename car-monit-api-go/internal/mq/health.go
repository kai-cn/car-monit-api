package mq

// 消费端心跳 —— 让 /readyz 能发现"消费循环还活着但已经不再前进"的假死。
//
// 背景（报告 02 R2）：旧实现里 main() 在 consumer.Start() 返回后立即把
// consumerUp 置 true，此后消费循环无论卡死、崩溃还是 broker 不可达，探针都永远 UP。
// 这里把"健康"定义成三个可观测事实的组合：
//  1. 消费循环至少启动过（registered）；
//  2. 循环当前仍在跑（running，退出/panic 后置 false）；
//  3. 心跳新鲜（lastTick 在 HeartbeatStaleAfter 内）且没有连续拉取失败。
//
// 心跳在两种时机刷新：成功拉到消息、以及 FetchMessage 按预期超时空转（空闲 topic）。
// 这样"没有消息"不会被误判为不健康，而"卡在处理里"会。

import (
	"sync"
	"time"
)

// HeartbeatStaleAfter 是心跳过期阈值。
//
// FetchMessage 的空闲超时是 1s，正常循环每秒至少刷新一次；超过 45s 没有任何刷新，
// 只可能是卡在 handler（DB/ES 无响应）或进程被挂起 —— 两种情况都应让探针转 DOWN。
const HeartbeatStaleAfter = 45 * time.Second

// maxConsecutiveFetchErrors 连续拉取失败达到该次数即判定不健康（默认 broker 不可达）。
const maxConsecutiveFetchErrors = 3

// Heartbeat 是并发安全的心跳记录器（消费循环写、探针读）。
type Heartbeat struct {
	mu                sync.Mutex
	registered        bool
	running           bool
	lastTick          time.Time
	consecutiveErrors int
	lastErr           string
}

// NewHeartbeat 构造心跳记录器。
func NewHeartbeat() *Heartbeat { return &Heartbeat{} }

// markRunning 在消费循环开始时调用。
func (h *Heartbeat) markRunning() {
	if h == nil {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	h.registered = true
	h.running = true
	h.lastTick = time.Now()
	h.consecutiveErrors = 0
	h.lastErr = ""
}

// tick 表示"循环前进了一步"（拉到消息、或按预期空闲超时）。
func (h *Heartbeat) tick() {
	if h == nil {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	h.lastTick = time.Now()
	h.consecutiveErrors = 0
	h.lastErr = ""
}

// fail 记录一次非预期失败（不刷新 lastTick，连续失败会累积）。
func (h *Heartbeat) fail(err error) {
	if h == nil {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	h.consecutiveErrors++
	if err != nil {
		h.lastErr = err.Error()
	}
}

// stop 在消费循环退出（正常退出、错误退出或 panic）时调用。
func (h *Heartbeat) stop() {
	if h == nil {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	h.running = false
}

// Healthy 返回消费端当前是否健康。
//
// PARITY/DIFF: 这是 Go 侧新增的探针语义，Java 侧由 MQ 客户端容器的
// "consumer is connected" 状态间接表达；本项目的 consumerUp 之前是常量 true。
func (h *Heartbeat) Healthy() bool {
	if h == nil {
		return false
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	if !h.registered || !h.running {
		return false
	}
	if h.consecutiveErrors >= maxConsecutiveFetchErrors {
		return false
	}
	return time.Since(h.lastTick) <= HeartbeatStaleAfter
}

// Snapshot 返回一份只读快照，供 /readyz 的 detail 与指标导出使用。
//
// 返回：registered（是否启动过）、running（是否仍在跑）、lastTick（最后心跳时间）、
// consecutiveErrors（连续失败次数）、lastErr（最近一次失败原因）。
func (h *Heartbeat) Snapshot() (registered, running bool, lastTick time.Time, consecutiveErrors int, lastErr string) {
	if h == nil {
		return false, false, time.Time{}, 0, ""
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	return h.registered, h.running, h.lastTick, h.consecutiveErrors, h.lastErr
}
