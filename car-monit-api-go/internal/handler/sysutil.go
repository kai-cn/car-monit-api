package handler

// JAVA 对照:
//
//	pro-business-api/src/main/java/com/ruoyi/base/controller/SysUtilController.java:33-202
//	pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java:191-274, 1962-2152, 396-1223
//
// 类/职责: 轨迹查询与富集接口（/base/sysutil/*）
// 对应 Go 文件: internal/handler/sysutil.go
// 关键映射:
//
//	GET  /base/sysutil/saveRedis            → SysUtilService.SaveRedis（Java 侧方法体全被注释，空实现）
//	GET  /base/sysutil/carTrackQueryByCarNo → CarTrackQueryNew + BuildTrailInfos(clear=true)
//	GET  /base/sysutil/carTrackQueryByTime  → 读 redis car_list_jc + BuildTrailInfos(clear=false)
//	POST /base/sysutil/changeTrailInfo      → ChangeData（对象转换）
//	GET  /base/sysutil/getByTrailBo         → GetByTrailBo（按 8 类流水回源）
//
// DIFF: Java 两个查询接口各自抄了一遍「解析轨迹点 → changeData → 塞 trailUuid」的 15 行循环，
// Go 收敛为 service.BuildTrailInfos —— 两者的唯一差别是 clearTrailPoints（Java 在 ByCarNo
// 里显式 setTrailPoints("")，在 ByTime 里那行是注释掉的）。
//
// PARITY: total 来自与取数同谓词的 COUNT。Java 侧 list 被 PageHelper 包成 Page，
// getTotal() 拿到的是匹配总数；Go 早期用「本页行数」代替，导致前端算不出总页数、
// 越界页也无法回夹末页（P-PAGE-8）。现在按 Java 的顺序 count → ClampToLastPage → 取数，
// 计数与取数共用 repo.applyHistoryTrailFilters（见 CountHistoryTrail 的注释）。

import (
	"context"
	"log/slog"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/middleware"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/response"
	"github.com/ruoyi/car-monit-api-go/internal/service"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// carListJC 对应 Constants.java:285 的 car_list_jc（重点车辆库，由运维任务写入）。
const carListJC = "car_list_jc"

// SysUtilDeps 对应 SysUtilController 的两个 @Autowired 字段。
type SysUtilDeps struct {
	Service *service.SysUtilService
	Cache   *cache.Client
}

// Register 挂载 /base/sysutil 下的 5 个端点。
//
// PARITY: Java 里被注释掉的 /syncTrack、/syncSuspiciousCar 未注册（与当前后端行为一致）。
func (d *SysUtilDeps) Register(g *gin.RouterGroup) {
	grp := g.Group("/base/sysutil")
	grp.GET("/saveRedis", d.saveRedis)
	grp.GET("/carTrackQueryByCarNo", d.carTrackQueryByCarNo)
	grp.GET("/carTrackQueryByTime", d.carTrackQueryByTime)
	grp.POST("/changeTrailInfo", d.changeTrailInfo)
	grp.GET("/getByTrailBo", d.getByTrailBo)
}

// saveRedis 对应 L33-36：`return sysUtilService.saveRedis(sysUtil)`，实现是空的。
func (d *SysUtilDeps) saveRedis(c *gin.Context) {
	if err := d.Service.SaveRedis(c.Request.Context()); err != nil {
		_ = c.Error(err)
		return
	}
	response.Ok(c, response.Success())
}

// carTrackQueryByCarNo 对应 L77-109。
func (d *SysUtilDeps) carTrackQueryByCarNo(c *gin.Context) {
	var vo model.CarParaVO
	if err := bindQuery(c, &vo); err != nil {
		_ = c.Error(err)
		return
	}

	pp := pageParams(c)
	ctx := c.Request.Context()

	list := make([]model.ZdataTrailTracks, 0)
	var total int64
	if utils.IsNotBlank(vo.CarNo) {
		vo.Flag = "bannian" // 默认只查半年（L82）
		// Java 的 startPage() 会先用同一套 WHERE 跑一次 count（PageInfo(list).getTotal()），
		// 所以 total 是全量命中数而不是本页行数；越界页也靠这个 total 回夹到末页。
		n, err := d.Service.CarTrackCountNew(ctx, &vo)
		if err != nil {
			_ = c.Error(err)
			return
		}
		total = n
		pp.ClampToLastPage(total)
		// PageSize<=0 时绝不能把 limit=0 传下去：Repo 约定 limit<=0 表示「不加 LIMIT」，
		// 那样会从「返回空页」变成「全表扫描 + 全量富集」（实测 pageSize=0 会返回 1.8MB / 8s）。
		if pp.PageSize > 0 {
			// 对应 PageHelper 改写 SQL：LIMIT offset+pageSize，之后在内存里切掉前 offset 行。
			limit := pp.Offset() + pp.PageSize
			pageNum, pageSize := pp.PageNum, limit
			vo.PageNum, vo.PageSize = &pageNum, &pageSize
			rows, err := d.Service.CarTrackQueryNew(ctx, &vo)
			if err != nil {
				_ = c.Error(err)
				return
			}
			list = pageSlice(rows, pp)
		}
	}

	infos, err := d.Service.BuildTrailInfos(ctx, list, true)
	if err != nil {
		_ = c.Error(err)
		return
	}
	c.JSON(http.StatusOK, response.Table(infos, total))
}

// carTrackQueryByTime 对应 L117-157：车牌来自 Redis 里的重点车辆库，而不是入参。
func (d *SysUtilDeps) carTrackQueryByTime(c *gin.Context) {
	var vo model.CarParaVO
	if err := bindQuery(c, &vo); err != nil {
		_ = c.Error(err)
		return
	}

	pp := pageParams(c)
	ctx := c.Request.Context()

	list := make([]model.ZdataTrailTracks, 0)
	var total int64
	carlist := d.loadKeyVehicles(ctx) // 对应 L123-126
	if len(carlist) > 0 {
		vo.Carlist = carlist
		// 与 carTrackQueryByCarNo 同理：total 来自 PageHelper 的 count，不是本页行数。
		n, err := d.Service.CarTrackCountNew(ctx, &vo)
		if err != nil {
			_ = c.Error(err)
			return
		}
		total = n
		pp.ClampToLastPage(total)
		// 同 carTrackQueryByCarNo：PageSize<=0 时给空页，不能让 limit=0 变成「不加 LIMIT」
		if pp.PageSize > 0 {
			limit := pp.Offset() + pp.PageSize
			pageNum, pageSize := pp.PageNum, limit
			vo.PageNum, vo.PageSize = &pageNum, &pageSize
			rows, err := d.Service.CarTrackQueryNew(ctx, &vo)
			if err != nil {
				_ = c.Error(err)
				return
			}
			list = pageSlice(rows, pp)
		}
	}

	// PARITY: 这里 Java 没有清空 trailPoints（L141 是注释掉的），所以返回体里保留原始轨迹串。
	infos, err := d.Service.BuildTrailInfos(ctx, list, false)
	if err != nil {
		_ = c.Error(err)
		return
	}
	c.JSON(http.StatusOK, response.Table(infos, total))
}

// loadKeyVehicles 对应 L123-126：`(List<CarVO>) redisCache.getCacheObject(Constants.car_list_jc)`。
//
// PARITY: 缓存不可用/内容损坏时返回空列表（Java 会 NPE 或 ClassCastException 500）。
// 这里选择降级：宁可返回空轨迹，也不要因为一个字典缓存把查询接口打挂。
func (d *SysUtilDeps) loadKeyVehicles(ctx context.Context) []model.CarVO {
	if d.Cache == nil {
		return nil
	}
	var list []model.CarVO
	ok, err := d.Cache.GetJSON(ctx, carListJC, &list)
	if err != nil || !ok {
		slog.Warn("[轨迹查询] 重点车辆缓存未命中", "key", carListJC, "err", err)
		return nil
	}
	return list
}

// changeTrailInfo 对应 L163-191：入参就是 TrailInfo（tracks + trailList），返回富集后的 TrailInfo。
func (d *SysUtilDeps) changeTrailInfo(c *gin.Context) {
	var req model.TrailInfo
	if err := c.ShouldBindJSON(&req); err != nil {
		// Java：@RequestBody 解析失败是 HttpMessageNotReadableException → HTTP 400，
		// 不是 code:400 的 200 响应，所以必须走 BindError 而不是 BizError。
		_ = c.Error(middleware.NewBindError(400, "Failed to read request body as TrailInfo.", err))
		return
	}
	if req.Tracks == nil || len(req.TrailList) == 0 {
		// Java L165-190：条件不满足时原样返回入参
		c.JSON(http.StatusOK, req)
		return
	}

	tracks := req.Tracks
	// 对应 L169-180：字符串经纬度转 BigDecimal（Go 侧是 *float64）
	if err := fillDecimal(&tracks.StartLonDec, model.Val(tracks.StartLon), "startLon"); err != nil {
		_ = c.Error(err)
		return
	}
	if err := fillDecimal(&tracks.StratLatDec, model.Val(tracks.StratLat), "stratLat"); err != nil {
		_ = c.Error(err)
		return
	}
	if err := fillDecimal(&tracks.EndLonDec, model.Val(tracks.EndLon), "endLon"); err != nil {
		_ = c.Error(err)
		return
	}
	if err := fillDecimal(&tracks.EndLatDec, model.Val(tracks.EndLat), "endLat"); err != nil {
		_ = c.Error(err)
		return
	}
	for i := range req.TrailList {
		req.TrailList[i].IsQuery = model.Str("1") // L181-183：需要回源查抓拍对象
	}

	changed, err := d.Service.ChangeData(c.Request.Context(), tracks, req.TrailList)
	if err != nil {
		_ = c.Error(err)
		return
	}
	// Java L187 是 `setTrailUuid(CommonUtil.isNull(tracks.getPlateKey()))`，
	// 而 CommonUtil.isNull 空值返回**空串**，所以这里必须装箱成 Str("")，不能留 nil。
	changed.TrailUuid = model.Str(utils.IsNull(tracks.PlateKey))
	c.JSON(http.StatusOK, changed)
}

// getByTrailBo 对应 L199-202：`return sysUtilService.getByTrailBo(trailBo)` —— 直接返回对象，无信封。
func (d *SysUtilDeps) getByTrailBo(c *gin.Context) {
	var bo model.TrailBo
	if err := bindQuery(c, &bo); err != nil {
		_ = c.Error(err)
		return
	}
	result, err := d.Service.GetByTrailBo(c.Request.Context(), &bo)
	if err != nil {
		_ = c.Error(err)
		return
	}
	c.JSON(http.StatusOK, result)
}

// fillDecimal 对应 `if (isNotBlank(s)) x.setXDec(new BigDecimal(s))`。
//
// PARITY: Java 的 new BigDecimal("abc") 抛 NumberFormatException → 接口 500；
// 这里同样返回 500 级错误，而不是静默忽略非法坐标。
func fillDecimal(dst **float64, raw, field string) error {
	if utils.IsBlank(raw) {
		return nil
	}
	v, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return middleware.NewBizError(500, "字段 "+field+" 不是合法数值："+raw, err)
	}
	*dst = &v
	return nil
}
