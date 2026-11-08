package scheduler

// 分布式租约锁与调度编排的回归护栏（报告 02 R5 / 多副本安全）。
//
// 不依赖 Redis：用内存版 fakeLocker 验证"抢到才执行、抢不到跳过、
// 后端错误按跳过处理、释放只发生一次"这四条语义。

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// fakeLocker 是 Locker 的内存实现，用于验证调度器的编排逻辑。
type fakeLocker struct {
	mu       sync.Mutex
	held     map[string]bool
	failWith error
	acquires int
	releases int
}

func newFakeLocker() *fakeLocker { return &fakeLocker{held: map[string]bool{}} }

func (f *fakeLocker) TryLock(_ context.Context, key string, _ time.Duration) (func(), bool, error) {
	if f.failWith != nil {
		return nil, false, f.failWith
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.held[key] {
		return nil, false, nil
	}
	f.held[key] = true
	f.acquires++
	return func() {
		f.mu.Lock()
		defer f.mu.Unlock()
		if f.held[key] {
			delete(f.held, key)
			f.releases++
		}
	}, true, nil
}

func TestSchedulerRunsJobWhenLockAcquired(t *testing.T) {
	var ran atomic.Int32
	lk := newFakeLocker()
	s := New(time.Local)
	s.SetLocker(lk, time.Minute)

	job := &Job{Name: "jobA", Spec: "* * * * *", Fn: func(context.Context) { ran.Add(1) }}
	s.run(context.Background(), job)

	if ran.Load() != 1 {
		t.Fatalf("抢到锁后应执行 1 次，实际 %d", ran.Load())
	}
	if lk.releases != 1 {
		t.Fatalf("执行后必须释放租约，实际释放 %d 次", lk.releases)
	}
}

func TestSchedulerSkipsJobWhenLockHeld(t *testing.T) {
	var ran atomic.Int32
	lk := newFakeLocker()
	lk.held["jobB"] = true // 模拟"另一个副本正在跑"
	s := New(time.Local)
	s.SetLocker(lk, time.Minute)

	job := &Job{Name: "jobB", Spec: "* * * * *", Fn: func(context.Context) { ran.Add(1) }}
	s.run(context.Background(), job)

	if ran.Load() != 0 {
		t.Fatalf("锁被其他副本持有时不应执行，实际执行 %d 次", ran.Load())
	}
}

func TestSchedulerSkipsOnLockerError(t *testing.T) {
	var ran atomic.Int32
	lk := newFakeLocker()
	lk.failWith = errors.New("redis down")
	s := New(time.Local)
	s.SetLocker(lk, time.Minute)

	job := &Job{Name: "jobC", Spec: "* * * * *", Fn: func(context.Context) { ran.Add(1) }}
	s.run(context.Background(), job)

	if ran.Load() != 0 {
		t.Fatalf("锁后端不可用时应跳过执行（宁可漏跑不重复跑），实际执行 %d 次", ran.Load())
	}
}

// TestSchedulerWithoutLockerRuns 锁未启用时（默认单副本形态）必须直接执行。
func TestSchedulerWithoutLockerRuns(t *testing.T) {
	var ran atomic.Int32
	s := New(time.Local)
	job := &Job{Name: "jobD", Spec: "* * * * *", Fn: func(context.Context) { ran.Add(1) }}
	s.run(context.Background(), job)
	if ran.Load() != 1 {
		t.Fatalf("未启用锁时应直接执行，实际 %d", ran.Load())
	}
}

// TestSchedulerReleaseIsIdempotent 幂等释放：重复调用 release 不应重复释放租约。
func TestSchedulerReleaseIsIdempotent(t *testing.T) {
	lk := newFakeLocker()
	s := New(time.Local)
	s.SetLocker(lk, time.Minute)

	job := &Job{Name: "jobE", Spec: "* * * * *", Fn: func(context.Context) {}}
	s.run(context.Background(), job)
	if lk.releases != 1 {
		t.Fatalf("一次执行应只释放一次，实际 %d", lk.releases)
	}
	if lk.held["jobE"] {
		t.Fatal("执行结束后租约不应残留")
	}
}

// TestLockConfigNormalized 校验配置缺省与下限。
func TestLockConfigNormalized(t *testing.T) {
	c := LockConfig{}.Normalized()
	if c.KeyPrefix != "scheduler:lock:" {
		t.Fatalf("默认前缀 = %q", c.KeyPrefix)
	}
	if c.TTL != 5*time.Minute {
		t.Fatalf("默认 TTL = %v", c.TTL)
	}

	small := LockConfig{TTL: time.Second}.Normalized()
	if small.TTL != 3*time.Second {
		t.Fatalf("TTL 过小时应抬到 3s，实际 %v", small.TTL)
	}
	if small.renewInterval() != time.Second {
		t.Fatalf("续约间隔应至少 1s，实际 %v", small.renewInterval())
	}
}
