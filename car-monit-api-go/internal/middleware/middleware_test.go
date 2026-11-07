package middleware

// 请求级超时开关的回归护栏（报告 02 P1-9）：默认关闭时必须完全不影响请求 ctx。

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

func newTimeoutEngine(d time.Duration) *gin.Engine {
	gin.SetMode(gin.TestMode)
	e := gin.New()
	e.Use(Timeout(d))
	e.GET("/probe", func(c *gin.Context) {
		_, hasDeadline := c.Request.Context().Deadline()
		if hasDeadline {
			c.String(http.StatusOK, "deadline")
			return
		}
		c.String(http.StatusOK, "no-deadline")
	})
	return e
}

func TestTimeoutDisabled(t *testing.T) {
	e := newTimeoutEngine(0)
	rec := httptest.NewRecorder()
	e.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/probe", nil))
	if rec.Body.String() != "no-deadline" {
		t.Fatalf("d=0 时不应注入 deadline，实际: %s", rec.Body.String())
	}
}

func TestTimeoutEnabled(t *testing.T) {
	e := newTimeoutEngine(2 * time.Second)
	rec := httptest.NewRecorder()
	e.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/probe", nil))
	if rec.Body.String() != "deadline" {
		t.Fatalf("d>0 时应给请求 ctx 注入 deadline，实际: %s", rec.Body.String())
	}
}
