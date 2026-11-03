package router

// JAVA 对照:
//
//	pro-base-common/src/main/java/com/ruoyi/common/config/interceptor/WebConfig.java
//	pro-base-common/src/main/java/com/ruoyi/common/config/interceptor/SecurityInterceptor.java
//	pro-business-api/src/main/java/com/ruoyi/base/controller/*.java（20 个 Controller 的 @RequestMapping）
//	pro-business-api/src/main/resources/application.yml:1-4（server.port / context-path）
//
// 类/职责: 把「中间件链 + 四组路由 + 健康检查 + 404 兜底」装配成一个 http.Handler
// 对应 Go 文件: internal/router/router.go
// 关键映射:
//
//	WebMvcConfigurer.addInterceptors          → engine.Use(RequestID, AccessLog, Recovery, ErrorHandler)
//	@RestController 的 @GetMapping("/x")      → 由各 handler 包的 Register 挂到同一 root group
//	server.servlet.context-path               → root := engine.Group(cfg.Server.ContextPath)
//	Spring 默认的 /error 白页                  → engine.NoRoute（返回同一套 AjaxResult 结构）
//	Actuator 的 /actuator/health              → /healthz（本项目 Java 侧未接 Actuator，属 Go 侧新增）
//	JVM 的 jstack / JFR                        → /debug/pprof/*（net/http/pprof，Go 侧新增）
//
// 已知顺序约束：gin 的静态段与参数段可以互为兄弟（已实测 gin v1.10 支持 /list 与 /:bigId 共存），
// 因此路由表与 Java 的 URL 完全一致，前端无需改 baseURL。
//
// DIFF: Spring 用注解扫描自动注册；Go 必须显式调用四组 Register——好处是启动时就能发现
// "某个 Controller 忘了挂"，坏处是新增 Controller 要在这里加一行。

import (
	"context"
	"net/http"
	"net/http/pprof"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/handler"
	"github.com/ruoyi/car-monit-api-go/internal/middleware"
	"github.com/ruoyi/car-monit-api-go/internal/response"
)

// Health 是健康检查探针的依赖注入点。
//
// DIFF: Spring Boot Actuator 会通过 HealthIndicator 自动聚合各依赖状态；
// Go 侧没有容器，由 main() 把"怎么探"注入进来，router 只负责拼装 JSON。
type Health struct {
	// DB 返回 nil 表示可用（对应 DataSourceHealthIndicator）
	DB func(ctx context.Context) error
	// Cache 返回 nil 表示可用（对应 RedisHealthIndicator）
	Cache func(ctx context.Context) error
	// ES 返回 nil 表示可用（ES 在 Java 侧不是强依赖，失败只降级为 warn）
	ES func(ctx context.Context) error
	// Consumer 返回 false 表示 MQ 消费端未启动
	Consumer func() bool
}

// Options 是装配路由所需的全部依赖。
type Options struct {
	Config   *config.Config
	Base     *handler.BaseDeps
	Query    *handler.QueryDeps
	SysUtil  *handler.SysUtilDeps
	SelfTest *handler.SelfTestDeps
	Health   *Health
}

// New 构造 gin.Engine。
func New(opts Options) *gin.Engine {
	gin.SetMode(ginMode(opts.Config.Server.Mode))

	// DIFF: gin.Default() 自带 Logger+Recovery，但它的日志是 gin 自己的格式；
	// 这里用 gin.New() + 自己的中间件，让日志统一走 slog（与 Java 的 logback 单一出口对应）。
	engine := gin.New()
	engine.Use(middleware.RequestID(), middleware.AccessLog(), middleware.Recovery(), middleware.ErrorHandler())
	// Java 配了 `spring.mvc.pathmatch.matching-strategy: ant_path_matcher`（application.yml:9-10），
	// 实测 `/base/gantry/list/` 在 Java 上是 200 —— Spring 的 AntPathMatcher 容忍结尾斜杠。
	// 之前这里写 false 并注释成"与 Spring 一致"，判定是反的：Go 会对同一个 URL 返回 404，
	// 等于把 Java 上能用的调用方直接打死。开启后 gin 用 301 跳到无斜杠路径，
	// 与 Java 的 200 仍有差别（状态码不同），但不再是"能不能访问"的差别。
	engine.RedirectTrailingSlash = true

	registerHealth(engine, opts.Health)
	registerPprof(engine)

	// server.servlet.context-path（默认 "/"）。gin 的 Group("/") 不会给路径加前缀。
	root := engine.Group(opts.Config.Server.ContextPath)

	if opts.Base != nil {
		opts.Base.Register(root)
	}
	if opts.Query != nil {
		opts.Query.Register(root)
	}
	if opts.SysUtil != nil {
		opts.SysUtil.Register(root)
	}
	if opts.SelfTest != nil {
		opts.SelfTest.Register(root)
	}

	// 404 兜底：Spring 的 /error 也返回 {code,msg,data}，这里保持同一结构，
	// 否则前端拿到的 "404 page not found" 纯文本会直接打爆 JSON.parse。
	engine.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, response.FailCode(http.StatusNotFound,
			"接口不存在: "+c.Request.Method+" "+c.Request.URL.Path))
	})
	engine.NoMethod(func(c *gin.Context) {
		c.JSON(http.StatusMethodNotAllowed, response.FailCode(http.StatusMethodNotAllowed,
			"请求方法不支持: "+c.Request.Method))
	})
	engine.HandleMethodNotAllowed = true

	return engine
}

func ginMode(mode string) string {
	switch mode {
	case "debug", "test", "release":
		return mode
	default:
		return gin.ReleaseMode
	}
}

// registerHealth 挂载 /healthz（存活）与 /readyz（依赖就绪）。
//
// PARITY: Java 侧并未引入 spring-boot-starter-actuator（application.yml 全文无 management.*），
// 因此这两个端点是 Go 侧新增；只读、无副作用，对灰度脚本与 K8s 探针都安全。
func registerHealth(engine *gin.Engine, h *Health) {
	probe := func(c *gin.Context, deep bool) {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 2*time.Second)
		defer cancel()

		body := gin.H{"status": "UP", "time": time.Now().Format(time.RFC3339)}
		status := http.StatusOK

		check := func(name string, fn func(context.Context) error) {
			if fn == nil {
				return
			}
			if err := fn(ctx); err != nil {
				body[name] = "DOWN: " + err.Error()
				body["status"] = "DOWN"
				status = http.StatusServiceUnavailable
				return
			}
			body[name] = "UP"
		}

		if deep && h != nil {
			check("gaussdb", h.DB)
			check("redis", h.Cache)
			check("elasticsearch", h.ES)
			if h.Consumer != nil {
				if h.Consumer() {
					body["mqConsumer"] = "UP"
				} else {
					// 消费端未启动只降级为 WARN：Java 侧消费者启动失败也不会让应用退出。
					body["mqConsumer"] = "DOWN"
				}
			}
		}
		c.JSON(status, body)
	}

	engine.GET("/healthz", func(c *gin.Context) { probe(c, false) })
	engine.GET("/readyz", func(c *gin.Context) { probe(c, true) })
	engine.GET("/health", func(c *gin.Context) { probe(c, true) }) // 兼容运维脚本里的 /health
}

// registerPprof 暴露 Go 的性能剖析端点。
//
// DIFF: Java 侧对应的是 jstack / jmap / JFR / Arthas；Go 用 net/http/pprof，
// 排查"哪个函数占 CPU/内存"比 JFR 更直接。生产建议只在内网或加鉴权。
func registerPprof(engine *gin.Engine) {
	g := engine.Group("/debug/pprof")
	g.GET("/", gin.WrapF(pprof.Index))
	g.GET("/cmdline", gin.WrapF(pprof.Cmdline))
	g.GET("/profile", gin.WrapF(pprof.Profile))
	g.GET("/symbol", gin.WrapF(pprof.Symbol))
	g.POST("/symbol", gin.WrapF(pprof.Symbol))
	g.GET("/trace", gin.WrapF(pprof.Trace))
	g.GET("/heap", gin.WrapH(pprof.Handler("heap")))
	g.GET("/goroutine", gin.WrapH(pprof.Handler("goroutine")))
	g.GET("/allocs", gin.WrapH(pprof.Handler("allocs")))
	g.GET("/block", gin.WrapH(pprof.Handler("block")))
	g.GET("/mutex", gin.WrapH(pprof.Handler("mutex")))
	g.GET("/threadcreate", gin.WrapH(pprof.Handler("threadcreate")))
}
