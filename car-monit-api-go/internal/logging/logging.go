// Package logging 统一日志入口。
//
// JAVA 对照: pro-business-api/src/main/resources/logback-spring.xml + SLF4J LoggerFactory
// 对应 Go 文件: internal/logging/logging.go
//
// 关键映射:
//
//	logback.xml 的 appender/pattern → slog Handler（TextHandler / JSONHandler）
//	MDC（ThreadLocal）              → context.Context 里携带的字段（WithLogger）
//	log.info("a={}, b={}", a, b)    → log.Info("msg", "a", a, "b", b)（结构化 kv，无需占位符）
package logging

import (
	"context"
	"log/slog"
	"os"
	"strings"
)

type ctxKey struct{}

// Init 按配置初始化全局 logger。
//
// DIFF: Logback 通过 XML 声明式配置；Go 的 slog 只能代码配置，且"全局 logger"是可替换变量
// （slog.SetDefault），不要在业务代码里缓存 logger 指针，否则测试替换会失效。
func Init(level, format string) *slog.Logger {
	var lv slog.Level
	switch strings.ToLower(level) {
	case "debug":
		lv = slog.LevelDebug
	case "warn", "warning":
		lv = slog.LevelWarn
	case "error":
		lv = slog.LevelError
	default:
		lv = slog.LevelInfo
	}
	opts := &slog.HandlerOptions{Level: lv, AddSource: lv <= slog.LevelDebug}

	var h slog.Handler
	if strings.EqualFold(format, "json") {
		h = slog.NewJSONHandler(os.Stdout, opts)
	} else {
		h = slog.NewTextHandler(os.Stdout, opts)
	}
	logger := slog.New(h)
	slog.SetDefault(logger)
	return logger
}

// WithLogger 把 logger 放进 context，等价于 Java 的 MDC 透传。
//
// DIFF: Java 的 MDC 是 ThreadLocal，异步/线程池切换会丢；Go 用 context 显式传递，
// 因此每个跨层调用（handler → service → repo）都必须把 ctx 原样往下传，不能新建 context.Background()。
func WithLogger(ctx context.Context, logger *slog.Logger) context.Context {
	return context.WithValue(ctx, ctxKey{}, logger)
}

// From 取出携带的 logger，未携带时回落到默认 logger。
func From(ctx context.Context) *slog.Logger {
	if l, ok := ctx.Value(ctxKey{}).(*slog.Logger); ok && l != nil {
		return l
	}
	return slog.Default()
}

// With 在 context 上追加固定字段（对应 MDC.put），返回新 context 与新 logger。
func With(ctx context.Context, args ...any) (context.Context, *slog.Logger) {
	l := From(ctx).With(args...)
	return WithLogger(ctx, l), l
}
