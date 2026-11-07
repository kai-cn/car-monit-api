// Command api 是 Java 后端（pro-business-api）的 Go 等价进程入口。
//
// JAVA 对照:
//
//	pro-business-api/src/main/java/com/ruoyi/ProApplication.java（@SpringBootApplication + main）
//	pro-business-api/src/main/resources/application.yml:1-297（server.port / context-path / 各段配置）
//	Spring 容器：Bean 的构造顺序 = 依赖图拓扑序（Service 依赖 Mapper，Mapper 依赖 DataSource）
//	@PostConstruct / @PreDestroy（消费者启动、连接释放、线程池关闭）
//
// 类/职责: 显式装配「配置 → 基础设施 → Repo → Service → Handler → Router → 定时任务 → HTTP Server」
// 对应 Go 文件: cmd/api/main.go
//
// 关键映射:
//
//	@SpringBootApplication 的组件扫描   → 下面 5 个 build 函数里的显式 new（没有反射，没有魔法）
//	@Autowired 的字段注入               → 构造函数参数（依赖缺失 = 编译失败，而不是启动期 NPE）
//	@PostConstruct                      → startBackground()：消费者、同步任务、调度器
//	@PreDestroy                         → shutdown()：逆序释放，先停入口再断连接
//	SpringApplication.run 阻塞          → http.Server.ListenAndServe + signal.NotifyContext
//
// DIFF: Spring Boot 的启动顺序由容器决定，出问题时只能看 "Bean 初始化顺序" 日志；
// Go 的 main() 就是一张清单，谁先谁后一目了然 —— 这也是本次迁移最大的可维护性收益。
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/db"
	"github.com/ruoyi/car-monit-api-go/internal/es"
	"github.com/ruoyi/car-monit-api-go/internal/handler"
	"github.com/ruoyi/car-monit-api-go/internal/logging"
	"github.com/ruoyi/car-monit-api-go/internal/mq"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
	"github.com/ruoyi/car-monit-api-go/internal/router"
	"github.com/ruoyi/car-monit-api-go/internal/scheduler"
	"github.com/ruoyi/car-monit-api-go/internal/service"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// 进程内固定版本号（Java 侧对应 pom.xml 的 <version>，这里用 ldflags 注入：
// go build -ldflags "-X main.version=1.0.0"）。默认值与 Java 侧一致。
var version = "1.0.0"

func main() {
	var (
		configPath  = flag.String("config", "configs/config.yaml", "配置文件路径（对应 application.yml）")
		showVersion = flag.Bool("version", false, "打印版本号后退出")
	)
	flag.Parse()

	if *showVersion {
		fmt.Println("car-monit-api-go", version)
		return
	}
	if err := run(*configPath); err != nil {
		fmt.Fprintln(os.Stderr, "启动失败:", err)
		os.Exit(1)
	}
}

func run(configPath string) error {
	// ---- 1. 配置（application.yml 的等价物）----
	cfg, err := config.Load(configPath)
	if err != nil {
		return err
	}

	// ---- 2. 日志（logback-spring.xml 的等价物）----
	lg := logging.Init(cfg.Logging.Level, cfg.Logging.Format)
	slog.SetDefault(lg)
	slog.Info("开始装配应用", "version", version, "config", configPath, "env", cfg.App.Env)

	// ctx 在收到 Ctrl+C / SIGTERM 时取消，向下传递到消费者、调度器与 HTTP Server。
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// ---- 3. 基础设施 ----
	dbClient, err := openDB(ctx, cfg)
	if err != nil {
		return err
	}
	cacheClient, err := openCache(ctx, cfg)
	if err != nil {
		_ = dbClient.Close()
		return err
	}
	esClient := openES(cfg) // ES 不是强依赖：连不上只在 /readyz 里报 DOWN

	// ---- 4. Repo（MyBatis Mapper 的等价物）----
	repos := newRepos(dbClient)

	// ---- 5. Service ----
	dict := service.NewDictRegistry(repos.LocationDict, repos.GantryIP, repos.Gantry,
		repos.TollStationIP, repos.Toll, repos.Section, cacheClient)
	sysUtil := service.NewSysUtilService(repos.TrailTracks, repos.VehicleWeight, repos.SnapshotFlow,
		repos.ProvCapture, repos.Fwqclls, repos.StationCapture, repos.FeeRecords,
		repos.FeeStationEnter, repos.FeeStationExit, dict, cacheClient, cfg.App.Env)

	unifiedQuery := service.NewUnifiedQueryService(esClient, dbClient, cfg.Optimization, cfg.Elasticsearch)
	largeQuery := service.NewLargeScaleQueryService(esClient, unifiedQuery, cfg.Optimization)
	exportSvc := service.NewUnifiedExportService(esClient, unifiedQuery, cfg.Optimization)
	progressive := service.NewProgressiveQueryService(cfg.Optimization, repos.SnapshotFlow,
		repos.FeeRecords, repos.TrailFitting, cacheClient, esClient)

	syncSvc := service.NewLargeScaleSyncService(esClient, cacheClient, cfg.Elasticsearch, cfg.Sync, 1,
		repos.SnapshotFlow, repos.FeeRecords, repos.TrailFitting)

	// 消息总线：Brokers 为空时整体降级（本地开发不必起 Kafka）
	bus := openBus(cfg)
	reliability := service.NewDataReliabilityService(bus, cacheClient, repos.KafkaRecord, cfg.Reliability)
	lossDetect := service.NewDataLossDetectionService(repos.SnapshotFlow, cacheClient, reliability, cfg.Detection)
	delayMonitor := service.NewDelayMonitoringService(cacheClient, cfg.Monitoring)
	producer := service.NewKafkaProducerService(bus, repos.KafkaRecord, reliability, lossDetect, delayMonitor, cfg.Kafka)
	multiSource := service.NewMultiSourceDataFlowService(cacheClient)
	consistency := service.NewGaussEsConsistencyService(esClient, syncSvc, unifiedQuery, cfg.Consistency,
		repos.SnapshotFlow, repos.FeeRecords, repos.TrailFitting)
	snapshotSync := service.NewSnapshotFlowSyncService(repos.SnapshotFlow, producer, cacheClient, cfg.Sync)
	dataConsumer := service.NewSnapshotFlowConsumer(bus, repos.SnapshotFlow, esClient,
		cfg.Elasticsearch.Index.Snapshot, cacheClient, cfg.Pulsar.IdempotentTTLSeconds)

	// 字典缓存预热（Java 侧由 updateRedis 的 @PostConstruct 触发）。
	// DIFF: Spring 里 updateRedis 失败会让整个应用启动失败；这里失败只告警，
	// 否则"字典表还没建"就会导致服务完全无法启动（本地开发体验极差）。
	if err := dict.RefreshAll(ctx); err != nil {
		slog.Warn("字典缓存预热失败，服务继续启动（按需回源）", "err", err)
	}

	// ---- 6. Handler ----
	baseDeps := &handler.BaseDeps{
		Fwqjcxx: repos.Fwqjcxx, Sfsjcxx: repos.Sfsjcxx, Sfzjcxx: repos.Sfzjcxx,
		Fwqclls: repos.Fwqclls, FeeGantry: repos.FeeGantry, FeeRecords: repos.FeeRecords,
		FeeStationEnter: repos.FeeStationEnter, FeeStationExit: repos.FeeStationExit,
		SnapshotFlow: repos.SnapshotFlow, ProvCapture: repos.ProvCapture, StationCapture: repos.StationCapture,
		Gantry: repos.Gantry, GantryIP: repos.GantryIP, VehicleWeight: repos.VehicleWeight,
		Section: repos.Section, Toll: repos.Toll, TollStationIP: repos.TollStationIP,
		Org: repos.Org, TrailTracks: repos.TrailTracks,
		Dict: dict, Cache: cacheClient, SysUtil: sysUtil,
	}
	queryDeps := &handler.QueryDeps{
		Large: largeQuery, Query: unifiedQuery, Export: exportSvc, Progressive: progressive, Sync: syncSvc,
	}
	sysUtilDeps := &handler.SysUtilDeps{Service: sysUtil, Cache: cacheClient}
	// SelfTestDeps 除字典外还要 SysUtil：/syncCurrentTrack 与 /syncHistroyTrack 调的就是
	// TrackTask 那两个方法，Java 侧是同一个 ISysUtilService Bean。
	selfTestDeps := &handler.SelfTestDeps{Dict: dict, SysUtil: sysUtil}

	// ---- 7. Router ----
	// R2 修复：consumerUp 由"启动过一次"改为"读消费循环的真实心跳"（见 mq.Heartbeat）。
	// 未配置 Kafka 时 dataConsumer.Healthy() 恒为 false，/readyz 会显示 mqConsumer=DOWN。
	engine := router.New(router.Options{
		Config: cfg, Base: baseDeps, Query: queryDeps, SysUtil: sysUtilDeps, SelfTest: selfTestDeps,
		Health: &router.Health{
			DB:       func(c context.Context) error { return pingDB(c, dbClient) },
			Cache:    func(c context.Context) error { return cacheClient.Raw().Ping(c).Err() },
			ES:       func(c context.Context) error { return pingES(c, esClient) },
			Consumer: dataConsumer.Healthy,
		},
	})

	// ---- 8. 后台任务（@PostConstruct 的等价物）----
	tasks := startBackground(ctx, startDeps{
		cfg: cfg, bus: bus, producer: producer, snapshotSync: snapshotSync, largeSync: syncSvc,
		consumer: dataConsumer, dict: dict, multiSource: multiSource,
		loss: lossDetect, delay: delayMonitor, reliability: reliability, consistency: consistency,
		sysUtil: sysUtil, export: exportSvc, largeQuery: largeQuery,
	})

	// ---- 9. HTTP Server ----
	srv := &http.Server{
		Addr:              fmt.Sprintf(":%d", cfg.Server.Port),
		Handler:           engine,
		ReadHeaderTimeout: 10 * time.Second,
		// DIFF: Java 的 spring.mvc.async.request-timeout 只管异步请求；
		// 这里不设 WriteTimeout —— 导出接口靠 ES scroll 出几百 MB 文件，固定超时会误杀。
		IdleTimeout: 120 * time.Second,
	}
	errCh := make(chan error, 1)
	go func() {
		slog.Info("HTTP 服务已启动", "addr", srv.Addr, "mode", cfg.Server.Mode,
			"contextPath", cfg.Server.ContextPath)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	select {
	case err := <-errCh:
		return fmt.Errorf("HTTP 服务异常: %w", err)
	case <-ctx.Done():
		slog.Info("收到退出信号，开始优雅关闭")
	}

	return shutdown(srv, tasks, dbClient, cacheClient)
}

// ---------------------------------------------------------------- 装配辅助

// repoSet 把 22 个 Repo 打成一个包，避免在 run() 里出现 22 个局部变量。
//
// DIFF: Java 的 Mapper 由 @MapperScan 批量注册；这里显式列字段，等价于“Mapper 清单”。
type repoSet struct {
	Fwqjcxx         *repo.DwdLcztFwqjcxxRepo
	Sfsjcxx         *repo.DwdLcztSfsjcxxRepo
	Sfzjcxx         *repo.DwdLcztSfzjcxxRepo
	Fwqclls         *repo.OdsCxztFwqcllsRepo
	FeeGantry       *repo.OdsLwzxsfsjFeeGantryFusion01Repo
	FeeRecords      *repo.OdsLwzxsfsjFeeRecords01Repo
	FeeStationEnter *repo.OdsLwzxsfsjFeeStationEnter01Repo
	FeeStationExit  *repo.OdsLwzxsfsjFeeStationExit01Repo
	SnapshotFlow    *repo.OdsRtSzdnSnapshotFlowAddcodeRepo
	ProvCapture     *repo.OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo
	StationCapture  *repo.OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo
	Gantry          *repo.OdsSzdnGantryRepo
	GantryIP        *repo.OdsSzdnGantryIpRepo
	VehicleWeight   *repo.OdsSzdnProvinceBorderVehicleWeightNewstructureRepo
	Section         *repo.OdsSzdnSectionRepo
	Toll            *repo.OdsSzdnTollRepo
	TollStationIP   *repo.OdsSzdnTollStationIpRepo
	Org             *repo.OdsYhglVBaseOrgRepo
	TrailTracks     *repo.ZdataTrailTracksRepo
	TrailFitting    *repo.ZdataTrailFittingRepo
	LocationDict    *repo.ZdataLocationDictRepo
	KafkaRecord     *repo.KafkaMessageRecordRepo
}

func newRepos(c *db.Client) *repoSet {
	return &repoSet{
		Fwqjcxx:         repo.NewDwdLcztFwqjcxxRepo(c),
		Sfsjcxx:         repo.NewDwdLcztSfsjcxxRepo(c),
		Sfzjcxx:         repo.NewDwdLcztSfzjcxxRepo(c),
		Fwqclls:         repo.NewOdsCxztFwqcllsRepo(c),
		FeeGantry:       repo.NewOdsLwzxsfsjFeeGantryFusion01Repo(c),
		FeeRecords:      repo.NewOdsLwzxsfsjFeeRecords01Repo(c),
		FeeStationEnter: repo.NewOdsLwzxsfsjFeeStationEnter01Repo(c),
		FeeStationExit:  repo.NewOdsLwzxsfsjFeeStationExit01Repo(c),
		SnapshotFlow:    repo.NewOdsRtSzdnSnapshotFlowAddcodeRepo(c),
		ProvCapture:     repo.NewOdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo(c),
		StationCapture:  repo.NewOdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo(c),
		Gantry:          repo.NewOdsSzdnGantryRepo(c),
		GantryIP:        repo.NewOdsSzdnGantryIpRepo(c),
		VehicleWeight:   repo.NewOdsSzdnProvinceBorderVehicleWeightNewstructureRepo(c),
		Section:         repo.NewOdsSzdnSectionRepo(c),
		Toll:            repo.NewOdsSzdnTollRepo(c),
		TollStationIP:   repo.NewOdsSzdnTollStationIpRepo(c),
		Org:             repo.NewOdsYhglVBaseOrgRepo(c),
		TrailTracks:     repo.NewZdataTrailTracksRepo(c),
		TrailFitting:    repo.NewZdataTrailFittingRepo(c),
		LocationDict:    repo.NewZdataLocationDictRepo(c),
		KafkaRecord:     repo.NewKafkaMessageRecordRepo(c),
	}
}

func openDB(ctx context.Context, cfg *config.Config) (*db.Client, error) {
	m := cfg.Datasource.Master()
	client, err := db.Open(ctx, db.Config{
		URL: m.URL, Username: m.Username, Password: m.Password,
		MaxOpenConns: m.MaxOpenConns, MaxIdleConns: m.MaxIdleConns,
		ConnMaxLifetime: m.ConnMaxLifetime, SlowThreshold: m.SlowThreshold, LogSQL: m.LogSQL,
	})
	if err != nil {
		return nil, fmt.Errorf("连接 GaussDB 失败: %w", err)
	}
	slog.Info("GaussDB 连接已建立", "maxOpen", m.MaxOpenConns)
	return client, nil
}

func openCache(ctx context.Context, cfg *config.Config) (*cache.Client, error) {
	client, err := cache.New(ctx, cache.Options{
		Addr: cfg.Redis.Addr(), Password: cfg.Redis.Password,
		DB: cfg.Redis.Database, PoolSize: cfg.Redis.PoolSize,
	})
	if err != nil {
		return nil, fmt.Errorf("连接 Redis 失败: %w", err)
	}
	slog.Info("Redis 连接已建立", "addr", cfg.Redis.Addr(), "db", cfg.Redis.Database)
	return client, nil
}

func openES(cfg *config.Config) *es.Client {
	e := cfg.Elasticsearch
	client := es.New(es.Config{
		BaseURL: e.BaseURL(), Username: e.Username, Password: e.Password,
		ConnTimeout: e.ConnectionTimeout, SocketTimout: e.SocketTimeout,
	})
	// DIFF: 不在启动时 ping（Java 的 RestHighLevelClient 也是懒连接），
	// 健康状况交给 /readyz 与各查询的降级分支。
	slog.Info("Elasticsearch 客户端已创建", "baseURL", e.BaseURL(),
		"indexes", []string{e.Index.Snapshot, e.Index.Fee, e.Index.Trail})
	return client
}

// openBus 构造 Kafka 总线；未配置 brokers 时返回 nil，调用方需容忍（接口方法内已做 nil 判断）。
func openBus(cfg *config.Config) *mq.KafkaBus {
	brokers := splitAndTrim(cfg.Kafka.BootstrapServers)
	if len(brokers) == 0 {
		slog.Warn("未配置 kafka.bootstrap-servers，消息总线降级为本地模式（生产者/消费者均不启动）")
		return nil
	}
	topic := cfg.Kafka.Topic.SnapshotFlow
	if topic == "" {
		topic = cfg.MQ.Topic.SnapshotFlow
	}
	return mq.NewKafka(mq.Configure{
		Brokers:         brokers,
		GroupID:         cfg.Kafka.GroupID,
		Topic:           topic,
		DeadLetterTopic: cfg.MQ.DeadLetter.RoutingKey,
		MaxRetry:        cfg.Pulsar.MaxRetryTimes,
	})
}

func splitAndTrim(s string) []string {
	out := make([]string, 0, 4)
	for _, part := range strings.Split(s, ",") {
		if p := strings.TrimSpace(part); p != "" {
			out = append(out, p)
		}
	}
	return out
}

// ---------------------------------------------------------------- 后台任务

// startDeps 汇总后台任务的依赖。
type startDeps struct {
	cfg          *config.Config
	bus          *mq.KafkaBus
	producer     *service.KafkaProducerService
	snapshotSync *service.SnapshotFlowSyncService
	largeSync    *service.LargeScaleSyncService
	consumer     *service.SnapshotFlowConsumer
	dict         *service.DictRegistry
	multiSource  *service.MultiSourceDataFlowService
	loss         *service.DataLossDetectionService
	delay        *service.DelayMonitoringService
	reliability  *service.DataReliabilityService
	consistency  *service.GaussEsConsistencyService
	// export / largeQuery 只在 shutdown 时使用：它们持有在途导出任务的 WaitGroup
	export     *service.UnifiedExportService
	largeQuery *service.LargeScaleQueryService
	// sysUtil 对应 TrackTask 里的 @Autowired ISysUtilService（syncCurrentTrack / syncHistroyTrack 两个任务）
	sysUtil *service.SysUtilService
}

// backgroundTasks 持有所有需要显式关闭的后台组件。
//
// 报告 01 Q8/Q9：导出服务与 LargeScaleQueryService 之前没有接入 shutdown，
// 在途 CSV 会被硬截断；同步任务则可能无限等待。现在统一在此登记并加超时。
type backgroundTasks struct {
	scheduler  *scheduler.Scheduler
	producer   *service.KafkaProducerService
	sync       *service.SnapshotFlowSyncService
	largeSync  *service.LargeScaleSyncService
	consumer   *service.SnapshotFlowConsumer
	bus        *mq.KafkaBus
	export     *service.UnifiedExportService
	largeQuery *service.LargeScaleQueryService
}

func startBackground(ctx context.Context, d startDeps) *backgroundTasks {
	tasks := &backgroundTasks{
		largeSync:  d.largeSync,
		bus:        d.bus,
		export:     d.export,
		largeQuery: d.largeQuery,
	}

	// 生产者重试扫描（@PostConstruct 里启动的 retryExecutor）
	if d.producer != nil {
		d.producer.Start(ctx)
		tasks.producer = d.producer
	}

	// 快照流水增量同步（SyncService 的 Start 内部按 incremental-sync-interval 起循环）
	if d.snapshotSync != nil {
		d.snapshotSync.Start(ctx)
		tasks.sync = d.snapshotSync
	}

	// MQ 消费端（SnapshotFlowPulsarConsumer 的目标）
	if d.consumer != nil {
		d.consumer.Start(ctx)
		tasks.consumer = d.consumer
	}

	// 字典/设备/延迟监控的进程内状态初始化（对应 Java 的 @PostConstruct init()）
	if d.loss != nil {
		d.loss.Init()
	}
	if d.delay != nil {
		d.delay.Init()
	}

	// 定时任务
	sched := scheduler.New(time.Local)
	if _, err := scheduler.RegisterAll(sched, d.cfg, &scheduler.Jobs{
		Dict: d.dict, MultiSource: d.multiSource, Loss: d.loss,
		Delay: d.delay, Reliability: d.reliability, Consistency: d.consistency,
		SysUtil: d.sysUtil,
	}); err != nil {
		// 表达式写错属于配置错误：直接退出，避免"服务起来了但定时任务全没跑"。
		slog.Error("定时任务登记失败", "err", err)
	} else {
		sched.Start(ctx)
		tasks.scheduler = sched
	}
	return tasks
}

func shutdown(srv *http.Server, tasks *backgroundTasks, dbc *db.Client, cacheClient *cache.Client) error {
	// 顺序与 @PreDestroy 相反：先停入口（不再接新请求），再停后台，最后断连接。
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	var errs []error
	if err := srv.Shutdown(shutdownCtx); err != nil {
		errs = append(errs, fmt.Errorf("关闭 HTTP 服务: %w", err))
	}

	// 后台组件统一用"总预算 60s + 逐项扣减"的等待策略。
	//
	// 报告 01 Q9：全量同步/导出使用 context.WithoutCancel（或进程级 ctx），
	// 关停时若直接 Wait() 会被在途的大任务挂住数小时；反过来若不等，CSV 会被截断（Q8）。
	// 这里的取舍是：给每个组件一个明确上限，超时记录 WARN + 汇总到返回值，
	// 让进程按 K8s 的 terminationGracePeriodSeconds 正常退出。
	deadline := time.Now().Add(60 * time.Second)
	wait := func(name string, fn func()) {
		remaining := time.Until(deadline)
		if remaining <= 0 {
			msg := "关闭 " + name + " 跳过：关闭总预算（60s）已用尽"
			slog.Warn(msg)
			errs = append(errs, errors.New(msg))
			return
		}
		if !utils.WaitTimeout(remaining, fn) {
			msg := fmt.Sprintf("关闭 %s 超时（剩余预算 %.1fs），继续关闭后续组件", name, remaining.Seconds())
			slog.Warn(msg)
			errs = append(errs, errors.New(msg))
		}
	}

	if tasks != nil {
		if tasks.scheduler != nil {
			wait("定时任务调度器", tasks.scheduler.Stop)
		}
		if tasks.consumer != nil {
			wait("MQ 消费者", tasks.consumer.Close)
		}
		if tasks.sync != nil {
			wait("快照同步", tasks.sync.Close)
		}
		if tasks.export != nil {
			wait("统一导出服务", tasks.export.Close)
		}
		if tasks.largeQuery != nil {
			wait("大表导出服务", tasks.largeQuery.Close)
		}
		if tasks.largeSync != nil {
			wait("GaussDB→ES 同步", tasks.largeSync.Close)
		}
		if tasks.producer != nil {
			wait("Kafka 生产者", tasks.producer.Close)
		}
		if tasks.bus != nil {
			wait("Kafka 总线", func() { _ = tasks.bus.Close() })
		}
	}
	if cacheClient != nil {
		wait("Redis", func() {
			if err := cacheClient.Close(); err != nil {
				errs = append(errs, fmt.Errorf("关闭 Redis: %w", err))
			}
		})
	}
	if dbc != nil {
		wait("GaussDB", func() {
			if err := dbc.Close(); err != nil {
				errs = append(errs, fmt.Errorf("关闭 GaussDB: %w", err))
			}
		})
	}
	slog.Info("应用已退出")
	return errors.Join(errs...)
}

// ---------------------------------------------------------------- 探针

func pingDB(ctx context.Context, c *db.Client) error {
	raw, err := c.Raw()
	if err != nil {
		return err
	}
	return raw.PingContext(ctx)
}

func pingES(ctx context.Context, c *es.Client) error {
	if c.Healthy(ctx) {
		return nil
	}
	return errors.New("elasticsearch 不可达（查询会自动降级到 GaussDB）")
}
