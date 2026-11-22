package handler

// JAVA 对照:
//
//	pro-business-api/src/main/java/com/ruoyi/base/controller/LargeScaleQueryController.java:54-319
//	pro-business-api/src/main/java/com/ruoyi/base/controller/UnifiedQueryController.java:64-194
//	pro-business-api/src/main/java/com/ruoyi/base/controller/ProgressiveQueryController.java:53-174
//
// 类/职责: 三张大表的「查询 / 统计 / 异步导出 / 同步运维」接口
// 对应 Go 文件: internal/handler/query.go
// 关键映射:
//
//	GET  /api/v1/large/{snapshot,fee,trail}  → LargeScaleQueryService.FuzzyQuery
//	GET  /api/v1/large/carTrackQueryByCarNo  → 车牌塞进 fuzzy[platenumber] 后走 trail
//	GET  /api/v1/large/stats/group           → AggregationStats
//	POST /api/v1/large/export/submit         → SubmitExport（立即返回 taskId）
//	POST /api/v1/large/sync/{full,incremental,repair} → LargeScaleSyncService
//	GET  /api/v1/unified/{ds}/list           → UnifiedQueryService.Query
//	POST /api/v1/unified/{ds}/export/submit  → UnifiedExportService.SubmitExportTask
//	GET  /api/v1/progressive/{表}/list       → ProgressiveQueryService.QueryXxx
//
// DIFF: 三个 Java Controller 都返回 Map<String,Object>（不是 AjaxResult），字段名由 put 顺序决定；
// Go 用 gin.H 逐键赋值复刻同一份 JSON —— 前端按 key 取值，顺序无所谓。
//
// PARITY: 两处“同名字段不同来源”的行为被原样保留：
//  1. large 侧 dataSource 用枚举名（SNAPSHOT/FEE/TRAIL），unified 侧回显路径参数原串；
//  2. large 的导出把请求体当 Map 后仍要求 key 带 "fuzzyFields." 前缀，unified 的导出直接用整个请求体。

import (
	"context"
	"log/slog"
	"net/http"
	"reflect"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"

	"github.com/ruoyi/car-monit-api-go/internal/middleware"
	"github.com/ruoyi/car-monit-api-go/internal/response"
	"github.com/ruoyi/car-monit-api-go/internal/service"
)

// QueryDeps 对应三个查询类 Controller 的 @Autowired 字段。
type QueryDeps struct {
	Large       *service.LargeScaleQueryService
	Query       *service.UnifiedQueryService
	Export      *service.UnifiedExportService
	Progressive *service.ProgressiveQueryService
	Sync        *service.LargeScaleSyncService
}

// Register 挂载 /api/v1/large、/api/v1/unified、/progressive 三组路由。
func (d *QueryDeps) Register(g *gin.RouterGroup) {
	large := g.Group("/api/v1/large")
	large.GET("/snapshot", func(c *gin.Context) { d.queryByDs(c, service.DsSnapshot) })
	large.GET("/fee", func(c *gin.Context) { d.queryByDs(c, service.DsFee) })
	large.GET("/trail", func(c *gin.Context) { d.queryByDs(c, service.DsTrail) })
	large.GET("/carTrackQueryByCarNo", d.queryCarTrackByCarNo)
	large.GET("/stats/group", d.groupByStats)
	large.POST("/export/submit", d.largeSubmitExport)
	large.GET("/export/status/:taskId", d.largeExportStatus)
	large.POST("/sync/full", d.triggerFullSync)
	large.POST("/sync/incremental", d.triggerIncrementalSync)
	large.POST("/sync/repair", d.triggerRepairSync)

	unified := g.Group("/api/v1/unified")
	unified.GET("/:ds/list", d.unifiedList)
	unified.POST("/:ds/export/submit", d.unifiedSubmitExport)
	unified.GET("/export/status/:taskId", d.unifiedExportStatus)

	prog := g.Group("/progressive")
	prog.GET("/snapshotflow/list", func(c *gin.Context) { d.progressiveList(c, service.DsSnapshot) })
	prog.GET("/feerecords/list", func(c *gin.Context) { d.progressiveList(c, service.DsFee) })
	prog.GET("/trailfitting/list", func(c *gin.Context) { d.progressiveList(c, service.DsTrail) })
	prog.GET("/scale-level", d.scaleLevel)
}

// ============================================================
// /api/v1/large —— 模块 1：三表全字段模糊查询（L54-138）
// ============================================================

// queryByDs 对应 LargeScaleQueryController#queryByDs（L118-138）。
func (d *QueryDeps) queryByDs(c *gin.Context, ds service.DataSource) {
	result := gin.H{}
	if !requireTimeRange(c) {
		return
	}
	pageNum, pageSize := pageArgs(c, 20)
	list, err := d.Query.Query(c.Request.Context(), ds, c.Query("startTime"), c.Query("endTime"),
		fuzzyFields(c), pageNum, pageSize)
	if err != nil {
		slog.Error("[查询接口] 异常", "ds", ds.String(), "err", err)
		result["code"] = 500
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	result["code"] = 200
	result["message"] = "ok"
	result["dataSource"] = enumName(ds) // Java: ds.name()
	result["pageNum"] = pageNum
	result["pageSize"] = pageSize
	result["data"] = list
	c.JSON(http.StatusOK, result)
}

// queryCarTrackByCarNo 对应 L99-112：把车牌映射成逻辑字段 platenumber，交给统一路由翻译成物理列。
func (d *QueryDeps) queryCarTrackByCarNo(c *gin.Context) {
	result := gin.H{}
	if !requireTimeRange(c) {
		return
	}
	pageNum, pageSize := pageArgs(c, 20)
	fuzzy := make(map[string]string, 1)
	if carNo := c.Query("carNo"); carNo != "" {
		fuzzy["platenumber"] = carNo
	}
	list, err := d.Query.Query(c.Request.Context(), service.DsTrail, c.Query("startTime"),
		c.Query("endTime"), fuzzy, pageNum, pageSize)
	if err != nil {
		slog.Error("[查询接口] 异常", "ds", "trail", "err", err)
		result["code"] = 500
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	result["code"] = 200
	result["message"] = "ok"
	result["dataSource"] = enumName(service.DsTrail)
	result["pageNum"] = pageNum
	result["pageSize"] = pageSize
	result["data"] = list
	c.JSON(http.StatusOK, result)
}

// ============================================================
// /api/v1/large —— 模块 2：分组 Top-N 统计（L164-191）
// ============================================================

// groupByStats 对应 L164-191。
func (d *QueryDeps) groupByStats(c *gin.Context) {
	result := gin.H{}
	typ := c.DefaultQuery("type", "snapshot")
	if !requireTimeRange(c) {
		return
	}
	groupBy := c.Query("groupBy")
	topN, _ := strconv.Atoi(c.DefaultQuery("topN", "100"))
	ds, err := service.ParseType(typ)
	if err != nil {
		result["code"] = 500
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	stats, err := d.Large.AggregationStats(c.Request.Context(), ds, c.Query("startTime"),
		c.Query("endTime"), groupBy, c.Query("countField"), fuzzyFields(c), topN)
	if err != nil {
		slog.Error("[统计接口] 异常", "type", typ, "err", err)
		result["code"] = 500
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	result["code"] = 200
	result["message"] = "ok"
	result["type"] = typ
	result["groupBy"] = groupBy
	result["topN"] = topN
	result["data"] = stats
	c.JSON(http.StatusOK, result)
}

// ============================================================
// /api/v1/large —— 模块 3：异步导出（L201-249）
// ============================================================

// largeSubmitExport 对应 L201-222（请求体里的 key 仍要求 "fuzzyFields." 前缀 —— 照抄）。
func (d *QueryDeps) largeSubmitExport(c *gin.Context) {
	result := gin.H{}
	typ := c.DefaultQuery("type", "snapshot")
	if !requireTimeRange(c) {
		return
	}
	body, berr := jsonBody(c)
	if berr != nil {
		_ = c.Error(berr)
		return
	}
	fields := prefixedFields(body)
	ds, err := service.ParseType(typ)
	if err != nil {
		result["code"] = 500
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	taskID, err := d.Large.SubmitExport(c.Request.Context(), ds, c.Query("startTime"),
		c.Query("endTime"), fields)
	if err != nil {
		slog.Error("[导出-提交] 异常", "type", typ, "err", err)
		result["code"] = 500
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	result["code"] = 200
	result["message"] = "导出任务已提交"
	result["type"] = typ
	result["taskId"] = taskID
	c.JSON(http.StatusOK, result)
}

// largeExportStatus 对应 L227-249：注意响应键是 endTime（Java 的字段名），
// 而 Go 的 ExportTaskStatus 里叫 FinishTime —— 这里做一次名字映射。
func (d *QueryDeps) largeExportStatus(c *gin.Context) {
	result := gin.H{}
	st := d.Large.GetExportStatus(c.Param("taskId"))
	if st == nil {
		result["code"] = 404
		result["message"] = "task not found"
		c.JSON(http.StatusOK, result)
		return
	}
	result["code"] = 200
	result["status"] = st.Status
	result["totalExported"] = st.TotalExported
	result["filePartCount"] = st.FilePartCount
	result["submitTime"] = st.SubmitTime
	result["endTime"] = st.FinishTime
	c.JSON(http.StatusOK, result)
}

// ============================================================
// /api/v1/large —— 模块 4：同步运维（L256-309）
// ============================================================

// triggerFullSync 对应 L256-269：`new Thread(() -> syncService.fullSyncOneYear()).start()`。
func (d *QueryDeps) triggerFullSync(c *gin.Context) {
	result := gin.H{"code": 200, "message": "全量同步任务已在后台启动（三表），预计耗时较长"}
	ctx := context.WithoutCancel(c.Request.Context())
	go func() {
		defer func() {
			if r := recover(); r != nil {
				slog.Error("[同步-全量] 协程 panic", "panic", r)
			}
		}()
		if err := d.Sync.FullSyncOneYear(ctx); err != nil {
			slog.Error("[同步-全量] 异常", "err", err)
		}
	}()
	c.JSON(http.StatusOK, result)
}

// triggerIncrementalSync 对应 L272-285：Java 同步等待完成后再返回。
func (d *QueryDeps) triggerIncrementalSync(c *gin.Context) {
	result := gin.H{"code": 200, "message": "增量同步完成（三表，基于 Redis 水位）"}
	if err := d.Sync.IncrementalSync(c.Request.Context()); err != nil {
		slog.Error("[同步-增量] 异常", "err", err)
		result["code"] = 500
		result["message"] = err.Error()
	}
	c.JSON(http.StatusOK, result)
}

// triggerRepairSync 对应 L291-309：补同步在后台线程跑。
func (d *QueryDeps) triggerRepairSync(c *gin.Context) {
	result := gin.H{"code": 200, "message": "补同步任务已在后台启动 type=" + c.DefaultQuery("type", "snapshot")}
	if !requireTimeRange(c) {
		return
	}
	ds, err := service.ParseType(c.DefaultQuery("type", "snapshot"))
	if err != nil {
		result["code"] = 500
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	startTime, endTime := c.Query("startTime"), c.Query("endTime")
	ctx := context.WithoutCancel(c.Request.Context())
	go func() {
		defer func() {
			if r := recover(); r != nil {
				slog.Error("[同步-补录] 协程 panic", "panic", r)
			}
		}()
		if err := d.Sync.RepairSync(ctx, ds, startTime, endTime); err != nil {
			slog.Error("[同步-补录] 异常", "err", err)
		}
	}()
	c.JSON(http.StatusOK, result)
}

// ============================================================
// /api/v1/unified（UnifiedQueryController）
// ============================================================

// unifiedList 对应 L64-95。
func (d *QueryDeps) unifiedList(c *gin.Context) {
	result := gin.H{}
	if !requireTimeRange(c) {
		return
	}
	ds, err := service.ParseDataSource(c.Param("ds"))
	if err != nil {
		result["code"] = 400
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	pageNum, pageSize := pageArgs(c, 20)
	data, err := d.Query.Query(c.Request.Context(), ds, c.Query("startTime"), c.Query("endTime"),
		fuzzyFields(c), pageNum, pageSize)
	if err != nil {
		slog.Error("[统一查询] 异常", "ds", ds.String(), "err", err)
		result["code"] = 500
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	result["code"] = 200
	result["message"] = "ok"
	result["dataSource"] = c.Param("ds") // Java 回显路径参数原串
	result["pageNum"] = pageNum
	result["pageSize"] = pageSize
	result["data"] = data
	c.JSON(http.StatusOK, result)
}

// unifiedSubmitExport 对应 L112-136：请求体就是 fuzzy 条件本身（无前缀）。
func (d *QueryDeps) unifiedSubmitExport(c *gin.Context) {
	result := gin.H{}
	if !requireTimeRange(c) {
		return
	}
	ds, err := service.ParseDataSource(c.Param("ds"))
	if err != nil {
		result["code"] = 400
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	fuzzy, berr := jsonBody(c)
	if berr != nil {
		_ = c.Error(berr)
		return
	}
	taskID, err := d.Export.SubmitExportTask(c.Request.Context(), ds, c.Query("startTime"),
		c.Query("endTime"), fuzzy)
	if err != nil {
		slog.Error("[统一导出] 提交异常", "ds", ds.String(), "err", err)
		result["code"] = 500
		result["message"] = err.Error()
		c.JSON(http.StatusOK, result)
		return
	}
	result["code"] = 200
	result["message"] = "导出任务已提交, 请用 taskId 轮询状态"
	result["taskId"] = taskID
	c.JSON(http.StatusOK, result)
}

// unifiedExportStatus 对应 L141-164：完成后带 filePaths 与 costSeconds，失败带 errorMessage。
func (d *QueryDeps) unifiedExportStatus(c *gin.Context) {
	result := gin.H{}
	st := d.Export.GetExportStatus(c.Param("taskId"))
	if st == nil {
		result["code"] = 404
		result["message"] = "task not found"
		c.JSON(http.StatusOK, result)
		return
	}
	result["code"] = 200
	result["status"] = st.Status
	result["totalExported"] = st.TotalExported
	result["filePartCount"] = st.FilePartCount
	result["submitTime"] = st.SubmitTime
	switch st.Status {
	case service.TaskCompleted:
		result["endTime"] = st.FinishTime
		result["filePaths"] = st.FilePaths
		result["costSeconds"] = (st.FinishTime - st.SubmitTime) / 1000
	case service.TaskFailed:
		result["errorMessage"] = st.ErrorMessage
	}
	c.JSON(http.StatusOK, result)
}

// ============================================================
// /progressive（ProgressiveQueryController）
// ============================================================

// progressiveList 对应 L53-158：三个表共用同一套参数，只是调不同的 Query 方法。
func (d *QueryDeps) progressiveList(c *gin.Context, ds service.DataSource) {
	req := service.QueryRequest{
		StartTime:   c.Query("startTime"),
		EndTime:     c.Query("endTime"),
		Platenumber: c.Query("platenumber"),
		Orgname:     c.Query("orgname"),
		Sectionname: c.Query("sectionname"),
		Roadname:    c.Query("roadname"),
		Gantryname:  c.Query("gantryname"),
		Tollname:    c.Query("tollname"),
		Cursor:      c.Query("cursor"),
	}
	req.PageSize, _ = strconv.Atoi(c.DefaultQuery("pageSize", "20"))

	ctx := c.Request.Context()
	var (
		result *service.QueryResult
		err    error
	)
	switch ds {
	case service.DsSnapshot:
		result, err = d.Progressive.QuerySnapshotFlow(ctx, req)
	case service.DsFee:
		result, err = d.Progressive.QueryFeeRecords(ctx, req)
	default:
		result, err = d.Progressive.QueryTrailFitting(ctx, req)
	}
	if err != nil {
		_ = c.Error(err)
		return
	}
	// PARITY: Java 用 getDataTable((List<?>) result.getData())，total 来自 PageInfo 包装的
	// 普通 ArrayList —— 也就是「本页行数」，不是匹配总数。这里照抄，避免前端分页控件的显示变化。
	rows := result.Data
	total := sliceLen(rows)
	c.JSON(http.StatusOK, response.TableWithMsg(rows, total, "策略: "+result.Strategy))
}

// scaleLevel 对应 L164-174：三张表的当前数据量级别。
func (d *QueryDeps) scaleLevel(c *gin.Context) {
	ctx := c.Request.Context()
	levels := map[string]string{
		"ods_rt_szdn_snapshot_flow_addcode": d.Progressive.DetectScaleLevel(ctx, "ods_rt_szdn_snapshot_flow_addcode").Name(),
		"ods_lwzxsfsj_fee_records_01":       d.Progressive.DetectScaleLevel(ctx, "ods_lwzxsfsj_fee_records_01").Name(),
		"zdata_trail_fitting":               d.Progressive.DetectScaleLevel(ctx, "zdata_trail_fitting").Name(),
	}
	response.OkData(c, levels)
}

// ============================================================
// 小工具
// ============================================================

// requireTimeRange 复刻 Spring 对 `@RequestParam String startTime` 的必填校验。
//
// PARITY: Spring 对必填 @RequestParam 缺失抛 MissingServletRequestParameterException，
// 根本不会进方法体，回的是 HTTP 400 + 默认错误体（timestamp/status/error/message/path）。
// 上一版这里沿用 400 状态码但返了本项目自己的 {code,message} 结构，状态码对、响应体不对；
// 现在改成经 BindError 走一遍，与 Java 逐字一致（message 在 Java 默认配置下是空串）。
func requireTimeRange(c *gin.Context) bool {
	var missing []string
	if c.Query("startTime") == "" {
		missing = append(missing, "startTime")
	}
	if c.Query("endTime") == "" {
		missing = append(missing, "endTime")
	}
	if len(missing) == 0 {
		return true
	}
	_ = c.Error(middleware.NewBindError(http.StatusBadRequest,
		"Required String parameter '"+strings.Join(missing, "'")+"' is not present"))
	c.Abort()
	return false
}

// pageArgs 读 pageNum/pageSize（Java 的 defaultValue = "1"/def、20）。
func pageArgs(c *gin.Context, defaultSize int) (int, int) {
	pageNum, err := strconv.Atoi(c.DefaultQuery("pageNum", "1"))
	if err != nil || pageNum <= 0 {
		pageNum = 1
	}
	pageSize, err := strconv.Atoi(c.DefaultQuery("pageSize", strconv.Itoa(defaultSize)))
	if err != nil || pageSize <= 0 {
		pageSize = defaultSize
	}
	return pageNum, pageSize
}

// fuzzyFields 对应 extractFuzzyFields：只取 "fuzzyFields." 前缀的查询参数。
func fuzzyFields(c *gin.Context) map[string]string {
	out := map[string]string{}
	for key, values := range c.Request.URL.Query() {
		if !strings.HasPrefix(key, "fuzzyFields.") || len(values) == 0 || values[0] == "" {
			continue
		}
		out[strings.TrimPrefix(key, "fuzzyFields.")] = values[0]
	}
	return out
}

// prefixedFields 对应 large 侧对「请求体」也套一层 fuzzyFields. 前缀过滤的行为。
func prefixedFields(body map[string]string) map[string]string {
	out := map[string]string{}
	for key, value := range body {
		if !strings.HasPrefix(key, "fuzzyFields.") || value == "" {
			continue
		}
		out[strings.TrimPrefix(key, "fuzzyFields.")] = value
	}
	return out
}

// jsonBody 解析 `@RequestBody(required = false) Map<String,String>`。
//
// PARITY: 要区分三种情况，因为它们的行为在 Java 侧并不相同：
//   - 没有请求体（Content-Length=0）→ Java 的 required=false 直接给 null → 空条件，200；
//   - 请求体是合法 JSON → 正常解析；
//   - 请求体存在但解析不了 → Java 抛 HttpMessageNotReadableException → HTTP 400。
//     之前这里把第三种也当"没传"，于是 Go 返回 200 而 Java 返回 400。
func jsonBody(c *gin.Context) (map[string]string, error) {
	if c.Request == nil || c.Request.ContentLength == 0 {
		return map[string]string{}, nil
	}
	body := map[string]string{}
	if err := c.ShouldBindJSON(&body); err != nil {
		return nil, middleware.NewBindError(400,
			"Failed to read request body as Map<String,String>.", err)
	}
	return body, nil
}

// enumName 对应 Java 的 `ds.name()`（枚举常量名，全大写）。
func enumName(ds service.DataSource) string {
	switch ds {
	case service.DsFee:
		return "FEE"
	case service.DsTrail:
		return "TRAIL"
	default:
		return "SNAPSHOT"
	}
}

// sliceLen 取 any 里的切片长度（对应 `new PageInfo(list).getTotal()` 对普通 List 的行为）。
func sliceLen(v any) int64 {
	rv := reflect.ValueOf(v)
	if !rv.IsValid() {
		return 0
	}
	switch rv.Kind() {
	case reflect.Slice, reflect.Array, reflect.Map:
		return int64(rv.Len())
	}
	return 0
}
