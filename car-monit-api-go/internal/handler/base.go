package handler

// JAVA 对照:
//
//	pro-business-api/src/main/java/com/ruoyi/base/controller/DwdLcztFwqjcxxController.java:22-53
//	pro-business-api/src/main/java/com/ruoyi/base/controller/DwdLcztSfsjcxxController.java:20-52
//	pro-business-api/src/main/java/com/ruoyi/base/controller/DwdLcztSfzjcxxController.java:20-52
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsCxztFwqcllsController.java:23-48
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeGantryFusion01Controller.java:23-52
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeRecords01Controller.java:31-205
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeStationEnter01Controller.java:23-48
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeStationExit01Controller.java:20-44
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowAddcodeController.java:28-147
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowProvcaptureAddcodeController.java:24-49
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowStationcaptureAddcodeController.java:24-49
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnGantryController.java:20-53
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnGantryIpController.java:22-47
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnProvinceBorderVehicleWeightNewstructureController.java:24-60
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnSectionController.java:20-53
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnTollController.java:23-54
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnTollStationIpController.java:22-47
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsYhglVBaseOrgController.java:23-55
//	pro-business-api/src/main/java/com/ruoyi/base/controller/ZdataTrailTracksController.java:22-47
//
// 类/职责: 19 个「基础表只读接口」的路由装配 + 3 段返回前加工（对应 Controller 里的 for 循环）
// 对应 Go 文件: internal/handler/base.go
// 关键映射:
//
//	每个 Controller 的 @Autowired XxxService  → BaseDeps 里的 *repo.XxxRepo 字段
//	feerecords 的「车牌去类型 → 时间格式化 → 门架回填」  → decorateFeeRecords
//	snapshotflow 的「id=UUID → 抓拍时间格式化 → 图片域名替换」 → decorateSnapshotFlow
//	snapshotflow / feerecords 的「查询范围 sys_config:data_query」 → prepareListScope
//	vehicleweight 的 /map（硬编码两个 uuid）                → handleVehicleWeightMap
//
// DIFF: Java 每张表一个 Controller 类（19 个文件、每个 40 行样板）；Go 侧收敛成 19 行注册调用。
// 新增一张基础表时只需在 Register 里加一行，不会漏掉 total / 分页 / 空数组这类细节。
//
// PARITY: Java 在 feerecords 上用 setFlag("JiAnDong") 做数据权限，但收费流水表没有 org 列
// （mapper XML 也缺失），Go 侧无法翻译这个条件，只能记 WARN 日志后按“不过滤”执行 ——
// 这一点会放大返回集，灰度对比时必须显式确认（见 README「已知差异」）。

import (
	"context"
	"log/slog"
	"strings"

	"github.com/gin-gonic/gin"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
	"github.com/ruoyi/car-monit-api-go/internal/response"
	"github.com/ruoyi/car-monit-api-go/internal/service"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// sysConfigDataQuery 对应 `redisCache.getCacheObject("sys_config:data_query")`（查询范围开关）。
const sysConfigDataQuery = "sys_config:data_query"

// vehicleWeightMapUuids 对应 Controller 里写死的两个 uuid（调试用，不是参数）。
const vehicleWeightMapUuids = "18f8e2af-6ebe-4b33-8f37-a688f441de37,7379e7aa-e325-449b-9728-b8f6940c77f1"

// BaseDeps 是 19 个基础表 Repo 的聚合体。
//
// DIFF: Spring 按类型注入 19 个 Service；Go 用显式结构体，main() 里一眼能看出路由依赖哪些表。
type BaseDeps struct {
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

	Dict  *service.DictRegistry
	Cache *cache.Client
	// SysUtil 仅供 /base/vehicleweight/map 且存；其余端点只依赖 Repo。
	SysUtil *service.SysUtilService
}

// Register 把 19 个基础表 Controller 挂到根路由上（路径与 Java 完全一致）。
func (d *BaseDeps) Register(g *gin.RouterGroup) {
	// ---- 简单 CRUD：list + /{id} ----
	RegisterReadOnly(g, ReadOnlySpec[model.DwdLcztFwqjcxx]{
		Base: "/base/fwqjcxx", IDParam: "agentPk", AllowAll: true,
	}, d.Fwqjcxx)

	RegisterReadOnly(g, ReadOnlySpec[model.DwdLcztSfsjcxx]{
		Base: "/base/sfsjcxx", IDParam: "agentPk", AllowAll: true,
	}, d.Sfsjcxx)

	RegisterReadOnly(g, ReadOnlySpec[model.DwdLcztSfzjcxx]{
		Base: "/base/sfzjcxx", IDParam: "agentPk", AllowAll: true,
	}, d.Sfzjcxx)

	// PARITY: Java 的 /{bigId} 声明为 Long（big_id 是 bigint），与 gantryIp/tollStationIp 同类，
	// 因此用 numeric 注册器保持「非法 id → 400」的 Spring 行为。
	RegisterReadOnlyNumeric(g, ReadOnlySpec[model.OdsCxztFwqclls]{
		Base: "/manager/fwqclls", IDParam: "bigId",
	}, d.Fwqclls)

	RegisterReadOnly(g, ReadOnlySpec[model.OdsLwzxsfsjFeeGantryFusion01]{
		Base: "/base/feeGantry", IDParam: "bigId", FlatInfo: true,
		Decorate: decorateFeeGantry,
	}, d.FeeGantry)

	// ---- 收费流水：列表要回填门架名称/路段编码 ----
	RegisterReadOnly(g, ReadOnlySpec[model.OdsLwzxsfsjFeeRecords01]{
		Base:        "/base/feerecords",
		IDParam:     "bigId",
		AllowExport: true,
		FlatInfo:    true,
		Prepare:     d.prepareFeeRecords,
		Decorate:    d.decorateFeeRecords,
	}, d.FeeRecords)

	RegisterReadOnly(g, ReadOnlySpec[model.OdsLwzxsfsjFeeStationEnter01]{
		Base: "/base/feeStationEnter", IDParam: "bigId", NumericID: true,
	}, d.FeeStationEnter)

	RegisterReadOnly(g, ReadOnlySpec[model.OdsLwzxsfsjFeeStationExit01]{
		Base: "/base/feestationexit", IDParam: "bigId",
	}, d.FeeStationExit)

	// PARITY: Java 的 /{bigId} 在这三个 Controller 里声明成 Long
	// （OdsLwzxsfsjFeeStationEnter01Controller.java:45、
	//   OdsRtSzdnSnapshotFlowProvcaptureAddcodeController.java:46、
	//   OdsRtSzdnSnapshotFlowStationcaptureAddcodeController.java:46），
	// 所以非数字 id 必须回到 HTTP 400；用 NumericID 标志拦住，不动 Repo 的 string 接口。
	// ---- 门架抓拍流水：id 每次随机 + 图片域名归一 ----
	RegisterReadOnly(g, ReadOnlySpec[model.OdsRtSzdnSnapshotFlowAddcode]{
		Base:           "/base/snapshotflow",
		IDParam:        "bigId",
		AllowExport:    true,
		FlatInfo:       true,
		Prepare:        d.prepareSnapshotFlow,
		Decorate:       decorateSnapshotFlow(true),
		DecorateExport: decorateSnapshotFlow(false),
	}, d.SnapshotFlow)

	RegisterReadOnly(g, ReadOnlySpec[model.OdsRtSzdnSnapshotFlowProvcaptureAddcode]{
		Base: "/base/provcapture", IDParam: "bigId", NumericID: true,
	}, d.ProvCapture)

	RegisterReadOnly(g, ReadOnlySpec[model.OdsRtSzdnSnapshotFlowStationcaptureAddcode]{
		Base: "/base/stationcapture", IDParam: "bigId", NumericID: true,
	}, d.StationCapture)

	RegisterReadOnly(g, ReadOnlySpec[model.OdsSzdnGantry]{
		Base: "/base/gantry", IDParam: "id", AllowAll: true,
	}, d.Gantry)

	RegisterReadOnlyNumeric(g, ReadOnlySpec[model.OdsSzdnGantryIp]{
		Base: "/base/gantryIp", IDParam: "id",
	}, d.GantryIP)

	// ---- 省界称重：/{dataSource} 当 id 用，另有一个写死 uuid 的 /map ----
	RegisterReadOnly(g, ReadOnlySpec[model.OdsSzdnProvinceBorderVehicleWeightNewstructure]{
		Base: "/base/vehicleweight", IDParam: "dataSource",
	}, d.VehicleWeight)
	g.Group("/base/vehicleweight").GET("/map", d.handleVehicleWeightMap)

	RegisterReadOnly(g, ReadOnlySpec[model.OdsSzdnSection]{
		Base: "/base/section", IDParam: "id", AllowAll: true,
	}, d.Section)

	RegisterReadOnly(g, ReadOnlySpec[model.OdsSzdnToll]{
		Base: "/base/toll", IDParam: "id", AllowAll: true,
	}, d.Toll)

	RegisterReadOnlyNumeric(g, ReadOnlySpec[model.OdsSzdnTollStationIp]{
		Base: "/base/tollStationIp", IDParam: "id",
	}, d.TollStationIP)

	RegisterReadOnly(g, ReadOnlySpec[model.OdsYhglVBaseOrg]{
		Base: "/base/org", IDParam: "bigId", AllowAll: true,
	}, d.Org)

	RegisterReadOnly(g, ReadOnlySpec[model.ZdataTrailTracks]{
		Base: "/base/trailtracks", IDParam: "uuid",
	}, d.TrailTracks)
}

// handleVehicleWeightMap 对应 OdsSzdnProvinceBorderVehicleWeightNewstructureController#map()（L50-53）：
// `AjaxResult.success(service.selectByQueryUuids("uuid1,uuid2"))` —— 参数写死，属于联调用的探针接口。
//
// PARITY: 这两个 uuid 是 Java 源码里的字面量，不是配置项，因此原样保留（改动它就改变了接口行为）。
func (d *BaseDeps) handleVehicleWeightMap(c *gin.Context) {
	if d.SysUtil == nil {
		response.OkData(c, map[string]any{})
		return
	}
	response.OkData(c, d.SysUtil.WeightCaptureMap(c.Request.Context(), vehicleWeightMapUuids))
}

// prepareFeeRecords 对应 OdsLwzxsfsjFeeRecords01Controller#list 的前 20 行（L50-77）：
// 查询范围开关 → 车牌为空时加数据权限标记 → 路段/门架多值参数展开。
func (d *BaseDeps) prepareFeeRecords(ctx context.Context, q *model.OdsLwzxsfsjFeeRecords01) error {
	if !d.inQueryAllScope(ctx) && utils.IsBlank(model.Val(q.Vehicleplate)) {
		q.Flag = model.Str("JiAnDong")
		// PARITY: 收费流水表缺少 org 列，mapper XML 也缺失，这个条件无法落到 SQL。
		// 与其猜列名导致 SQL 直接报错，不如显式告警后按“不过滤”执行。
		slog.Warn("[收费流水] 数据权限标记 JiAnDong 无法翻译为 SQL（表无 org 列），已按不过滤执行")
	}
	if utils.IsNotBlank(model.Val(q.SectionCodeStr)) {
		q.SectionList = splitCSV(model.Val(q.SectionCodeStr))
	}
	if code := utils.DeleteEnd(model.Val(q.Code)); utils.IsNotBlank(code) {
		q.CodeList = splitCSV(code)
		q.Code = model.Str("") // 对应 setCode("")：原字段不再参与等值过滤
	}
	return nil
}

// decorateFeeRecords 对应 L90-116（list）与 L166-192（listToExport）—— 两段代码完全相同。
func (d *BaseDeps) decorateFeeRecords(ctx context.Context, rows []model.OdsLwzxsfsjFeeRecords01) error {
	if len(rows) == 0 {
		return nil
	}
	gantryMap, err := d.Dict.GantryMap(ctx)
	if err != nil {
		return err
	}
	for i := range rows {
		r := &rows[i]
		// 车牌形如 "赣A12345_蓝"：列表只展示车牌本体
		plate := utils.IsNull(r.Vehicleplate)
		if idx := strings.Index(plate, "_"); idx > -1 {
			r.Vehicleplate = model.Str(plate[:idx])
		}
		if r.Transtime != nil {
			r.TranstimeStr = model.Str(model.FormatDateTime(r.Transtime.Time()))
		}
		if r.Lastgantrytime != nil {
			r.LastgantrytimeStr = model.Str(model.FormatDateTime(r.Lastgantrytime.Time()))
		}
		if g, ok := gantryMap[utils.IsNull(r.Gantryid)]; ok {
			r.GantryName = g.GantryName      // 门架名称
			r.SectionCodeStr = g.SectionCode // 路线编号
		}
	}
	return nil
}

// prepareSnapshotFlow 对应 OdsRtSzdnSnapshotFlowAddcodeController#list 的前 30 行（L44-72）。
func (d *BaseDeps) prepareSnapshotFlow(ctx context.Context, q *model.OdsRtSzdnSnapshotFlowAddcode) error {
	if !d.inQueryAllScope(ctx) && utils.IsBlank(model.Val(q.Platenumber)) {
		q.Flag = model.Str("JiAnDong")
	}
	if utils.IsNotBlank(model.Val(q.SectionCodeStr)) {
		q.SectionList = splitCSV(model.Val(q.SectionCodeStr))
		q.Sectioncode = model.Str("") // 对应 setSectioncode("")：改走 sectionList 的 IN 过滤
	}
	if code := utils.DeleteEnd(model.Val(q.Code)); utils.IsNotBlank(code) {
		q.CodeList = splitCSV(code)
		q.Code = model.Str("")
	}
	return nil
}

// decorateFeeGantry 对应 OdsLwzxsfsjFeeGantryFusion01Controller.java:36-41。
//
// PARITY: Java 在 list 里给每一行现生成一个 UUID 写回 id（实体上的 id 是
// @TableField(exist=false)，库里没有这一列），前端拿它当行 key；Go 之前没做这一步，
// 导致 Java 返 id="92745042..." 而 Go 返 id=null。
// 注意只有 list 做，/feeGantry/{bigId} 的 getInfo 不做 —— 保持原样。
func decorateFeeGantry(_ context.Context, rows []model.OdsLwzxsfsjFeeGantryFusion01) error {
	for i := range rows {
		rows[i].Id = model.Str(utils.GetUUID())
	}
	return nil
}

// decorateSnapshotFlow 对应 L77-88（list）与 L125-133（listToExport）。
//
// withPicURL 为 true 时额外做一次图片域名替换（只有 list 做，listToExport 不做 —— 照抄）。
func decorateSnapshotFlow(withPicURL bool) func(context.Context, []model.OdsRtSzdnSnapshotFlowAddcode) error {
	return func(_ context.Context, rows []model.OdsRtSzdnSnapshotFlowAddcode) error {
		for i := range rows {
			r := &rows[i]
			r.Id = model.Str(utils.GetUUID()) // Java: StringUtils.getUUID()（32 位无横线），前端拿它当行 key
			if r.Snapshottime != nil {
				r.SnapshottimeStr = model.Str(model.FormatDateTime(r.Snapshottime.Time()))
			}
			if withPicURL {
				r.Snappicturepath = model.Str(utils.RepalacePicUrl(utils.DeleteEnd(model.Val(r.Snappicturepath))))
			}
		}
		return nil
	}
}
