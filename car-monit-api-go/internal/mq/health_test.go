package mq

// 消费端心跳的回归护栏（R2）：未启动 / 退出 / 连续拉取失败 / 心跳过期 都必须判定为不健康。

import (
	"errors"
	"testing"
	"time"
)

func TestHeartbeatLifecycle(t *testing.T) {
	h := NewHeartbeat()

	if h.Healthy() {
		t.Fatal("未启动时不应判定健康")
	}

	h.markRunning()
	if !h.Healthy() {
		t.Fatal("启动后应立即健康")
	}

	h.stop()
	if h.Healthy() {
		t.Fatal("退出后不应判定健康")
	}
}

func TestHeartbeatConsecutiveFailures(t *testing.T) {
	h := NewHeartbeat()
	h.markRunning()

	// 未达阈值仍健康（容忍偶发失败）。
	h.fail(errors.New("boom"))
	h.fail(errors.New("boom"))
	if !h.Healthy() {
		t.Fatal("连续失败 2 次不应判定不健康")
	}

	h.fail(errors.New("boom"))
	if h.Healthy() {
		t.Fatal("连续失败达到阈值必须判定不健康")
	}

	// 一次成功 tick 立即恢复。
	h.tick()
	if !h.Healthy() {
		t.Fatal("成功 tick 后应恢复健康")
	}
}

func TestHeartbeatStale(t *testing.T) {
	h := NewHeartbeat()
	h.markRunning()

	// 直接改 lastTick 模拟"卡在 handler 里 46 秒"。
	h.mu.Lock()
	h.lastTick = time.Now().Add(-(HeartbeatStaleAfter + time.Second))
	h.mu.Unlock()

	if h.Healthy() {
		t.Fatalf("心跳超过 %v 未刷新必须判定不健康", HeartbeatStaleAfter)
	}

	h.tick()
	if !h.Healthy() {
		t.Fatal("心跳刷新后应恢复健康")
	}
}

func TestHeartbeatSnapshot(t *testing.T) {
	h := NewHeartbeat()
	h.markRunning()
	h.fail(errors.New("kafka: connection refused"))

	registered, running, lastTick, errs, lastErr := h.Snapshot()
	if !registered || !running {
		t.Fatalf("快照应为已登记且运行中，实际 registered=%v running=%v", registered, running)
	}
	if lastTick.IsZero() {
		t.Fatal("快照的 lastTick 不应为零值")
	}
	if errs != 1 || lastErr == "" {
		t.Fatalf("连续失败计数/错误信息不符：errs=%d lastErr=%q", errs, lastErr)
	}
}
