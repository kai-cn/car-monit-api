// Package db 承载数据库连接与事务。
//
// JAVA 对照:
//
//	pro-business-api/src/main/resources/application.yml:12-45（dynamic-datasource + Druid + p6spy）
//	pro-base-common/.../config/OrikaMapperConfig.java（无关，作为配置装配参考）
//	MyBatis-Plus 的 SqlSessionTemplate / @Transactional
//
// 对应 Go 文件: internal/db/db.go
//
// 关键映射:
//
//	动态数据源 master        → *gorm.DB 单实例（本项目只有 master；多数据源用 map[string]*gorm.DB）
//	Druid 连接池参数          → sql.DB 的 SetMaxOpenConns / SetMaxIdleConns / SetConnMaxLifetime
//	p6spy 打印完整 SQL        → gorm logger 的 Info + SlowThreshold
//	@Transactional           → db.Transaction(ctx, func(tx *gorm.DB) error)
//	JdbcTemplate.queryForObject（大表流式扫描） → 目前用 Raw(...).Scan 分批读取（游标分页，批 2000）；
//	                                           如需逐行回调的 Stream，请先补实现再改本行说明
package db

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log/slog"
	"net/url"
	"strings"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	gormlogger "gorm.io/gorm/logger"
	"gorm.io/gorm/schema"
)

// Client 是数据库门面。业务层只依赖它，不直接摸 gorm.DB，
// 这样"多数据源/读写分离"只在 db 包内演进。
type Client struct {
	gorm *gorm.DB
}

// Config 从 config.MasterDatasource 拍平后的连接参数
type Config struct {
	URL             string
	Username        string
	Password        string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration
	SlowThreshold   time.Duration
	LogSQL          bool
}

// Open 建立连接并做一次 Ping。
//
// DIFF: Spring Boot 的 DataSource 是懒加载的，配置错误往往在第一次查询才炸；
// 这里启动即 Ping，让"连不上库"在启动阶段暴露（fail fast），启动脚本的预期输出因此更确定。
func Open(ctx context.Context, cfg Config) (*Client, error) {
	dsn, err := BuildDSN(cfg)
	if err != nil {
		return nil, err
	}

	logLevel := gormlogger.Warn
	if cfg.LogSQL {
		logLevel = gormlogger.Info
	}
	// DIFF（R1）: 不再用 gormlogger.New + 单一 writer。gorm 的 Writer 接口只收一段
	// 已格式化的文本，无法区分"慢 SQL / SQL 错误 / 普通 SQL"；旧实现统一 slog.Debug，
	// 导致 slow-threshold: 5s 在生产 info 级别下完全静默。这里直接实现
	// gormlogger.Interface，在 Trace 里按 gorm 原始语义分流到 Error/Warn/Debug。
	gl := &gormSlogLogger{level: logLevel, slowThreshold: cfg.SlowThreshold}

	gdb, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: gl,
		// DIFF: Java 侧 mybatis-plus 的 table-underline=true 做驼峰→下划线；
		// Go 侧在模型上已经把 column tag 写死，故关闭自动复数化，避免 ods_xxx → ods_xxxs。
		NamingStrategy: newSchemaNamer(),
		// 关闭默认事务包装（单条写语句不需要额外 BEGIN/COMMIT，减少一次往返）
		SkipDefaultTransaction: true,
		// 告警级别：不使用 gorm 的 PrepareStmt 缓存，避免 GaussDB 预处理语句泄漏
		PrepareStmt: false,
	})
	if err != nil {
		return nil, fmt.Errorf("连接数据库失败: %w", err)
	}

	raw, err := gdb.DB()
	if err != nil {
		return nil, err
	}
	if cfg.MaxOpenConns > 0 {
		raw.SetMaxOpenConns(cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns > 0 {
		raw.SetMaxIdleConns(cfg.MaxIdleConns)
	}
	if cfg.ConnMaxLifetime > 0 {
		raw.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	}

	pingCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	if err := raw.PingContext(pingCtx); err != nil {
		return nil, fmt.Errorf("数据库 Ping 失败: %w", err)
	}

	return &Client{gorm: gdb.WithContext(ctx)}, nil
}

// ORM 返回 *gorm.DB（对应 MyBatis-Plus 的 SqlSession 入口）。
func (c *Client) ORM(ctx context.Context) *gorm.DB { return c.gorm.WithContext(ctx) }

// Raw 返回底层的 *sql.DB，供大表流式查询/COPY 使用（对应 JdbcTemplate 的原生能力）。
func (c *Client) Raw() (*sql.DB, error) { return c.gorm.DB() }

// Transaction 对应 Spring 的 @Transactional。
//
// DIFF: Java 靠 AOP 代理 + 方法注解声明事务边界，异常（RuntimeException）自动回滚；
// Go 必须把事务体写成闭包，**返回 error 即回滚**。注意：闭包里不要吞掉 error，
// 否则等价于 Java 里 catch 住异常却不抛——事务会提交。
func (c *Client) Transaction(ctx context.Context, fn func(tx *gorm.DB) error) error {
	return c.gorm.WithContext(ctx).Transaction(fn)
}

// Close 关闭连接池（对应 Spring 容器关闭时的 DataSource#close）
func (c *Client) Close() error {
	raw, err := c.gorm.DB()
	if err != nil {
		return err
	}
	return raw.Close()
}

// BuildDSN 把 Java 的 jdbc:postgresql:// URL 转成 pgx DSN。
//
// DIFF: Java 的 JDBC URL 带一堆 JDBC 专属参数（useUnicode/characterEncoding/...），
// pgx 不认识；这里只保留 PostgreSQL 原生参数（sslmode 等），其余丢弃。
func BuildDSN(cfg Config) (string, error) {
	raw := strings.TrimSpace(cfg.URL)
	raw = strings.TrimPrefix(raw, "jdbc:")
	if !strings.HasPrefix(raw, "postgresql://") && !strings.HasPrefix(raw, "postgres://") {
		return "", fmt.Errorf("仅支持 postgresql:// 或 jdbc:postgresql:// 形式的 url，当前为 %q", cfg.URL)
	}
	u, err := url.Parse(raw)
	if err != nil {
		return "", fmt.Errorf("解析数据库 url 失败: %w", err)
	}

	host := u.Hostname()
	port := u.Port()
	if port == "" {
		port = "5432"
	}
	dbname := strings.TrimPrefix(u.Path, "/")
	user := cfg.Username
	pass := cfg.Password
	if user == "" && u.User != nil {
		user = u.User.Username()
	}
	if pass == "" && u.User != nil {
		pass, _ = u.User.Password()
	}

	// 只透传 pgx 认识的查询参数
	keep := map[string]string{}
	for k, vs := range u.Query() {
		switch k {
		case "sslmode", "connect_timeout", "statement_cache_capacity", "default_query_exec_mode", "TimeZone":
			if len(vs) > 0 {
				keep[k] = vs[0]
			}
		}
	}
	if _, ok := keep["sslmode"]; !ok {
		keep["sslmode"] = "disable"
	}
	if _, ok := keep["TimeZone"]; !ok {
		keep["TimeZone"] = "Asia/Shanghai"
	}

	parts := []string{
		"host=" + host,
		"port=" + port,
		"user=" + user,
		"password=" + pass,
		"dbname=" + dbname,
	}
	for k, v := range keep {
		parts = append(parts, k+"="+v)
	}
	return strings.Join(parts, " "), nil
}

// schemaNamer 让 GORM 不做复数化、不做大小写转换——表名/列名全部以模型上的 tag 为准。
//
// DIFF: 这里不手写 schema.Namer 的 6 个方法（TableName/SchemaName/ColumnName/JoinTableName/
// IndexName/CheckerName），而是内嵌官方 NamingStrategy 并只改两个开关：
//
//	SingularTable: true → ods_xxx 不会被复数化成 ods_xxxs
//	NoLowerCase:   true → 保留 Java 侧的大小写混用列名（如 bigId / grade_level）
//
// 这是 Go 的「组合优于继承」在处理接口时的典型用法。
type schemaNamer struct{ schema.NamingStrategy }

// newSchemaNamer 构造表名策略（无复数、不改大小写）
func newSchemaNamer() schemaNamer {
	return schemaNamer{NamingStrategy: schema.NamingStrategy{
		SingularTable: true,
		NoLowerCase:   true,
	}}
}

// gormSlogLogger 把 GORM 的日志按级别转发到 slog（实现 gormlogger.Interface）。
//
// 行为对齐 gorm 默认 logger 的三条分支，只改输出目标与级别：
//   - 执行出错（ErrRecordNotFound 除外，与 IgnoreRecordNotFoundError=true 一致）→ slog.Error
//   - 超过 SlowThreshold → slog.Warn（生产 info 级别可见，作为大表慢查询的第一道防线）
//   - 其余 SQL → slog.Debug（LogSQL=true 时 level=Info，但仍只落 Debug，避免刷爆生产日志）
type gormSlogLogger struct {
	level         gormlogger.LogLevel
	slowThreshold time.Duration
}

// LogMode 对应 gorm 的日志级别切换（gorm 的 Session 可能调用）。
func (l *gormSlogLogger) LogMode(level gormlogger.LogLevel) gormlogger.Interface {
	cp := *l
	cp.level = level
	return &cp
}

// Info 对应 gorm 的通用 info 日志。
func (l *gormSlogLogger) Info(_ context.Context, msg string, data ...any) {
	if l.level >= gormlogger.Info {
		slog.Info(fmt.Sprintf(msg, data...), "component", "gorm")
	}
}

// Warn 对应 gorm 的通用 warn 日志。
func (l *gormSlogLogger) Warn(_ context.Context, msg string, data ...any) {
	if l.level >= gormlogger.Warn {
		slog.Warn(fmt.Sprintf(msg, data...), "component", "gorm")
	}
}

// Error 对应 gorm 的通用 error 日志。
func (l *gormSlogLogger) Error(_ context.Context, msg string, data ...any) {
	if l.level >= gormlogger.Error {
		slog.Error(fmt.Sprintf(msg, data...), "component", "gorm")
	}
}

// Trace 复刻 gormlogger.Trace 的分支顺序（错误 → 慢 SQL → 普通 SQL）。
//
// 注意 fc() 只能调用一次：它内部会做参数插值，重复调用是纯浪费。
func (l *gormSlogLogger) Trace(_ context.Context, begin time.Time, fc func() (string, int64), err error) {
	if l.level <= gormlogger.Silent {
		return
	}
	elapsed := time.Since(begin)
	costMs := float64(elapsed.Microseconds()) / 1000.0

	switch {
	case err != nil && !errors.Is(err, gormlogger.ErrRecordNotFound):
		sql, rows := fc()
		slog.Error("SQL 执行失败", "err", err, "costMs", costMs, "rows", rows, "sql", sql, "component", "gorm")
	case l.slowThreshold > 0 && elapsed > l.slowThreshold:
		sql, rows := fc()
		slog.Warn("慢 SQL", "threshold", l.slowThreshold.String(), "costMs", costMs,
			"rows", rows, "sql", sql, "component", "gorm")
	case l.level >= gormlogger.Info:
		sql, rows := fc()
		slog.Debug("SQL", "costMs", costMs, "rows", rows, "sql", sql, "component", "gorm")
	}
}
