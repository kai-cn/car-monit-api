package utils

// 本文件承载"进程退出时为组件关闭设置上限"的通用工具。
//
// 背景（报告 01 Q9）：全量同步/导出等长任务使用 context.WithoutCancel，
// 关闭时 wg.Wait() 没有 deadline，一个在途的全年同步会把进程挂住数小时。
// 这里提供一个带超时的等待：超时后调用方记录 WARN 并继续关闭下一个组件，
// 由进程退出兜底（残留 goroutine 随进程结束，不再需要清理）。

import "time"

// WaitTimeout 在 d 内等待 fn 返回。
//
// 返回 true 表示 fn 已正常返回；false 表示已超时（fn 仍在后台运行，调用方应记录告警）。
// d <= 0 时立即返回 false，不阻塞。
func WaitTimeout(d time.Duration, fn func()) bool {
	if fn == nil {
		return true
	}
	done := make(chan struct{})
	go func() {
		defer close(done)
		fn()
	}()
	if d <= 0 {
		return false
	}
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-done:
		return true
	case <-timer.C:
		return false
	}
}
