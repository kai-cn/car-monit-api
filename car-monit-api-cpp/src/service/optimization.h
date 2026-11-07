#pragma once
// 大规模 / 统一 / 渐进式查询的服务层。
//
// 对应 Java：
//   com.ruoyi.base.service.optimization.UnifiedQueryService
//   com.ruoyi.base.service.optimization.LargeScaleQueryService
//   com.ruoyi.base.service.optimization.UnifiedExportService
//   com.ruoyi.base.service.optimization.ProgressiveQueryArchitectureService
//   com.ruoyi.base.service.optimization.LargeScaleDataSyncService
//   com.ruoyi.base.service.optimization.EsIndexManageService
//   com.ruoyi.base.service.optimization.GaussEsConsistencyService
//
// 说明（环境差异，见 implementation 中对应 WARN 日志）：
// 本环境 localhost:9200 不可达。所有 ES REST 调用都真实发出；连接失败时降级为
// 等价 PostgreSQL 查询（相同时间范围 / 模糊过滤 / 排序 / 分页），行为与 Java 在
// ES 不可用时不同，仅作为本环境可运行的回退路径。
#include "common/json.h"

#include <map>
#include <optional>
#include <string>

namespace cm::service {

enum class DataSource { Snapshot, Fee, Trail };

// Java enum DataSource：SNAPSHOT / FEE / TRAIL（用于响应中的 dataSource 字段）。
std::string data_source_name(DataSource ds);

// UnifiedQueryController 的 parseDataSource：大小写不敏感；非法值抛出
// std::invalid_argument（controller 转成 {code:400,message}）。
DataSource parse_data_source(const std::string& ds);

// LargeScaleQueryController 的 resolveDs：null/未知按 snapshot 处理。
DataSource resolve_data_source(const std::string& type);

using FuzzyFields = std::map<std::string, std::string>;

class UnifiedQueryService {
public:
  // UnifiedQueryService.query
  Json query(DataSource ds, const std::string& start_time, const std::string& end_time,
             const FuzzyFields& fuzzy, int page_num, int page_size);
};

class LargeScaleQueryService {
public:
  // LargeScaleQueryService.fuzzyQuery
  Json fuzzy_query(const std::string& type, const std::string& start_time,
                   const std::string& end_time, const FuzzyFields& fuzzy, int page_num,
                   int page_size);
  // LargeScaleQueryService.aggregationStats
  Json aggregation_stats(const std::string& type, const std::string& start_time,
                         const std::string& end_time, const std::string& group_by,
                         const std::optional<std::string>& count_field, const FuzzyFields& fuzzy,
                         int top_n);
  // LargeScaleQueryService.submitExportTask -> taskId
  std::string submit_export_task(const std::string& type, const std::string& start_time,
                                 const std::string& end_time, const FuzzyFields& fuzzy);
  // LargeScaleQueryService.getExportStatus；任务不存在返回 null。
  Json export_status(const std::string& task_id);
};

class UnifiedExportService {
public:
  // UnifiedExportService.submitExportTask -> taskId
  std::string submit_export_task(DataSource ds, const std::string& start_time,
                                 const std::string& end_time, const FuzzyFields& fuzzy);
  // UnifiedExportService.getExportStatus；任务不存在返回 null。
  Json export_status(const std::string& task_id);
};

// ProgressiveQueryArchitectureService.QueryRequest
struct ProgressiveQueryRequest {
  std::optional<std::string> start_time;
  std::optional<std::string> end_time;
  std::optional<std::string> platenumber;
  std::optional<std::string> gantryname;
  std::optional<std::string> roadname;
  std::optional<std::string> sectionname;
  std::optional<std::string> orgname;
  std::optional<std::string> tollname;
  std::optional<std::string> cursor;
  int page_size = 20;
};

// ProgressiveQueryArchitectureService.QueryResult
struct ProgressiveQueryResult {
  Json data = Json::array();
  long long total = 0;
  std::string strategy;
};

class ProgressiveQueryArchitectureService {
public:
  ProgressiveQueryResult query_snapshot_flow(const ProgressiveQueryRequest& req);
  ProgressiveQueryResult query_fee_records(const ProgressiveQueryRequest& req);
  ProgressiveQueryResult query_trail_fitting(const ProgressiveQueryRequest& req);
  // detectScaleLevel 的返回值：LEVEL_10M / LEVEL_100M / LEVEL_1B
  std::string detect_scale_level(const std::string& table_name);
};

class LargeScaleDataSyncService {
public:
  void full_sync_one_year();
  void incremental_sync();
  void repair_sync(DataSource ds, const std::string& start_time, const std::string& end_time);
};

class GaussEsConsistencyService {
public:
  // GaussEsConsistencyService.scheduledReconcile 的一次 tick。
  void consistency_tick();
};

UnifiedQueryService& unified_query();
LargeScaleQueryService& large_scale_query();
UnifiedExportService& unified_export();
ProgressiveQueryArchitectureService& progressive_query();
LargeScaleDataSyncService& data_sync();
GaussEsConsistencyService& consistency_service();

// 由 register_optimization 调用：按 consistency.reconcile.cron 的时分秒启动
// 守护线程（等价于 Java 的 Quartz 定时任务）。未开启时不做任何事。
void ensure_consistency_scheduler();

} // namespace cm::service
