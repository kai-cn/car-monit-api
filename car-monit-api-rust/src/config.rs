// 来源: pro-business-api/src/main/resources/application.yml
//       pro-business-api/src/main/resources/application-optimization.yml
// 职责: 承载全量配置；对应 Spring 的 @Value / @ConfigurationProperties 注入点。
// 对应关系:
//   server.*                     ↔ server.port / context-path
//   spring.datasource.dynamic.*  ↔ Druid + dynamic-datasource
//   spring.redis.*               ↔ Lettuce 连接池
//   spring.kafka.*               ↔ spring-kafka
//   spring.pulsar.*              ↔ pulsar-client
//   elasticsearch.*              ↔ RestHighLevelClient
//   optimization.*               ↔ @Value("${optimization.*}")
//   sync/consistency/reliability/detection/monitoring ↔ 各服务 @Value
//
// DIFF: Spring 在容器启动时把配置注入到每个 Bean；Rust 没有运行时 DI，统一在
// `Config::load()` 里反序列化成一棵结构体树，由 main() 显式传给需要的组件。
// 这样「谁能读配置」在编译期就确定，不需要启动后猜测。

use std::env;
use std::time::Duration;

use serde::Deserialize;

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct Config {
    pub server: ServerConfig,
    #[serde(rename = "spring")]
    pub datasource: DatasourceConfig,
    pub redis: RedisConfig,
    pub kafka: KafkaConfig,
    pub pulsar: PulsarConfig,
    pub rocketmq: RocketMqConfig,
    pub rabbitmq: RabbitMqConfig,
    pub elasticsearch: ElasticsearchConfig,
    pub optimization: OptimizationConfig,
    pub mq: MqConfig,
    pub sync: SyncConfig,
    pub consistency: ConsistencyConfig,
    pub reliability: ReliabilityConfig,
    pub detection: DetectionConfig,
    pub monitoring: MonitoringConfig,
    pub logging: LoggingConfig,
    #[serde(rename = "app")]
    pub app: AppConfig,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct ServerConfig {
    pub port: u16,
    #[serde(rename = "context-path")]
    pub context_path: String,
    pub mode: String,
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            port: 9901,
            context_path: "/".into(),
            mode: "release".into(),
        }
    }
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct DatasourceConfig {
    pub datasource: DatasourceNode,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct DatasourceNode {
    pub dynamic: DynamicConfig,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct DynamicConfig {
    pub datasource: DynamicDatasource,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct DynamicDatasource {
    pub master: MasterDatasource,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct MasterDatasource {
    pub url: String,
    pub username: String,
    pub password: String,
    #[serde(rename = "driver-class-name")]
    pub driver_class_name: String,
    // 以下四项是 Go/Rust 连接池参数，对应 Druid initial-size / maxActive / maxWait
    #[serde(rename = "max-open-conns")]
    pub max_open_conns: u32,
    #[serde(rename = "max-idle-conns")]
    pub max_idle_conns: u32,
    #[serde(rename = "conn-max-lifetime-seconds")]
    pub conn_max_lifetime_seconds: u64,
    #[serde(rename = "log-sql")]
    pub log_sql: bool,
}

impl Default for MasterDatasource {
    fn default() -> Self {
        Self {
            url: String::new(),
            username: String::new(),
            password: String::new(),
            driver_class_name: "org.postgresql.Driver".into(),
            max_open_conns: 20,
            max_idle_conns: 5,
            conn_max_lifetime_seconds: 1800,
            log_sql: false,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct RedisConfig {
    pub host: String,
    pub port: u16,
    pub password: String,
    pub database: i64,
    #[serde(rename = "pool-size")]
    pub pool_size: u32,
}

impl Default for RedisConfig {
    fn default() -> Self {
        Self {
            host: "127.0.0.1".into(),
            port: 6379,
            password: String::new(),
            database: 0,
            pool_size: 16,
        }
    }
}

impl RedisConfig {
    pub fn addr(&self) -> String {
        format!("{}:{}", self.host, self.port)
    }
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct KafkaConfig {
    #[serde(rename = "bootstrap-servers")]
    pub bootstrap_servers: String,
    pub topic: KafkaTopic,
    #[serde(rename = "max-retry-count")]
    pub max_retry_count: i32,
    #[serde(rename = "group-id")]
    pub group_id: String,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct KafkaTopic {
    #[serde(rename = "snapshot-flow")]
    pub snapshot_flow: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct PulsarConfig {
    #[serde(rename = "service-url")]
    pub service_url: String,
    pub topic: String,
    #[serde(rename = "producer-name")]
    pub producer_name: String,
    #[serde(rename = "send-timeout-ms")]
    pub send_timeout_ms: u64,
    #[serde(rename = "batch-max-messages")]
    pub batch_max_messages: u32,
    #[serde(rename = "batch-max-publish-delay-ms")]
    pub batch_max_publish_delay_ms: u64,
    #[serde(rename = "max-pending-messages")]
    pub max_pending_messages: u32,
    #[serde(rename = "subscription-name")]
    pub subscription_name: String,
    #[serde(rename = "receiver-queue-size")]
    pub receiver_queue_size: u32,
    #[serde(rename = "ack-timeout-ms")]
    pub ack_timeout_ms: u64,
    #[serde(rename = "max-retry-times")]
    pub max_retry_times: i32,
    #[serde(rename = "idempotent-ttl-seconds")]
    pub idempotent_ttl_seconds: u64,
    #[serde(rename = "max-retry-count")]
    pub max_retry_count: i32,
}

impl Default for PulsarConfig {
    fn default() -> Self {
        Self {
            service_url: "pulsar://localhost:6650".into(),
            topic: "persistent://public/default/ods-rt-szdn-snapshot-flow".into(),
            producer_name: "car-monit-producer".into(),
            send_timeout_ms: 30_000,
            batch_max_messages: 1000,
            batch_max_publish_delay_ms: 10,
            max_pending_messages: 10_000,
            subscription_name: "ods-rt-szdn-snapshot-flow-sub".into(),
            receiver_queue_size: 1000,
            ack_timeout_ms: 60_000,
            max_retry_times: 3,
            idempotent_ttl_seconds: 86_400,
            max_retry_count: 10,
        }
    }
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct RocketMqConfig {
    #[serde(rename = "name-server")]
    pub name_server: String,
    pub producer: RocketMqProducer,
    pub consumer: RocketMqConsumer,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct RocketMqProducer {
    pub group: String,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct RocketMqConsumer {
    pub group: String,
    #[serde(rename = "message-model")]
    pub message_model: String,
    #[serde(rename = "consume-thread-max")]
    pub consume_thread_max: i32,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct RabbitMqConfig {
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password: String,
    #[serde(rename = "virtual-host")]
    pub virtual_host: String,
    pub enabled: bool,
}

impl Default for RabbitMqConfig {
    fn default() -> Self {
        Self {
            host: "localhost".into(),
            port: 5672,
            username: "guest".into(),
            password: "guest".into(),
            virtual_host: "/".into(),
            enabled: false,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct ElasticsearchConfig {
    pub host: String,
    pub port: u16,
    pub scheme: String,
    pub username: String,
    pub password: String,
    #[serde(rename = "connection-timeout-ms")]
    pub connection_timeout_ms: u64,
    #[serde(rename = "socket-timeout-ms")]
    pub socket_timeout_ms: u64,
    pub index: EsIndexConfig,
}

impl Default for ElasticsearchConfig {
    fn default() -> Self {
        Self {
            host: "localhost".into(),
            port: 9200,
            scheme: "http".into(),
            username: "elastic".into(),
            password: "changeme".into(),
            connection_timeout_ms: 30_000,
            socket_timeout_ms: 30_000,
            index: EsIndexConfig::default(),
        }
    }
}

impl ElasticsearchConfig {
    pub fn base_url(&self) -> String {
        let scheme = if self.scheme.is_empty() {
            "http"
        } else {
            &self.scheme
        };
        format!("{}://{}:{}", scheme, self.host, self.port)
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct EsIndexConfig {
    pub snapshot: String,
    pub fee: String,
    pub trail: String,
    pub shards: u32,
    pub replicas: u32,
    #[serde(rename = "auto-create")]
    pub auto_create: bool,
    #[serde(rename = "ilm-policy")]
    pub ilm_policy: String,
    #[serde(rename = "attach-ilm")]
    pub attach_ilm: bool,
}

impl Default for EsIndexConfig {
    fn default() -> Self {
        Self {
            snapshot: "snapshot_flow".into(),
            fee: "fee_records".into(),
            trail: "trail_fitting".into(),
            shards: 6,
            replicas: 1,
            auto_create: false,
            ilm_policy: "car_monit_ilm_policy".into(),
            attach_ilm: false,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct OptimizationConfig {
    #[serde(rename = "scale-level")]
    pub scale_level: String,
    pub query: OptimizationQuery,
    pub export: OptimizationExport,
}

impl Default for OptimizationConfig {
    fn default() -> Self {
        Self {
            scale_level: "LEVEL_10M".into(),
            query: OptimizationQuery::default(),
            export: OptimizationExport::default(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct OptimizationQuery {
    #[serde(rename = "timeout-ms")]
    pub timeout_ms: u64,
    #[serde(rename = "max-window")]
    pub max_window: i64,
    #[serde(rename = "es-force-days")]
    pub es_force_days: i64,
}

impl Default for OptimizationQuery {
    fn default() -> Self {
        Self {
            timeout_ms: 30_000,
            max_window: 10_000,
            es_force_days: 30,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct OptimizationExport {
    #[serde(rename = "scroll-batch")]
    pub scroll_batch: i64,
    #[serde(rename = "file-batch")]
    pub file_batch: i64,
    pub dir: String,
    #[serde(rename = "scroll-keepalive-min")]
    pub scroll_keepalive_min: u64,
}

impl Default for OptimizationExport {
    fn default() -> Self {
        Self {
            scroll_batch: 2000,
            file_batch: 100_000,
            dir: "/data/export".into(),
            scroll_keepalive_min: 5,
        }
    }
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct MqConfig {
    pub topic: MqTopic,
    #[serde(rename = "dead-letter")]
    pub dead_letter: MqDeadLetter,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct MqTopic {
    #[serde(rename = "snapshot-flow")]
    pub snapshot_flow: String,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default)]
pub struct MqDeadLetter {
    pub exchange: String,
    pub queue: String,
    #[serde(rename = "routing-key")]
    pub routing_key: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct SyncConfig {
    #[serde(rename = "batch-size")]
    pub batch_size: i64,
    #[serde(rename = "full-sync-enabled")]
    pub full_sync_enabled: bool,
    #[serde(rename = "incremental-sync-interval")]
    pub incremental_sync_interval_ms: u64,
}

impl Default for SyncConfig {
    fn default() -> Self {
        Self {
            batch_size: 1000,
            full_sync_enabled: true,
            incremental_sync_interval_ms: 60_000,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct ConsistencyConfig {
    pub reconcile: ReconcileConfig,
}

impl Default for ConsistencyConfig {
    fn default() -> Self {
        Self {
            reconcile: ReconcileConfig::default(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct ReconcileConfig {
    pub enabled: bool,
    #[serde(rename = "lookback-months")]
    pub lookback_months: i32,
    #[serde(rename = "drift-ratio")]
    pub drift_ratio: f64,
    pub cron: String,
}

impl Default for ReconcileConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            lookback_months: 3,
            drift_ratio: 0.01,
            cron: "0 30 2 * * ?".into(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct ReliabilityConfig {
    #[serde(rename = "message-timeout-ms")]
    pub message_timeout_ms: u64,
    #[serde(rename = "max-retry-count")]
    pub max_retry_count: i32,
    #[serde(rename = "compensation-interval-seconds")]
    pub compensation_interval_seconds: u64,
    #[serde(rename = "alert-threshold-ms")]
    pub alert_threshold_ms: u64,
}

impl Default for ReliabilityConfig {
    fn default() -> Self {
        Self {
            message_timeout_ms: 30_000,
            max_retry_count: 5,
            compensation_interval_seconds: 60,
            alert_threshold_ms: 10_000,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct DetectionConfig {
    #[serde(rename = "window-size-minutes")]
    pub window_size_minutes: i64,
    #[serde(rename = "interval-minutes")]
    pub interval_minutes: i64,
    #[serde(rename = "loss-threshold-percent")]
    pub loss_threshold_percent: f64,
}

impl Default for DetectionConfig {
    fn default() -> Self {
        Self {
            window_size_minutes: 60,
            interval_minutes: 30,
            loss_threshold_percent: 5.0,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct MonitoringConfig {
    #[serde(rename = "device-report-threshold-ms")]
    pub device_report_threshold_ms: u64,
    #[serde(rename = "message-transfer-threshold-ms")]
    pub message_transfer_threshold_ms: u64,
    #[serde(rename = "data-process-threshold-ms")]
    pub data_process_threshold_ms: u64,
    #[serde(rename = "end-to-end-threshold-ms")]
    pub end_to_end_threshold_ms: u64,
    #[serde(rename = "stats-window-minutes")]
    pub stats_window_minutes: i64,
}

impl Default for MonitoringConfig {
    fn default() -> Self {
        Self {
            device_report_threshold_ms: 5000,
            message_transfer_threshold_ms: 3000,
            data_process_threshold_ms: 10_000,
            end_to_end_threshold_ms: 30_000,
            stats_window_minutes: 10,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct LoggingConfig {
    pub level: String,
    pub format: String,
}

impl Default for LoggingConfig {
    fn default() -> Self {
        Self {
            level: "info".into(),
            format: "text".into(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct AppConfig {
    pub env: String,
    #[serde(rename = "sysbase-url")]
    pub sysbase_url: String,
    /// JS 侧配置里没有；Rust 侧用于显式开关后台消费者（默认打开，与 Java 一致）
    #[serde(rename = "consumer-enabled")]
    pub consumer_enabled: bool,
    #[serde(rename = "enable-scheduler")]
    pub enable_scheduler: bool,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            env: "local".into(),
            sysbase_url: "http://223.84.150.189:26066/prod-api".into(),
            consumer_enabled: true,
            enable_scheduler: true,
        }
    }
}

/// 环境变量覆盖：APP_* 采用单下划线命名（与 .env.example 一致）。
/// 对应 Spring Boot 的 relaxed binding；带连字符的键在这里显式映射，避免 config crate 的
/// 嵌套分隔符把 `context-path` 误解成三层。
fn apply_env_overrides(cfg: &mut Config) {
    fn set<T: std::str::FromStr>(key: &str, f: impl FnOnce(T)) {
        if let Ok(raw) = env::var(key) {
            if let Ok(v) = raw.parse::<T>() {
                f(v);
            }
        }
    }
    set("APP_SERVER_PORT", |v: u16| cfg.server.port = v);
    if let Ok(v) = env::var("APP_SERVER_CONTEXT_PATH") {
        cfg.server.context_path = v;
    }
    set("APP_SERVER_MODE", |v: String| cfg.server.mode = v);

    if let Ok(v) = env::var("APP_SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_URL") {
        cfg.datasource.datasource.dynamic.datasource.master.url = v;
    }
    if let Ok(v) = env::var("APP_SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME") {
        cfg.datasource.datasource.dynamic.datasource.master.username = v;
    }
    if let Ok(v) = env::var("APP_SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD") {
        cfg.datasource.datasource.dynamic.datasource.master.password = v;
    }
    set(
        "APP_SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_MAX_OPEN_CONNS",
        |v: u32| {
            cfg.datasource
                .datasource
                .dynamic
                .datasource
                .master
                .max_open_conns = v
        },
    );
    set(
        "APP_SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_MAX_IDLE_CONNS",
        |v: u32| {
            cfg.datasource
                .datasource
                .dynamic
                .datasource
                .master
                .max_idle_conns = v
        },
    );

    if let Ok(v) = env::var("APP_REDIS_HOST") {
        cfg.redis.host = v;
    }
    set("APP_REDIS_PORT", |v: u16| cfg.redis.port = v);
    if let Ok(v) = env::var("APP_REDIS_PASSWORD") {
        cfg.redis.password = v;
    }
    set("APP_REDIS_DATABASE", |v: i64| cfg.redis.database = v);

    if let Ok(v) = env::var("APP_KAFKA_BOOTSTRAP_SERVERS") {
        cfg.kafka.bootstrap_servers = v;
    }
    if let Ok(v) = env::var("APP_KAFKA_TOPIC_SNAPSHOT_FLOW") {
        cfg.kafka.topic.snapshot_flow = v;
    }
    if let Ok(v) = env::var("APP_KAFKA_GROUP_ID") {
        cfg.kafka.group_id = v;
    }

    if let Ok(v) = env::var("APP_ELASTICSEARCH_HOST") {
        cfg.elasticsearch.host = v;
    }
    set("APP_ELASTICSEARCH_PORT", |v: u16| {
        cfg.elasticsearch.port = v
    });
    if let Ok(v) = env::var("APP_ELASTICSEARCH_SCHEME") {
        cfg.elasticsearch.scheme = v;
    }
    if let Ok(v) = env::var("APP_ELASTICSEARCH_USERNAME") {
        cfg.elasticsearch.username = v;
    }
    if let Ok(v) = env::var("APP_ELASTICSEARCH_PASSWORD") {
        cfg.elasticsearch.password = v;
    }
    if let Ok(v) = env::var("APP_ELASTICSEARCH_INDEX_SNAPSHOT") {
        cfg.elasticsearch.index.snapshot = v;
    }
    if let Ok(v) = env::var("APP_ELASTICSEARCH_INDEX_FEE") {
        cfg.elasticsearch.index.fee = v;
    }
    if let Ok(v) = env::var("APP_ELASTICSEARCH_INDEX_TRAIL") {
        cfg.elasticsearch.index.trail = v;
    }

    if let Ok(v) = env::var("APP_OPTIMIZATION_EXPORT_DIR") {
        cfg.optimization.export.dir = v;
    }
    if let Ok(v) = env::var("APP_OPTIMIZATION_SCALE_LEVEL") {
        cfg.optimization.scale_level = v;
    }

    if let Ok(v) = env::var("APP_APP_ENV") {
        cfg.app.env = v;
    }
    if let Ok(v) = env::var("APP_CONSUMER_ENABLED") {
        cfg.app.consumer_enabled = matches!(v.to_ascii_lowercase().as_str(), "1" | "true" | "yes");
    }
    if let Ok(v) = env::var("APP_ENABLE_SCHEDULER") {
        cfg.app.enable_scheduler = matches!(v.to_ascii_lowercase().as_str(), "1" | "true" | "yes");
    }
}

impl Config {
    pub fn master(&self) -> &MasterDatasource {
        &self.datasource.datasource.dynamic.datasource.master
    }

    pub fn incremental_interval(&self) -> Duration {
        Duration::from_millis(self.sync.incremental_sync_interval_ms)
    }

    /// 等价于 Spring Boot 的配置加载顺序：默认值 → 配置文件 → 环境变量。
    /// 环境变量前缀 APP_，`.`/`-` 都映射为 `_`。
    pub fn load(path: Option<&str>) -> anyhow::Result<Self> {
        let path = path
            .map(|s| s.to_string())
            .or_else(|| env::var("CAR_MONIT_CONFIG").ok())
            .unwrap_or_else(|| "config/application.yaml".to_string());

        let builder = ::config::Config::builder()
            .add_source(::config::File::with_name(&path).required(false))
            .add_source(
                ::config::Environment::with_prefix("APP")
                    .separator("__")
                    .try_parsing(true)
                    .list_separator(","),
            );

        let raw = builder
            .build()
            .map_err(|e| anyhow::anyhow!("读取配置 {} 失败: {}", path, e))?;
        let mut cfg: Config = raw
            .try_deserialize()
            .map_err(|e| anyhow::anyhow!("解析配置失败: {}", e))?;
        apply_env_overrides(&mut cfg);

        // 支持 application.yml 中的平铺键（kafka.topic / isLocalhost / sysbaseUrl / redis host 等）
        if cfg.app.env == "local" {
            if let Ok(v) = env::var("isLocalhost") {
                cfg.app.env = v;
            }
        }
        cfg.validate()?;
        Ok(cfg)
    }

    /// 对应 JSR-303 / @Validated：没有容器，所以在加载末尾显式校验。
    pub fn validate(&self) -> anyhow::Result<()> {
        let mut problems = Vec::new();
        if self.server.port == 0 {
            problems.push("server.port 必须 > 0".to_string());
        }
        if self.master().url.trim().is_empty() {
            problems.push("spring.datasource.dynamic.datasource.master.url 不能为空".to_string());
        }
        if self.master().username.trim().is_empty() {
            problems
                .push("spring.datasource.dynamic.datasource.master.username 不能为空".to_string());
        }
        if self.redis.host.trim().is_empty() {
            problems.push("redis.host 不能为空".to_string());
        }
        if !problems.is_empty() {
            anyhow::bail!("配置校验失败: {}", problems.join("; "));
        }
        Ok(())
    }
}
