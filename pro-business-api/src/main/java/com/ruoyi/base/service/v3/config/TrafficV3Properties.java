package com.ruoyi.base.service.v3.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * V3 交通流水查询/同步/导出的统一配置。
 *
 * <p>配置前缀 {@code traffic}，与 {@code pro-business-api/src/main/resources/application.yml}
 * 中的 {@code traffic:} 节点对应。所有开关默认保持“只读、不自动改写数据”，
 * 需要运维显式开启（auto-bootstrap / sync / reconcile）。</p>
 */
@Data
@Component
@ConfigurationProperties(prefix = "traffic")
public class TrafficV3Properties {

    /**
     * 业务时区（P2-1）：查询解析、JDBC 时间窗、导出格式化统一使用该时区。
     * 启动时据此设置 JVM 默认时区并打印自检信息；容器默认 UTC 时避免整体偏 8 小时。
     */
    private String timezone = "Asia/Shanghai";

    private Query query = new Query();
    private Es es = new Es();
    private Plate plate = new Plate();
    private Sync sync = new Sync();
    private Reconcile reconcile = new Reconcile();
    private Export export = new Export();
    private BigScreen bigscreen = new BigScreen();

    @Data
    public static class Query {
        /**
         * es=走 Elasticsearch（需 ES 已完成初始化+回灌并显式切换）；legacy=旧 GaussDB Mapper（安全默认）。
         * 即使配置为 es，启动时若 ES/读别名不可用也会自动回退 legacy 并打 WARN。
         */
        private String engine = "legacy";
        /** 列表单页上限（设计 §4.3） */
        private int maxPageSize = 100;
        /** from+size 上限（ES max_result_window） */
        private int maxWindow = 10000;
        /** 时间范围上限（天） */
        private int maxDays = 365;
        /** 未传时间范围时默认最近天数 */
        private int defaultDays = 7;
        /** 车牌模糊输入最小长度（设计 §4.3：至少 2 个字符） */
        private int minPlateFuzzyLength = 2;
        /** 总数封顶（track_total_hits） */
        private int totalHitsCap = 10000;

        public boolean isEsEngine() {
            return "es".equalsIgnoreCase(engine);
        }
    }

    @Data
    public static class Es {
        /** 启动时自动创建 ILM/模板/月索引（生产建议 false，由运维脚本执行） */
        private boolean autoBootstrap = false;
        /** 启动时向前创建的月份数（含当前月） */
        private int bootstrapMonths = 13;
        /** 向前预建月份数 */
        private int forwardMonths = 1;
        /** PIT keep_alive */
        private String pitKeepAlive = "2m";
        /** 月索引统一后缀 */
        private String readAliasSuffix = "-read";
        private String writeAliasSuffix = "-write";
    }

    @Data
    public static class Plate {
        private Color color = new Color();

        @Data
        public static class Color {
            private Dict dict = new Dict();

            /**
             * 车牌颜色字典：单一事实源为 MySQL carmonitdb.sys_dict_type/sys_dict_data，
             * dict_type=plate_color。API 启动加载 + 定时刷新；代码内不再维护颜色码表。
             */
            @Data
            public static class Dict {
                private boolean enabled = true;
                private String url = "jdbc:mysql://127.0.0.1:3307/carmonitdb"
                        + "?useUnicode=true&characterEncoding=utf8&useSSL=false"
                        + "&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai"
                        + "&connectTimeout=3000&socketTimeout=3000";
                private String username = "root";
                private String password = "root";
                private String dictType = "plate_color";
                private long refreshIntervalMs = 300000L;
            }
        }
    }

    @Data
    public static class Sync {
        /** Outbox relay / Kafka 消费者总开关；默认关闭，避免本地误连 */
        private boolean enabled = false;
        private String topic = "search-sync";
        private String groupId = "search-sync-api";
        private long pollIntervalMs = 5000L;
        private int batchSize = 500;
        private int maxRetry = 5;
        /** bulk 批大小 */
        private int bulkSize = 500;
        /** car-warning 增量采集开关 */
        private boolean carWarningEnabled = true;
        private long carWarningPollIntervalMs = 30000L;
        private int carWarningLookbackDays = 7;
    }

    @Data
    public static class Reconcile {
        private boolean enabled = false;
        private String cron = "0 30 2 * * ?";
        private int lookbackMinutes = 60;
        private int bucketMinutes = 1;
        /** 漂移阈值：|gauss-es|/gauss */
        private double driftRatio = 0.001D;
        /** 单次对账最多回灌的桶数，防止雪崩 */
        private int maxRepairBuckets = 12;
        /**
         * 漂移桶是否同时清理“GaussDB 不存在但 ES 仍存在”的孤儿文档。
         * 只回灌无法删除多余文档，漂移会一直存在。
         */
        private boolean deleteOrphans = true;
        /** 单桶孤儿扫描最多读取的 ES 文档数，防止异常大桶拖垮对账 */
        private int orphanSweepMaxDocs = 20000;
    }

    @Data
    public static class Export {
        /** 导出文件目录；生产应替换为对象存储 */
        private String dir = System.getProperty("java.io.tmpdir") + "/car-monit-export";
        /** 全局 worker 数（设计 §5.5：2 个） */
        private int workers = 2;
        /** 单次拉取行数 */
        private int pageSize = 1000;
        /** 任务最长运行小时数（<=0 表示不限制） */
        private int maxHours = 24;
        /** 已完成任务与临时文件的保留小时数，超期由定时清理删除 */
        private int retentionHours = 24;
    }

    @Data
    public static class BigScreen {
        /**
         * 大屏预聚合查询开关。默认 false：dws_* 未回填前返回 503，
         * backend 按契约回退 legacy；ETL/预聚合就绪后置 true。
         */
        private boolean statsEnabled = false;
        /** 对账/预聚合查询超时（毫秒） */
        private int queryTimeoutMs = 2000;
        private Etl etl = new Etl();

        /**
         * 阶段一批量 ETL：MySQL carmonitdb -> GaussDB jl_data01.dws_*。
         * 生产最终由 Flink 承担；该配置用于初始化/补偿回填。
         */
        @Data
        public static class Etl {
            private boolean enabled = false;
            private String mysqlUrl = "jdbc:mysql://127.0.0.1:3307/carmonitdb"
                    + "?useUnicode=true&characterEncoding=utf8&useSSL=false"
                    + "&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai"
                    + "&connectTimeout=3000&socketTimeout=3000";
            private String username = "root";
            private String password = "root";
            /** 定时增量回填间隔（毫秒），仅 enabled=true 时生效 */
            private long intervalMs = 600000L;
            /** 每次定时回填回看天数 */
            private int lookbackDays = 2;
        }
    }
}
