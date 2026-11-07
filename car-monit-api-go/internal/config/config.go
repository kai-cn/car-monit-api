// Package config 承载"配置加载与校验"。
//
// JAVA 对照: pro-business-api/src/main/resources/application.yml:1-297
//   - spring-boot 的 @ConfigurationProperties / @Value 注入
//
// 对应 Go 文件: internal/config/config.go
//
// 关键映射:
//
//	application.yml            → configs/config.yaml（同名同层级，YAML 键原样保留，便于逐行对照）
//	@Value("${server.port}")   → Config.Server.Port（Load() 之后由结构体直接取用）
//	@Profile("dev")            → --config=configs/config-dev.yaml / APP_ENV=dev
//	JSR-303 校验                → Load() 末尾的 Validate()（显式调用，无代理、无注解）
package config

import (
	"fmt"
	"path/filepath"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Config 是全量配置根对象。
//
// DIFF: Java 用几十个 @Value/@ConfigurationProperties 分散注入到各 Bean；Go 侧一次性装配成
// 一棵结构体树，由 main() 显式传给需要的组件——"谁能读配置"在编译期就一目了然。
type Config struct {
	Server        ServerConfig       `mapstructure:"server"`
	Datasource    DatasourceConfig   `mapstructure:"spring"`
	Redis         RedisConfig        `mapstructure:"redis"`
	Kafka         KafkaConfig        `mapstructure:"kafka"`
	Pulsar        PulsarConfig       `mapstructure:"pulsar"`
	RocketMQ      RocketMQConfig     `mapstructure:"rocketmq"`
	RabbitMQ      RabbitMQConfig     `mapstructure:"rabbitmq"`
	Elasticsearch ESConfig           `mapstructure:"elasticsearch"`
	Optimization  OptimizationConfig `mapstructure:"optimization"`
	MQ            MQConfig           `mapstructure:"mq"`
	Sync          SyncConfig         `mapstructure:"sync"`
	Consistency   ConsistencyConfig  `mapstructure:"consistency"`
	Reliability   ReliabilityConfig  `mapstructure:"reliability"`
	Detection     DetectionConfig    `mapstructure:"detection"`
	Monitoring    MonitoringConfig   `mapstructure:"monitoring"`
	Logging       LoggingConfig      `mapstructure:"logging"`
	App           AppConfig          `mapstructure:"app"`
}

// ServerConfig 对应 application.yml:1-4
//
// Go 侧新增项（Java 无对应，均带默认值以保持既有行为）：
//   - PprofEnabled：/debug/pprof/* 默认关闭（报告 02 P0-5，避免与业务同端口裸暴露）；
//   - MetricsEnabled：/metrics（Prometheus）默认开启（报告 02 P0-7）；
//   - ConsumerRequiredForReady：mqConsumer 不健康时 /readyz 是否返回 503，默认 false
//     （保持既有『MQ 非强依赖』语义，需要强约束的部署可打开）。
type ServerConfig struct {
	Port                     int    `mapstructure:"port"`
	ContextPath              string `mapstructure:"context-path"`
	Mode                     string `mapstructure:"mode"` // gin 模式：debug/release
	PprofEnabled             bool   `mapstructure:"pprof-enabled"`
	MetricsEnabled           bool   `mapstructure:"metrics-enabled"`
	ConsumerRequiredForReady bool   `mapstructure:"consumer-required-for-ready"`
	// RequestTimeout 为基础查询链路提供统一 ctx 超时（0 = 关闭，保持 Java 既有行为）。
	// 报告 02 P1-9：/base/*/list 之前完全依赖 pgx 默认行为，慢依赖会拖住 goroutine。
	RequestTimeout time.Duration `mapstructure:"request-timeout"`
}

// DatasourceConfig 对应 application.yml 的 spring: 节点（本项目的 spring 下只有 datasource）。
//
// DIFF: Java 侧动态数据源 + Druid 连接池 + p6spy SQL 打印是一整套 starter；Go 侧用
// database/sql 连接池（gorm/pgx）由 DriverDSN 直接描述，SQL 日志由 gorm logger 接管。
//
// 层层对齐是硬要求：application.yml 的真实路径是四层
//
//	spring . datasource . dynamic . datasource . master . url
//	  ↑         ↑           ↑          ↑          ↑
//	  Config  上面的     DataSourceNode  Dynamic   DynamicDatasource
//
// 少写任何一层，viper 的 Unmarshal 都不会报错，只是静静地给你零值 —— 然后 Validate
// 在启动时报「url 不能为空」，进程根本起不来。所以下面三级容器都不能合并。
type DatasourceConfig struct {
	Datasource DataSourceNode `mapstructure:"datasource"`
}

// DataSourceNode 对应 spring.datasource
type DataSourceNode struct {
	Dynamic DynamicConfig `mapstructure:"dynamic"`
}

// DynamicConfig 对应 spring.datasource.dynamic（dynamic-datasource starter 的容器节点，
// 与 p6spy / druid 同级）
type DynamicConfig struct {
	Datasource DynamicDatasource `mapstructure:"datasource"`
}

// Master 快捷访问 spring.datasource.dynamic.datasource.master。
// 调用方用 cfg.Datasource.Master()，不必写五层链式字段。
func (d DatasourceConfig) Master() MasterDatasource {
	return d.Datasource.Dynamic.Datasource.Master
}

// DynamicDatasource 对应 spring.datasource.dynamic.datasource
type DynamicDatasource struct {
	Master MasterDatasource `mapstructure:"master"`
}

// MasterDatasource 对应 application.yml:40-45
type MasterDatasource struct {
	URL      string `mapstructure:"url"`
	Username string `mapstructure:"username"`
	Password string `mapstructure:"password"`
	Driver   string `mapstructure:"driver-class-name"`
	// 以下为 Go 侧连接池参数（Druid initial-size/maxActive/maxWait 的等价物）
	MaxOpenConns    int           `mapstructure:"max-open-conns"`
	MaxIdleConns    int           `mapstructure:"max-idle-conns"`
	ConnMaxLifetime time.Duration `mapstructure:"conn-max-lifetime"`
	SlowThreshold   time.Duration `mapstructure:"slow-threshold"`
	LogSQL          bool          `mapstructure:"log-sql"`
}

// RedisConfig 对应 application.yml:46-59 + pro-base-common RedisConfiguration
type RedisConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	Password string `mapstructure:"password"`
	Database int    `mapstructure:"database"`
	PoolSize int    `mapstructure:"pool-size"`
}

// Addr 返回 go-redis 需要的 host:port
func (r RedisConfig) Addr() string { return fmt.Sprintf("%s:%d", r.Host, r.Port) }

// KafkaConfig 对应 application.yml:61-62, 145-148
type KafkaConfig struct {
	BootstrapServers string `mapstructure:"bootstrap-servers"`
	Topic            struct {
		SnapshotFlow string `mapstructure:"snapshot-flow"`
	} `mapstructure:"topic"`
	MaxRetryCount int    `mapstructure:"max-retry-count"`
	GroupID       string `mapstructure:"group-id"`
}

// PulsarConfig 对应 application.yml:64-102
//
// DIFF: 官方 apache/pulsar-client-go 需要 CGO + C++ 客户端，与"纯 Go 交叉编译"冲突。
// 本项目用 MessageBus 接口隔离（internal/mq），默认用 Kafka 实现同语义；
// 需要真 Pulsar 时替换 mq.NewPulsarBus 实现即可，业务代码零改动。详见 README「架构决策」。
type PulsarConfig struct {
	ServiceURL             string `mapstructure:"service-url"`
	Topic                  string `mapstructure:"topic"`
	ProducerName           string `mapstructure:"producer-name"`
	SendTimeoutMs          int    `mapstructure:"send-timeout-ms"`
	BatchMaxMessages       int    `mapstructure:"batch-max-messages"`
	BatchMaxPublishDelayMs int    `mapstructure:"batch-max-publish-delay-ms"`
	MaxPendingMessages     int    `mapstructure:"max-pending-messages"`
	SubscriptionName       string `mapstructure:"subscription-name"`
	ReceiverQueueSize      int    `mapstructure:"receiver-queue-size"`
	AckTimeoutMs           int    `mapstructure:"ack-timeout-ms"`
	MaxRetryTimes          int    `mapstructure:"max-retry-times"`
	IdempotentTTLSeconds   int    `mapstructure:"idempotent-ttl-seconds"`
	MaxRetryCount          int    `mapstructure:"max-retry-count"`
}

// RocketMQConfig 对应 application.yml:159-169（Go 侧同样需要架构决策，见 README）
type RocketMQConfig struct {
	NameServer string `mapstructure:"name-server"`
	Producer   struct {
		Group string `mapstructure:"group"`
	} `mapstructure:"producer"`
	Consumer struct {
		Group            string `mapstructure:"group"`
		MessageModel     string `mapstructure:"message-model"`
		ConsumeThreadMax int    `mapstructure:"consume-thread-max"`
	} `mapstructure:"consumer"`
}

// RabbitMQConfig 对应 application.yml:171-187
type RabbitMQConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	Username string `mapstructure:"username"`
	Password string `mapstructure:"password"`
	VHost    string `mapstructure:"virtual-host"`
	// Enabled 关闭时不会建立 AMQP 连接（本地开发默认关闭）
	Enabled bool `mapstructure:"enabled"`
}

// ESConfig 对应 application.yml:188-211
type ESConfig struct {
	Host              string        `mapstructure:"host"`
	Port              int           `mapstructure:"port"`
	Scheme            string        `mapstructure:"scheme"`
	Username          string        `mapstructure:"username"`
	Password          string        `mapstructure:"password"`
	ConnectionTimeout time.Duration `mapstructure:"connection-timeout"`
	SocketTimeout     time.Duration `mapstructure:"socket-timeout"`
	Index             struct {
		Snapshot   string `mapstructure:"snapshot"`
		Fee        string `mapstructure:"fee"`
		Trail      string `mapstructure:"trail"`
		Shards     int    `mapstructure:"shards"`
		Replicas   int    `mapstructure:"replicas"`
		AutoCreate bool   `mapstructure:"auto-create"`
		ILMPolicy  string `mapstructure:"ilm-policy"`
		AttachILM  bool   `mapstructure:"attach-ilm"`
	} `mapstructure:"index"`
}

// BaseURL 返回 http://host:port
func (e ESConfig) BaseURL() string {
	scheme := e.Scheme
	if scheme == "" {
		scheme = "http"
	}
	return fmt.Sprintf("%s://%s:%d", scheme, e.Host, e.Port)
}

// OptimizationConfig 对应 application.yml:213-230
type OptimizationConfig struct {
	// ScaleLevel 对应 @Value("${optimization.scale-level:LEVEL_10M}")
	ScaleLevel string `mapstructure:"scale-level"`
	Query      struct {
		TimeoutMs   int `mapstructure:"timeout-ms"`
		MaxWindow   int `mapstructure:"max-window"`
		ESForceDays int `mapstructure:"es-force-days"`
	} `mapstructure:"query"`
	Export struct {
		ScrollBatch        int    `mapstructure:"scroll-batch"`
		FileBatch          int    `mapstructure:"file-batch"`
		Dir                string `mapstructure:"dir"`
		ScrollKeepaliveMin int    `mapstructure:"scroll-keepalive-min"`
	} `mapstructure:"export"`
}

// MQConfig 对应 application.yml:232-239
type MQConfig struct {
	Topic struct {
		SnapshotFlow string `mapstructure:"snapshot-flow"`
	} `mapstructure:"topic"`
	DeadLetter struct {
		Exchange   string `mapstructure:"exchange"`
		Queue      string `mapstructure:"queue"`
		RoutingKey string `mapstructure:"routing-key"`
	} `mapstructure:"dead-letter"`
}

// SyncConfig 对应 application.yml:241-250
type SyncConfig struct {
	BatchSize               int  `mapstructure:"batch-size"`
	FullSyncEnabled         bool `mapstructure:"full-sync-enabled"`
	IncrementalSyncInterval int  `mapstructure:"incremental-sync-interval"`
}

// ConsistencyConfig 对应 application.yml:252-263
type ConsistencyConfig struct {
	Reconcile struct {
		Enabled       bool    `mapstructure:"enabled"`
		LookbackMonth int     `mapstructure:"lookback-months"`
		DriftRatio    float64 `mapstructure:"drift-ratio"`
		Cron          string  `mapstructure:"cron"`
	} `mapstructure:"reconcile"`
}

// ReliabilityConfig 对应 application.yml:265-274
type ReliabilityConfig struct {
	MessageTimeoutMs            int `mapstructure:"message-timeout-ms"`
	MaxRetryCount               int `mapstructure:"max-retry-count"`
	CompensationIntervalSeconds int `mapstructure:"compensation-interval-seconds"`
	AlertThresholdMs            int `mapstructure:"alert-threshold-ms"`
}

// DetectionConfig 对应 application.yml:276-283
type DetectionConfig struct {
	WindowSizeMinutes int     `mapstructure:"window-size-minutes"`
	IntervalMinutes   int     `mapstructure:"interval-minutes"`
	LossThresholdPct  float64 `mapstructure:"loss-threshold-percent"`
}

// MonitoringConfig 对应 application.yml:285-296
type MonitoringConfig struct {
	DeviceReportThresholdMs    int `mapstructure:"device-report-threshold-ms"`
	MessageTransferThresholdMs int `mapstructure:"message-transfer-threshold-ms"`
	DataProcessThresholdMs     int `mapstructure:"data-process-threshold-ms"`
	EndToEndThresholdMs        int `mapstructure:"end-to-end-threshold-ms"`
	StatsWindowMinutes         int `mapstructure:"stats-window-minutes"`
}

// LoggingConfig 对应 application.yml:122-126 + logback-spring.xml
type LoggingConfig struct {
	Level  string `mapstructure:"level"`  // root level
	Format string `mapstructure:"format"` // text | json
}

// AppConfig 对应 application.yml:141-142（isLocalhost / sysbaseUrl）
//
// Timezone 是 Go 侧新增：Java 由 JVM 默认时区决定（部署基线 Asia/Shanghai），
// Go 若依赖宿主机 TZ 会出现『DB 路径固定 +08:00、绑定/JSON 路径跟随 Local』的双轨
// （报告 01 Q7）。进程启动时按此项显式固定 time.Local，非法值在 Validate 阶段拒绝。
type AppConfig struct {
	Env        string `mapstructure:"env"`         // local | prod（原 isLocalhost）
	SysBaseURL string `mapstructure:"sysbase-url"` // 原 sysbaseUrl
	Timezone   string `mapstructure:"timezone"`    // 默认 Asia/Shanghai
}

// Load 读取配置文件并叠加环境变量。
//
// DIFF: Spring Boot 的配置优先级是 profile > 环境变量 > application.yml；这里用 Viper 的
// 显式顺序复刻：配置文件 → 环境变量（前缀 APP_，`.` 变 `_`）→ 代码默认值。
// 注意 Viper 不会做类型校验，所以 Load 末尾必须显式 Validate()。
func Load(path string) (*Config, error) {
	v := viper.New()
	v.SetConfigFile(path)
	v.SetConfigType("yaml")

	// defaults：与 application.yml 中注释掉的默认值保持一致（如 server.port: 9901）
	v.SetDefault("server.port", 9901)
	v.SetDefault("server.context-path", "/")
	v.SetDefault("server.mode", "release")
	// Go 侧新增开关：pprof 默认关（安全），metrics 默认开（可观测性），consumer 不阻断 readiness
	v.SetDefault("server.pprof-enabled", false)
	v.SetDefault("server.metrics-enabled", true)
	v.SetDefault("server.consumer-required-for-ready", false)
	v.SetDefault("server.request-timeout", 0) // 0 = 不启用（保持 Java 行为）
	v.SetDefault("app.timezone", "Asia/Shanghai")
	v.SetDefault("redis.host", "127.0.0.1")
	v.SetDefault("redis.port", 6379)
	v.SetDefault("redis.database", 0)
	v.SetDefault("redis.pool-size", 16)
	v.SetDefault("logging.level", "info")
	v.SetDefault("logging.format", "text")
	v.SetDefault("optimization.scale-level", "LEVEL_10M")
	v.SetDefault("optimization.query.timeout-ms", 30000)
	v.SetDefault("optimization.query.max-window", 10000)
	v.SetDefault("optimization.query.es-force-days", 30)
	v.SetDefault("optimization.export.scroll-batch", 2000)
	v.SetDefault("optimization.export.file-batch", 100000)
	v.SetDefault("optimization.export.dir", "/data/export")
	v.SetDefault("optimization.export.scroll-keepalive-min", 5)
	v.SetDefault("sync.batch-size", 1000)
	v.SetDefault("sync.incremental-sync-interval", 60000)
	v.SetDefault("reliability.message-timeout-ms", 30000)
	v.SetDefault("reliability.max-retry-count", 5)
	v.SetDefault("reliability.compensation-interval-seconds", 60)
	v.SetDefault("detection.window-size-minutes", 60)
	v.SetDefault("detection.interval-minutes", 30)
	v.SetDefault("detection.loss-threshold-percent", 5)
	v.SetDefault("monitoring.stats-window-minutes", 10)
	v.SetDefault("pulsar.idempotent-ttl-seconds", 86400)
	v.SetDefault("pulsar.max-retry-times", 3)

	// 环境变量：APP_SERVER_PORT 覆盖 server.port（对应 Spring 的 relaxed binding）
	//
	// 已知约束（报告 02 §3.3）：Viper 的 AutomaticEnv 只在 Unmarshal 时对
	// 『已出现在 yaml 或 defaults 中的键』生效。新增配置项必须同时写入 defaults
	// （或 yaml），否则 APP_XXX 注入会被静默丢弃 —— 加配置时请先看这一行。
	v.SetEnvPrefix("APP")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_", "-", "_"))
	v.AutomaticEnv()

	if err := v.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("读取配置 %s 失败: %w", path, err)
	}
	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("解析配置失败: %w", err)
	}
	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	return &cfg, nil
}

// Validate 手工校验必填项。
//
// DIFF: Java 的 @Validated + @NotBlank 由 Spring 在 Bean 初始化时自动执行；
// Go 没有容器，必须在 Load() 里显式调用，否则错误会推迟到第一次 DB 查询才暴露。
func (c *Config) Validate() error {
	var problems []string
	if c.Server.Port <= 0 {
		problems = append(problems, "server.port 必须 > 0")
	}
	if c.Datasource.Master().URL == "" {
		problems = append(problems, "spring.datasource.dynamic.datasource.master.url 不能为空")
	}
	if c.Datasource.Master().Username == "" {
		problems = append(problems, "spring.datasource.dynamic.datasource.master.username 不能为空")
	}
	if c.Redis.Host == "" {
		problems = append(problems, "redis.host 不能为空")
	}
	// 时区：非法值必须在启动阶段拒绝（报告 01 Q7：time.Local 是绑定/JSON/cron 的共同输入）
	if _, err := c.ResolveTimezone(); err != nil {
		problems = append(problems, err.Error())
	}
	// 导出目录：非 local 环境必须是绝对路径（报告 02 P1-8：Linux 上相对路径语义随 cwd 变化）
	if !strings.EqualFold(strings.TrimSpace(c.App.Env), "local") && c.App.Env != "" {
		if dir := strings.TrimSpace(c.Optimization.Export.Dir); dir != "" && !filepath.IsAbs(dir) {
			problems = append(problems, "optimization.export.dir 在非 local 环境必须为绝对路径，当前为 "+dir)
		}
	}
	if len(problems) > 0 {
		return fmt.Errorf("配置校验失败: %s", strings.Join(problems, "; "))
	}
	return nil
}

// ResolveTimezone 解析 app.timezone。
//
// PARITY: Java 侧时区由 JVM 默认时区（部署基线 Asia/Shanghai）决定，代码里没有显式设置；
// Go 侧必须显式固定 time.Local，否则绑定解析、JSON 反序列化、cron 触发会跟随宿主机 TZ，
// 与 DB 路径的 javaZone（固定 +08:00）形成双轨。
//
// 精简镜像可能没有 tzdata：Asia/Shanghai 退化为固定 +08:00（中国 1991 年后无夏令时，
// 与 model.javaZone 的兜底策略保持一致）；其他时区名缺 tzdata 则报错，避免静默用错时区。
func (c *Config) ResolveTimezone() (*time.Location, error) {
	name := strings.TrimSpace(c.App.Timezone)
	if name == "" {
		name = "Asia/Shanghai"
	}
	if loc, err := time.LoadLocation(name); err == nil {
		return loc, nil
	}
	if name == "Asia/Shanghai" || name == "PRC" {
		return time.FixedZone("Asia/Shanghai", 8*3600), nil
	}
	return nil, fmt.Errorf("app.timezone 非法或缺少 tzdata: %q", name)
}
