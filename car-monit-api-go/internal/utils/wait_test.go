package utils

import (
	"sync/atomic"
	"testing"
	"time"
)

func TestWaitTimeoutReturnsTrueWhenDone(t *testing.T) {
	var ran atomic.Bool
	if !WaitTimeout(time.Second, func() { ran.Store(true) }) {
		t.Fatal("fn 立即返回时应判定为已完成")
	}
	if !ran.Load() {
		t.Fatal("fn 未被执行")
	}
}

func TestWaitTimeoutReturnsFalseOnTimeout(t *testing.T) {
	start := time.Now()
	if WaitTimeout(20*time.Millisecond, func() { time.Sleep(500 * time.Millisecond) }) {
		t.Fatal("fn 超过超时时间时应返回 false")
	}
	if elapsed := time.Since(start); elapsed > 300*time.Millisecond {
		t.Fatalf("等待超时未生效，耗时 %v", elapsed)
	}
}

func TestWaitTimeoutNonPositive(t *testing.T) {
	if WaitTimeout(0, func() { time.Sleep(time.Second) }) {
		t.Fatal("d<=0 时应立即返回 false")
	}
	if !WaitTimeout(0, nil) {
		t.Fatal("fn 为 nil 时应视为已完成")
	}
}
