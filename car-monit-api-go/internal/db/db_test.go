package db

// 本文件是 R1 修复的回归护栏：GORM 慢 SQL / SQL 错误必须落在 Warn / Error，
// 普通 SQL 保持 Debug —— 否则生产 info 级别下慢查询会再次静默。

import (
	"context"
	"errors"
	"log/slog"
	"sync"
	"testing"
	"time"

	gormlogger "gorm.io/gorm/logger"
)

// captureHandler 把 slog 记录收集到内存，供断言使用。
type captureHandler struct {
	mu      sync.Mutex
	records []slog.Record
}

func (h *captureHandler) Enabled(context.Context, slog.Level) bool { return true }

func (h *captureHandler) Handle(_ context.Context, r slog.Record) error {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.records = append(h.records, r)
	return nil
}

func (h *captureHandler) WithAttrs([]slog.Attr) slog.Handler { return h }
func (h *captureHandler) WithGroup(string) slog.Handler      { return h }

func (h *captureHandler) levels() []slog.Level {
	h.mu.Lock()
	defer h.mu.Unlock()
	out := make([]slog.Level, 0, len(h.records))
	for _, r := range h.records {
		out = append(out, r.Level)
	}
	return out
}

func withCapturedSlog(t *testing.T) *captureHandler {
	t.Helper()
	h := &captureHandler{}
	prev := slog.Default()
	slog.SetDefault(slog.New(h))
	t.Cleanup(func() { slog.SetDefault(prev) })
	return h
}

func fakeSQL() (string, int64) { return "SELECT 1", 1 }

func TestGormLoggerRoutesByLevel(t *testing.T) {
	cases := []struct {
		name      string
		level     gormlogger.LogLevel
		slow      time.Duration
		begin     time.Time
		err       error
		wantLevel slog.Level
		wantLog   bool
	}{
		{
			name:      "SQL 错误 → Error",
			level:     gormlogger.Warn,
			slow:      time.Hour,
			begin:     time.Now(),
			err:       errors.New("column does not exist"),
			wantLevel: slog.LevelError,
			wantLog:   true,
		},
		{
			name:      "慢 SQL → Warn（生产 info 级别可见）",
			level:     gormlogger.Warn,
			slow:      time.Millisecond,
			begin:     time.Now().Add(-time.Second),
			wantLevel: slog.LevelWarn,
			wantLog:   true,
		},
		{
			name:      "普通 SQL + LogSQL=info → Debug",
			level:     gormlogger.Info,
			slow:      time.Hour,
			begin:     time.Now(),
			wantLevel: slog.LevelDebug,
			wantLog:   true,
		},
		{
			name:    "普通 SQL + 非 LogSQL → 不输出",
			level:   gormlogger.Warn,
			slow:    time.Hour,
			begin:   time.Now(),
			wantLog: false,
		},
		{
			name:    "RecordNotFound 被忽略（与 IgnoreRecordNotFoundError=true 一致）",
			level:   gormlogger.Warn,
			slow:    time.Hour,
			begin:   time.Now(),
			err:     gormlogger.ErrRecordNotFound,
			wantLog: false,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			h := withCapturedSlog(t)
			lg := &gormSlogLogger{level: tc.level, slowThreshold: tc.slow}
			lg.Trace(context.Background(), tc.begin, fakeSQL, tc.err)

			got := h.levels()
			if !tc.wantLog {
				if len(got) != 0 {
					t.Fatalf("期望不输出日志，实际输出 %d 条: %v", len(got), got)
				}
				return
			}
			if len(got) != 1 {
				t.Fatalf("期望 1 条日志，实际 %d 条", len(got))
			}
			if got[0] != tc.wantLevel {
				t.Fatalf("日志级别 = %v，期望 %v", got[0], tc.wantLevel)
			}
		})
	}
}

// TestGormLoggerSilent 确保级别为 Silent 时完全不输出（对应 gorm 的语义）。
func TestGormLoggerSilent(t *testing.T) {
	h := withCapturedSlog(t)
	lg := &gormSlogLogger{level: gormlogger.Silent, slowThreshold: time.Nanosecond}
	lg.Trace(context.Background(), time.Now().Add(-time.Second), fakeSQL, errors.New("boom"))
	if n := len(h.levels()); n != 0 {
		t.Fatalf("Silent 级别不应输出，实际 %d 条", n)
	}
}
