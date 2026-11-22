package service

// 关闭语义的回归护栏：Close() 必须先取消进程级任务 ctx（在途导出才能退出），
// 再等待 WaitGroup —— 顺序反了会让 Close 永久阻塞。

import (
	"testing"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/config"
)

func TestUnifiedExportServiceCloseCancelsBaseCtx(t *testing.T) {
	s := NewUnifiedExportService(nil, nil, config.OptimizationConfig{})
	if err := s.baseCtx.Err(); err != nil {
		t.Fatalf("构造后 baseCtx 不应已取消: %v", err)
	}

	done := make(chan struct{})
	go func() {
		s.Close()
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("Close 在无在途任务时应立即返回")
	}

	if err := s.baseCtx.Err(); err == nil {
		t.Fatal("Close 后 baseCtx 必须已取消（在途导出据此退出）")
	}
}

func TestLargeScaleQueryServiceCloseCancelsBaseCtx(t *testing.T) {
	s := NewLargeScaleQueryService(nil, nil, config.OptimizationConfig{})
	if err := s.baseCtx.Err(); err != nil {
		t.Fatalf("构造后 baseCtx 不应已取消: %v", err)
	}

	done := make(chan struct{})
	go func() {
		s.Close()
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("Close 在无在途任务时应立即返回")
	}

	if err := s.baseCtx.Err(); err == nil {
		t.Fatal("Close 后 baseCtx 必须已取消")
	}
}
