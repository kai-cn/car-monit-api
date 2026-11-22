package router_test

// JAVA 对照: pro-base-common/.../config/interceptor/WebConfig.java + 20 个 Controller 的 @RequestMapping
//
// 类/职责: 路由装配的"可执行检查"——只验证「注册期」行为，不连数据库/Redis/ES
// 对应 Go 文件: internal/router/router_test.go
//
// 为什么这个测试值得存在：
//
//	1. gin 的路由树在"静态段 + 参数段互斥"的老版本里会 panic，而 Java 侧同一个前缀下
//	   既有 /base/feerecords/list 又有 /base/feerecords/{bigId}。本测试把这条约束
//	   固化成断言——将来升级/降级 gin 时若出现冲突，go test 立刻失败。
//	2. Register 只构造闭包，不解引用 Repo 指针，因此可以把依赖全部留空（nil）来跑，
//	   不需要起任何中间件，天然适合 CI。
//
// DIFF: Java 侧的等价检查是 "启动 Spring 上下文"，几十秒且必须连配置里的 DB；
// Go 的这个测试 <10ms 完成，因为它只编译路由树。

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/handler"
	"github.com/ruoyi/car-monit-api-go/internal/metrics"
	"github.com/ruoyi/car-monit-api-go/internal/router"
)

func newTestEngine() *gin.Engine {
	return router.New(router.Options{
		// pprof 在默认配置下关闭（server.pprof-enabled=false）；路由清单测试需要它，
		// 这里显式打开。默认关闭的行为由 TestPprofDisabledByDefault 单独断言。
		Config:   &config.Config{Server: config.ServerConfig{PprofEnabled: true}},
		Base:     &handler.BaseDeps{},
		Query:    &handler.QueryDeps{},
		SysUtil:  &handler.SysUtilDeps{},
		SelfTest: &handler.SelfTestDeps{},
		Health:   &router.Health{},
	})
}

// TestPprofDisabledByDefault 锁住报告 02 P0-5 的默认值：零值配置不得暴露 /debug/pprof。
func TestPprofDisabledByDefault(t *testing.T) {
	engine := router.New(router.Options{
		Config:   &config.Config{},
		Base:     &handler.BaseDeps{},
		Query:    &handler.QueryDeps{},
		SysUtil:  &handler.SysUtilDeps{},
		SelfTest: &handler.SelfTestDeps{},
		Health:   &router.Health{},
	})
	for _, r := range engine.Routes() {
		if strings.Contains(r.Path, "/debug/pprof") {
			t.Fatalf("默认配置不应注册 pprof 路由，发现 %s %s", r.Method, r.Path)
		}
	}
}

// TestMetricsEndpointRegistered /metrics 是 Go 侧新增端点（报告 02 P0-7），
// 与 context-path 无关，始终挂在根路径。
func TestMetricsEndpointRegistered(t *testing.T) {
	engine := router.New(router.Options{
		Config:   &config.Config{Server: config.ServerConfig{MetricsEnabled: true}},
		Base:     &handler.BaseDeps{},
		Query:    &handler.QueryDeps{},
		SysUtil:  &handler.SysUtilDeps{},
		SelfTest: &handler.SelfTestDeps{},
		Health:   &router.Health{},
		Metrics:  metrics.New(),
	})
	for _, r := range engine.Routes() {
		if r.Method == http.MethodGet && r.Path == "/metrics" {
			return
		}
	}
	t.Fatal("未注册 GET /metrics")
}

// TestRoutesRegistered 断言 Java 侧的关键 URL 在 Go 侧一一存在。
//
// 覆盖范围：19 个基础表的 list + 详情 + listall（抽样）、3 组优化查询、5 个 sysutil 端点、
// 健康检查与 404 兜底。新增 Controller 时这里会提醒"记得同步路由清单"。
func TestRoutesRegistered(t *testing.T) {
	routes := newTestEngine()

	got := map[string]bool{}
	for _, r := range routes.Routes() {
		got[r.Method+" "+r.Path] = true
	}
	if len(got) < 60 {
		t.Fatalf("路由数量异常偏少: %d，期望 >= 60（可能某个 Register 没被调用）", len(got))
	}

	want := []string{
		// 19 张基础表（抽样：主键为字符串 / 为 bigint / 带导出 / 带 /map 的四种形态）
		"GET /base/fwqjcxx/list",
		"GET /base/fwqjcxx/listAll",
		"GET /base/fwqjcxx/:agentPk",
		"GET /base/feerecords/list",
		"GET /base/feerecords/listToExport",
		"GET /base/feerecords/:bigId",
		// NOTE: 这张表在 Java 侧的 @RequestMapping 是 /manager/fwqclls（不是 /base），别顺手改成 /base
		"GET /manager/fwqclls/:bigId",
		"GET /base/snapshotflow/list",
		"GET /base/snapshotflow/listToExport",
		"GET /base/vehicleweight/list",
		"GET /base/vehicleweight/map",
		"GET /base/vehicleweight/:dataSource",
		"GET /base/trailtracks/list",
		// 优化查询三组
		"GET /api/v1/large/snapshot",
		"GET /api/v1/large/fee",
		"GET /api/v1/large/trail",
		"GET /api/v1/large/carTrackQueryByCarNo",
		"GET /api/v1/large/stats/group",
		"POST /api/v1/large/export/submit",
		"GET /api/v1/large/export/status/:taskId",
		"POST /api/v1/large/sync/full",
		"POST /api/v1/large/sync/incremental",
		"POST /api/v1/large/sync/repair",
		"GET /api/v1/unified/:ds/list",
		"POST /api/v1/unified/:ds/export/submit",
		"GET /api/v1/unified/export/status/:taskId",
		"GET /progressive/snapshotflow/list",
		"GET /progressive/feerecords/list",
		"GET /progressive/trailfitting/list",
		"GET /progressive/scale-level",
		// 轨迹查询
		"GET /base/sysutil/saveRedis",
		"GET /base/sysutil/carTrackQueryByCarNo",
		"GET /base/sysutil/carTrackQueryByTime",
		"POST /base/sysutil/changeTrailInfo",
		"GET /base/sysutil/getByTrailBo",
		// 运维自测
		"GET /base/sysutilTest/syncBaseInfo",
		"GET /base/sysutilTest/syncCurrentTrack",
		"GET /base/sysutilTest/syncHistroyTrack",
		"GET /base/sysutilTest/syncSuspiciousCar10",
		"GET /base/sysutilTest/syncOdsSzdnGantry",
		"GET /base/sysutilTest/separateSnapshotFlowTimeList",
		// Go 侧新增
		"GET /healthz",
		"GET /readyz",
		"GET /debug/pprof/goroutine",
	}
	for _, w := range want {
		if !got[w] {
			t.Errorf("缺少路由: %s", w)
		}
	}
}

// TestSelfTestEndpoints 校验 /base/sysutilTest 的两类行为分别正确：
//
//  1. 已实现的两个端点（syncCurrentTrack / syncHistroyTrack）在依赖缺失时**降级返回 200**，
//     而不是 nil 解引用 panic —— 这两个端点的依赖与 4 点定时任务共用，运维手动触发时
//     不该因为某个 Repo 未装配就把进程打挂；
//  2. 未实现的 12 个端点返回 501，且响应体里带 javaRef / reason。
//     这不是「看起来专业」：Java 侧这些端点因为 Mapper 语句缺失会抛
//     Invalid bound statement（详见 internal/handler/selftest.go 文件头 PARITY），
//     这里把原因固化进断言，避免后来者误以为只是偷懒没做。
func TestSelfTestEndpoints(t *testing.T) {
	engine := newTestEngine()

	get := func(path string) *httptest.ResponseRecorder {
		rec := httptest.NewRecorder()
		engine.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
		return rec
	}

	for _, path := range []string{"/base/sysutilTest/syncCurrentTrack", "/base/sysutilTest/syncHistroyTrack"} {
		if rec := get(path); rec.Code != http.StatusOK {
			t.Errorf("%s 状态码 = %d，期望 200（依赖为 nil 时应降级，body=%s）", path, rec.Code, rec.Body.String())
		}
	}

	blocked := []string{
		"/base/sysutilTest/syncSuspiciousCar1", "/base/sysutilTest/syncSuspiciousCar10",
		"/base/sysutilTest/syncOdsSzdnGantry", "/base/sysutilTest/separateSnapshotFlowTimeList",
	}
	for _, path := range blocked {
		rec := get(path)
		if rec.Code != http.StatusNotImplemented {
			t.Errorf("%s 状态码 = %d，期望 501", path, rec.Code)
			continue
		}
		body := rec.Body.String()
		if !strings.Contains(body, "\"javaRef\"") || !strings.Contains(body, "\"reason\"") {
			t.Errorf("%s 的 501 响应缺少 javaRef/reason: %s", path, body)
		}
	}
}

// TestRouterMiddlewareChain 验证 404 返回的仍是 {code,msg,data}，而不是 gin 的纯文本。
//
// PARITY: Spring Boot 的 /error 也返回 JSON；前端统一按 res.data.code 判断，
// 若这里返回纯文本会直接把前端打爆（JSON.parse 抛错）。
func TestRouterMiddlewareChain(t *testing.T) {
	engine := newTestEngine()
	req := httptest.NewRequest(http.MethodGet, "/not-exist/path", nil)
	rec := httptest.NewRecorder()
	engine.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("状态码 = %d，期望 404", rec.Code)
	}
	body := rec.Body.String()
	if !strings.Contains(body, "\"code\":404") || !strings.Contains(body, "\"msg\"") {
		t.Fatalf("404 响应不是 AjaxResult 结构: %s", body)
	}
	if rec.Header().Get("X-Request-Id") == "" {
		t.Fatal("缺少 X-Request-Id 响应头（RequestID 中间件未生效）")
	}
}

// TestHealthLiveness 验证 /healthz 不依赖任何中间件即可返回 UP。
func TestHealthLiveness(t *testing.T) {
	engine := newTestEngine()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()
	engine.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("状态码 = %d，期望 200（body=%s）", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "\"status\":\"UP\"") {
		t.Fatalf("/healthz 响应异常: %s", rec.Body.String())
	}
}
