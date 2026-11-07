// Package metrics 暴露最小可观测性指标集（Prometheus）。
//
// JAVA 对照: 无（Java 侧未接 Actuator/Micrometer，本包是 Go 侧新增，属报告 02 P0-7）
//
// 设计取舍：
//   - 只依赖 prometheus/client_golang 的默认 registry 之外的一个私有 Registry，
//     避免与进程内其他库（若有）的默认指标混在一起；
//   - 依赖健康用后台采样（默认 15s）而不是每次抓取都 ping：避免 Prometheus 抓取
//     放大 DB/Redis/ES 压力，也让"抓取时刻恰好抖动"不会误报；
//   - 不引入 OpenTelemetry：trace 需要跨服务拓扑才有意义，当前先做指标（P2-2）。
package metrics

import (
	"context"
	"database/sql"
	"log/slog"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
)

// Namespace 是所有指标的统一前缀（Prometheus 命名规范：<namespace>_<subsystem>_<name>）。
const Namespace = "car_monit"

// Metrics 持有指标集与私有 Registry。
type Metrics struct {
	reg *prometheus.Registry

	httpTotal   *prometheus.CounterVec
	httpLatency *prometheus.HistogramVec

	depUp *prometheus.GaugeVec

	consumerHealthy   prometheus.Gauge
	consumerHeartbeat prometheus.Gauge
	consumerAge       prometheus.Gauge
	consumerMessages  *prometheus.CounterVec
	consumerLatency   *prometheus.HistogramVec
}

// New 构造指标集并注册到私有 Registry。
func New() *Metrics {
	m := &Metrics{
		reg: prometheus.NewRegistry(),
		httpTotal: prometheus.NewCounterVec(prometheus.CounterOpts{
			Namespace: Namespace, Subsystem: "http", Name: "requests_total",
			Help: "HTTP 请求总数（按方法/路由模板/状态码）",
		}, []string{"method", "route", "status"}),
		httpLatency: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Namespace: Namespace, Subsystem: "http", Name: "request_duration_seconds",
			Help:    "HTTP 请求耗时（按方法/路由模板）",
			Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60},
		}, []string{"method", "route"}),
		depUp: prometheus.NewGaugeVec(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "dependency", Name: "up",
			Help: "依赖可用性（1=UP，0=DOWN），由后台采样更新",
		}, []string{"dependency"}),
		consumerHealthy: prometheus.NewGauge(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "consumer", Name: "healthy",
			Help: "MQ 消费端心跳是否健康（1=健康，0=不健康/未启动）",
		}),
		consumerHeartbeat: prometheus.NewGauge(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "consumer", Name: "last_heartbeat_timestamp_seconds",
			Help: "消费循环最后一次心跳的 Unix 时间戳（秒）",
		}),
		consumerAge: prometheus.NewGauge(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "consumer", Name: "heartbeat_age_seconds",
			Help: "距消费循环最后一次心跳的秒数；持续增大说明循环卡死",
		}),
		consumerMessages: prometheus.NewCounterVec(prometheus.CounterOpts{
			Namespace: Namespace, Subsystem: "consumer", Name: "messages_total",
			Help: "消费消息总数（result=ok/error）",
		}, []string{"result"}),
		consumerLatency: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Namespace: Namespace, Subsystem: "consumer", Name: "handle_duration_seconds",
			Help:    "单条消息处理耗时（含 DB+ES 双写）",
			Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10},
		}, []string{"result"}),
	}

	m.reg.MustRegister(m.httpTotal, m.httpLatency, m.depUp,
		m.consumerHealthy, m.consumerHeartbeat, m.consumerAge, m.consumerMessages, m.consumerLatency)
	return m
}

// Handler 返回 /metrics 的 http.Handler。
func (m *Metrics) Handler() http.Handler {
	if m == nil {
		return http.NotFoundHandler()
	}
	return promhttp.HandlerFor(m.reg, promhttp.HandlerOpts{})
}

// GinMiddleware 记录 HTTP RED 指标（rate/errors/duration）。
//
// route 用 c.FullPath()（路由模板，如 /base/gantry/:id），避免把每个 id 变成独立时间序列。
// /metrics 自身不记录，防止抓取流量污染业务指标。
func (m *Metrics) GinMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if m == nil || c.FullPath() == "/metrics" {
			c.Next()
			return
		}
		start := time.Now()
		c.Next()

		route := c.FullPath()
		if route == "" {
			route = "unmatched"
		}
		method := c.Request.Method
		m.httpTotal.WithLabelValues(method, route, strconv.Itoa(c.Writer.Status())).Inc()
		m.httpLatency.WithLabelValues(method, route).Observe(time.Since(start).Seconds())
	}
}

// ObserveConsumerMessage 记录一条消息的处理结果与耗时（由 SnapshotFlowConsumer 回调）。
func (m *Metrics) ObserveConsumerMessage(result string, cost time.Duration) {
	if m == nil {
		return
	}
	if result == "" {
		result = "unknown"
	}
	m.consumerMessages.WithLabelValues(result).Inc()
	m.consumerLatency.WithLabelValues(result).Observe(cost.Seconds())
}

// ConsumerSnapshot 是消费端心跳快照的函数签名（与 service.SnapshotFlowConsumer.HealthSnapshot 一致）。
type ConsumerSnapshot func() (registered, running bool, lastTick time.Time, consecutiveErrors int, lastErr string)

// StartSampler 启动依赖健康采样（默认 15s 一次）。
//
// deps 里任何一项为 nil 时跳过该项；HTTP 超时 2s，避免慢依赖拖住采样循环。
// 采样协程自带 recover，跟随 ctx 退出。
func (m *Metrics) StartSampler(ctx context.Context, interval time.Duration, deps map[string]func(context.Context) error,
	check ConsumerSnapshot) {
	if m == nil {
		return
	}
	if interval <= 0 {
		interval = 15 * time.Second
	}

	sample := func() {
		for name, fn := range deps {
			if fn == nil {
				continue
			}
			probeCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
			err := fn(probeCtx)
			cancel()
			if err != nil {
				m.depUp.WithLabelValues(name).Set(0)
				continue
			}
			m.depUp.WithLabelValues(name).Set(1)
		}
		if check != nil {
			registered, running, lastTick, _, _ := check()
			healthy := registered && running && !lastTick.IsZero()
			if healthy {
				m.consumerHealthy.Set(1)
				m.consumerHeartbeat.Set(float64(lastTick.Unix()))
				m.consumerAge.Set(time.Since(lastTick).Seconds())
			} else {
				m.consumerHealthy.Set(0)
				if !lastTick.IsZero() {
					m.consumerHeartbeat.Set(float64(lastTick.Unix()))
					m.consumerAge.Set(time.Since(lastTick).Seconds())
				}
			}
		}
	}

	go func() {
		defer func() {
			if r := recover(); r != nil {
				slog.Error("[指标] 依赖采样协程 panic 退出", "panic", r)
			}
		}()
		sample()
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				sample()
			}
		}
	}()
}

// RegisterDBPool 把 database/sql 连接池状态导出为 gauge（对应报告 02 §5.9）。
func (m *Metrics) RegisterDBPool(db *sql.DB) {
	if m == nil || db == nil {
		return
	}
	stats := db.Stats
	m.reg.MustRegister(
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "db_pool", Name: "open_connections",
			Help: "当前打开的连接数",
		}, func() float64 { return float64(stats().OpenConnections) }),
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "db_pool", Name: "in_use_connections",
			Help: "正在使用中的连接数",
		}, func() float64 { return float64(stats().InUse) }),
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "db_pool", Name: "idle_connections",
			Help: "空闲连接数",
		}, func() float64 { return float64(stats().Idle) }),
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "db_pool", Name: "max_open_connections",
			Help: "连接池上限",
		}, func() float64 { return float64(stats().MaxOpenConnections) }),
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "db_pool", Name: "wait_total",
			Help: "等待可用连接的总次数（持续增长说明池过小）",
		}, func() float64 { return float64(stats().WaitCount) }),
	)
}

// RegisterRedisPool 把 go-redis 连接池状态导出为 gauge。
func (m *Metrics) RegisterRedisPool(client *redis.Client) {
	if m == nil || client == nil {
		return
	}
	pool := client.PoolStats
	m.reg.MustRegister(
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "redis_pool", Name: "total_conns",
			Help: "Redis 连接池总连接数",
		}, func() float64 { return float64(pool().TotalConns) }),
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "redis_pool", Name: "idle_conns",
			Help: "Redis 连接池空闲连接数",
		}, func() float64 { return float64(pool().IdleConns) }),
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "redis_pool", Name: "stale_conns",
			Help: "Redis 连接池陈旧连接数",
		}, func() float64 { return float64(pool().StaleConns) }),
	)
}

// SyncStats 是 GaussDB→ES 同步计数器的快照函数签名。
type SyncStats func() (read, writeOK, writeFailed int64)

// RegisterSyncStats 把同步进度导出为 gauge（报告 02 §4.2：原子计数器此前无任何出口）。
func (m *Metrics) RegisterSyncStats(stats SyncStats) {
	if m == nil || stats == nil {
		return
	}
	m.reg.MustRegister(
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "gauss_es_sync", Name: "rows_read_total",
			Help: "同步已读取的行数（进程累计）",
		}, func() float64 { r, _, _ := stats(); return float64(r) }),
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "gauss_es_sync", Name: "rows_written_total",
			Help: "同步成功写入 ES 的行数（进程累计）",
		}, func() float64 { _, ok, _ := stats(); return float64(ok) }),
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: Namespace, Subsystem: "gauss_es_sync", Name: "rows_failed_total",
			Help: "同步写入 ES 失败的行数（进程累计）",
		}, func() float64 { _, _, failed := stats(); return float64(failed) }),
	)
}
