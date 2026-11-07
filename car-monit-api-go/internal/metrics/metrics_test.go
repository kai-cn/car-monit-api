package metrics

// 指标注册与中间件的回归护栏（报告 02 P0-7）：无需外部依赖，直接校验 Registry 产物。

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

// metricNames 把 Gather 结果拍平成 name 集合，便于断言。
func metricNames(t *testing.T, m *Metrics) map[string]bool {
	t.Helper()
	families, err := m.reg.Gather()
	if err != nil {
		t.Fatalf("Gather 失败: %v", err)
	}
	out := make(map[string]bool, len(families))
	for _, f := range families {
		out[f.GetName()] = true
	}
	return out
}

func TestHTTPMiddlewareRecordsRED(t *testing.T) {
	gin.SetMode(gin.TestMode)
	m := New()
	e := gin.New()
	e.Use(m.GinMiddleware())
	e.GET("/demo/:id", func(c *gin.Context) { c.String(http.StatusOK, "ok") })
	e.GET("/metrics", func(c *gin.Context) { c.String(http.StatusOK, "metrics") })

	for i := 0; i < 2; i++ {
		rec := httptest.NewRecorder()
		e.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/demo/123", nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("业务请求失败: %d", rec.Code)
		}
	}
	// /metrics 自身不应进入业务指标
	rec := httptest.NewRecorder()
	e.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))

	families, err := m.reg.Gather()
	if err != nil {
		t.Fatalf("Gather 失败: %v", err)
	}
	var found bool
	for _, f := range families {
		if f.GetName() != "car_monit_http_requests_total" {
			continue
		}
		found = true
		for _, mt := range f.GetMetric() {
			labels := map[string]string{}
			for _, lp := range mt.GetLabel() {
				labels[lp.GetName()] = lp.GetValue()
			}
			if labels["route"] == "/metrics" {
				t.Fatal("/metrics 自身不应被计入 HTTP 指标")
			}
			if labels["route"] != "/demo/:id" {
				t.Fatalf("route 应为路由模板 /demo/:id，实际 %q", labels["route"])
			}
			if labels["status"] != "200" {
				t.Fatalf("status 标签 = %q，期望 200", labels["status"])
			}
			if mt.GetCounter().GetValue() != 2 {
				t.Fatalf("计数 = %v，期望 2", mt.GetCounter().GetValue())
			}
		}
	}
	if !found {
		t.Fatal("未找到 car_monit_http_requests_total")
	}
}

func TestObserveConsumerMessage(t *testing.T) {
	m := New()
	m.ObserveConsumerMessage("ok", 12*time.Millisecond)
	m.ObserveConsumerMessage("error", 30*time.Millisecond)

	names := metricNames(t, m)
	for _, want := range []string{
		"car_monit_consumer_messages_total",
		"car_monit_consumer_handle_duration_seconds",
	} {
		if !names[want] {
			t.Fatalf("缺少指标 %s，实际：%v", want, names)
		}
	}
}

func TestHandlerServesTextFormat(t *testing.T) {
	m := New()
	m.ObserveConsumerMessage("ok", time.Millisecond)
	rec := httptest.NewRecorder()
	m.Handler().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("GET /metrics = %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "car_monit_consumer_messages_total") {
		t.Fatalf("响应体缺少指标名，前 200 字节: %.200s", rec.Body.String())
	}
}

// TestNilMetricsSafe 保证依赖注入为 nil 时不会 panic（router 允许 Metrics=nil）。
func TestNilMetricsSafe(t *testing.T) {
	var m *Metrics
	m.ObserveConsumerMessage("ok", time.Millisecond) // 不应 panic
	if m.Handler() == nil {
		t.Fatal("nil Metrics 的 Handler 不应返回 nil")
	}

	gin.SetMode(gin.TestMode)
	e := gin.New()
	e.Use(m.GinMiddleware())
	e.GET("/ping", func(c *gin.Context) { c.String(http.StatusOK, "pong") })
	rec := httptest.NewRecorder()
	e.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/ping", nil))
	if rec.Code != http.StatusOK || rec.Body.String() != "pong" {
		t.Fatalf("nil Metrics 下请求应正常透传，实际 %d / %q", rec.Code, rec.Body.String())
	}
}
