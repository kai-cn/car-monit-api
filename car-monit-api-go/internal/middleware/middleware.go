// Package middleware 提供 Gin 中间件链，等价于 Spring 的 Filter / Interceptor / AOP 切面。
//
// JAVA 对照:
//
//	pro-base-common/src/main/java/com/ruoyi/common/config/interceptor/WebConfig.java（拦截器注册）
//	pro-base-common/src/main/java/com/ruoyi/common/config/interceptor/SecurityInterceptor.java
//	Spring MVC 的 HandlerInterceptor.preHandle / postHandle / afterCompletion
//
// 对应 Go 文件: internal/middleware/middleware.go
//
// 关键映射:
//
//	Filter/Interceptor           → func(*gin.Context) 链（gin.Use 注册）
//	@ControllerAdvice 全局异常    → Recovery() + ErrorHandler()（c.Error(err) 汇总成统一响应）
//	Logback 的 access log        → AccessLog()（每个请求一行结构化日志）
//	RequestContextHolder         → c.Request.Context()（把值放进 context 往下传）
package middleware

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"runtime/debug"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/ruoyi/car-monit-api-go/internal/logging"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/response"
)

// HeaderRequestID 与常见网关约定一致；前端/链路追踪用它串日志。
const HeaderRequestID = "X-Request-Id"

// ctxKeyRequestID 用私有类型做键，避免 context 键冲突（Java 里对应 MDC key）。
type ctxKeyRequestID struct{}

// RequestID 给每个请求分配 traceId 并写入 context + 响应头。
//
// DIFF: Spring 用 Sleuth/Micrometer Tracing 自动注入 traceId；Go 没有自动埋点，
// 必须由中间件显式生成并塞进 context，后续日志通过 logging.From(ctx) 才能带上它。
func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		rid := c.GetHeader(HeaderRequestID)
		if rid == "" {
			rid = uuid.NewString()
		}
		c.Set("requestId", rid)
		c.Header(HeaderRequestID, rid)

		ctx := c.Request.Context()
		ctx = logging.WithLogger(ctx, slog.Default().With("requestId", rid, "path", c.FullPath()))
		c.Request = c.Request.WithContext(ctx)
		c.Next()
	}
}

// Timeout 给请求级 ctx 加统一超时（报告 02 P1-9）。
//
// 默认关闭（server.request-timeout: 0）。开启后 DB/ES 等下游调用会随 ctx 到期返回
// context deadline exceeded，由既有 ErrorHandler 转成错误响应 —— 不改任何接口契约，
// 只是避免慢依赖无限拖住 goroutine。
func Timeout(d time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		if d <= 0 {
			c.Next()
			return
		}
		ctx, cancel := context.WithTimeout(c.Request.Context(), d)
		defer cancel()
		c.Request = c.Request.WithContext(ctx)
		c.Next()
	}
}

// AccessLog 打印访问日志（对应 logback 的 access log appender）。
func AccessLog() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()

		lg := logging.From(c.Request.Context())
		args := []any{
			"method", c.Request.Method,
			"path", c.Request.URL.Path,
			"status", c.Writer.Status(),
			"cost", time.Since(start).String(),
			"ip", c.ClientIP(),
			"bytes", c.Writer.Size(),
		}
		// DIFF: Java 里 access log 是"配置一个 appender"就有的；Go 必须自己写这一行。
		if c.Writer.Status() >= http.StatusInternalServerError {
			lg.Error("请求处理失败", args...)
			return
		}
		lg.Info("请求完成", args...)
	}
}

// Recovery 把 panic 转成 500。
//
// DIFF: Java 的未捕获异常由 DispatcherServlet 兜底；Go 的 goroutine panic 会直接杀掉进程，
// 所以 HTTP 入口必须显式 recover。注意：recover 只对"同一个 goroutine"生效，
// 业务里 `go func()` 启动的协程需要自己 recover（见 service 层的说明）。
func Recovery() gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if r := recover(); r != nil {
				lg := logging.From(c.Request.Context())
				lg.Error("panic 已捕获", "panic", r, "stack", string(debug.Stack()))
				c.AbortWithStatusJSON(http.StatusInternalServerError,
					response.Fail("服务器内部错误"))
			}
		}()
		c.Next()
	}
}

// ErrorHandler 把 c.Error(err) 收集到的错误统一转换为 AjaxResult。
//
// DIFF: Java 用 @ControllerAdvice + @ExceptionHandler 集中处理异常；
// Gin 没有异常传播机制，只能"处理函数里 c.Error(err) + 这里统一出响应"，或者 handler 里直接返回。
func ErrorHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()
		if len(c.Errors) == 0 || c.Writer.Written() {
			return
		}
		err := c.Errors.Last().Err
		lg := logging.From(c.Request.Context())
		lg.Error("业务处理失败", "err", err.Error())

		var be *BizError
		if errors.As(err, &be) {
			c.JSON(http.StatusOK, response.FailCode(be.Code, be.Message))
			return
		}
		// 参数绑定失败：走 Spring 的错误页面机制，不是 AjaxResult。
		var bnd *BindError
		if errors.As(err, &bnd) {
			c.JSON(bnd.Status, bnd.envelope(c.Request.URL.Path))
			return
		}
		c.JSON(http.StatusOK, response.Fail(err.Error()))
	}
}

// BindError 对应 Spring 的参数类型转换失败（TypeMismatchException 等）。
//
// PARITY: 这类错误与业务异常（BizError）不同源：Java 里 @PathVariable Long id 收到
// "ZZZ-NOT-EXIST" 时，根本不会进到方法体，由 DefaultHandlerExceptionResolver 直接
// 回 HTTP 400 + Spring 默认错误体；而 ServiceException 是 HTTP 200 + 业务 code。
// Go 之前把它归成 BizError，于是语义变成了「请求成功但业务失败」：
// 实测 /base/gantryIp/ZZZ-NOT-EXIST：java=400 go=200（码对但 HTTP 状态错）。
type BindError struct {
	Status  int
	Reason  string
	Message string
	Err     error
}

// Error 实现 error 接口
func (e *BindError) Error() string {
	if e.Err != nil {
		return e.Reason + ": " + e.Err.Error()
	}
	return e.Reason
}

// Unwrap 支持 errors.Is/As 穿透到内部错误
func (e *BindError) Unwrap() error { return e.Err }

// NewBindError 构造一个 Spring 语义的参数绑定失败
func NewBindError(status int, reason string, cause ...error) *BindError {
	be := &BindError{Status: status, Reason: reason, Message: reason}
	if len(cause) > 0 {
		be.Err = cause[0]
	}
	return be
}

// envelope 拼出 Spring Boot 默认错误体的五个键（对应 org.springframework.boot.web.servlet.error.ErrorAttributes）。
func (e *BindError) envelope(path string) gin.H {
	return gin.H{
		"timestamp": time.Now().UTC().Format(model.JavaStdDateLayout),
		"status":    e.Status,
		"error":     http.StatusText(e.Status),
		"message":   "",
		"path":      path,
	}
}

// BizError 对应 Java 的 ServiceException（业务异常：HTTP 200 + 业务 code 非 200）。
//
// DIFF: Java 用受检/非受检异常区分"可恢复"和"编程错误"；Go 只有 error，
// 用包装类型 + errors.As 表达同样的区分，仍由上面的 ErrorHandler 统一映射成响应。
type BizError struct {
	Code    int
	Message string
	Err     error
}

// Error 实现 error 接口
func (e *BizError) Error() string {
	if e.Err != nil {
		return e.Message + ": " + e.Err.Error()
	}
	return e.Message
}

// Unwrap 支持 errors.Is/As 穿透到内部错误
func (e *BizError) Unwrap() error { return e.Err }

// NewBizError 构造业务异常（对应 throw new ServiceException(msg)）
func NewBizError(code int, msg string, cause ...error) *BizError {
	be := &BizError{Code: code, Message: msg}
	if len(cause) > 0 {
		be.Err = cause[0]
	}
	return be
}
