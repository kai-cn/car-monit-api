package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java
//   191-274    saveRedis（方法体整体被注释，只剩 return AjaxResult.success()）
//   1962-2004  carTrackQuery / carTrackQueryNew
//   284-387    syncTrack（实时轨迹；见 track_sync.go）
//   2011-2022  getTrailBoListString
//   2030-2084  getTrailBoList
//   2092-2152  mapTrailBoList
//   396-962    changeData（轨迹点 → 设备经纬度/路段/桩号富集）
//   969-1223   getByTrailBo（抓拍对象按 uuid 回源 + 图片地址归一）
// 类/职责: SysUtilService — 轨迹查询与富集；上游是 SysUtilController（/base/sysutil/*）
// 对应 Go 文件: internal/service/sysutil.go
// 关键映射:
//   SysUtilController.carTrackQueryByCarNo/ByTime 里 "查流水 → 解析轨迹点 → changeData" 的循环
//                                                    → BuildTrailInfos（Controller 只剩余参数与响应包装）
//   getTrailBoListString / getTrailBoList          → getTrailBoListString / GetTrailBoList
//   mapTrailBoList（4 分钟窗口去重 + 图片合并）      → mapTrailBoList
//   changeData（5 张字典 map + 三段设备分支）        → ChangeData + pickFromMap
//   getByTrailBo（8 类流水按 uuid 查 + 负缓存）      → GetByTrailBo + lookupByUUID
//   redisCache.getCacheObject(DATE_xxx + uuid)     → cache.GetJSON(dateXxxPrefix + uuid)
//
// DIFF: Java 把"轨迹点解析 + 富集"写在 Controller 里（两个 endpoint 各抄一遍），Go 把循环收敛到
// BuildTrailInfos，handler 只做参数校验和响应包装 —— 逻辑只有一份，改起来不会漏。
// 另外 Java 的 getByTrailBo 会就地修改入参 TrailBo，Go 用副本返回，避免调用方共享状态。
//
// PARITY(已知缺陷，照抄不修):
//   1) changeData L481-482 把 lat 赋成了 trailBo.getLon()，导致"经度非空时纬度不会被补全"；
//   2) changeData L471 的 indexType 声明在 for 之外，stateType 未命中 switch 时会沿用上一个点的值；
//   3) getTrailBoList L2054 只在 captureTime 含 "T" 时才赋值，否则该点 captureTime 为空串；
//   4) mapTrailBoList 注释写"三分钟"，实际阈值是 4 分钟。
// 这四条都会改变灰度对比的返回结构，因此按原样保留并在此标注，修复需走业务确认。

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// 抓拍对象缓存前缀，对应 Constants.java:361-369（DATE_xxx）
const (
	dateBorderWeighingPrefix  = "DATE_BorderWeighingCapture:"
	dateGantryPrefix          = "DATE_GantryCapture:"
	dateProvPrefix            = "DATE_ProvCapture:"
	dateServiceAreaPrefix     = "DATE_ServiceAreaCapture:"
	dateStationPrefix         = "DATE_StationCapture:"
	dateFeeRecordPrefix       = "DATE_FeeRecord:"
	dateFeeStationEnterPrefix = "DATE_FeeStationEnter:"
	dateFeeStationExitPrefix  = "DATE_FeeStationExit:"

	// trailDedupeWindow 对应 mapTrailBoList L2103 的 4 * 60 * 1000
	trailDedupeWindow = 4 * time.Minute

	// 索引类型，对应 changeData L494-527
	indexTypeGantry      = "gantryType"
	indexTypeStation     = "stationType"
	indexTypeServiceArea = "service_area"

	// flag 值，对应 changeData L767
	trackFlagCurrent = "currentTrack"

	layoutCaptureRaw = "2006-01-02T15:04:05"
	layoutNormalTime = "2006-01-02 15:04:05"

	// capturePrefixLen 是 layoutCaptureRaw 渲染后的固定长度，用于"只取前缀"的宽容解析。
	capturePrefixLen = len(layoutCaptureRaw)
)

// parseCaptureTime 对应 SysUtilServiceImpl.java:2037+2055 的
// `new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss").parse(captureTime)`。
//
// PARITY: SimpleDateFormat 解析到模式结束即返回，**忽略尾部残留**；真实轨迹点是
// "2025-10-01T00:02:36.000+08:00"，Java 能解析、Go 的 time.Parse 会因
// `extra text: "+08:00"` 报错。这个差异一旦按 Java 语义修正，下游
// mapTrailBoList 的按时间去重/合并才会生效（否则 captureTime 恒空，去重整段形同不存在）。
func parseCaptureTime(raw string) (time.Time, bool) {
	if t, err := time.ParseInLocation(layoutCaptureRaw, raw, time.Local); err == nil {
		return t, true
	}
	if len(raw) >= capturePrefixLen {
		if t, err := time.ParseInLocation(layoutCaptureRaw, raw[:capturePrefixLen], time.Local); err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}

// SysUtilService 对应 SysUtilServiceImpl（Spring @Service 由 main() 的显式构造代替）
type SysUtilService struct {
	trailRepo          *repo.ZdataTrailTracksRepo
	weightRepo         *repo.OdsSzdnProvinceBorderVehicleWeightNewstructureRepo
	gantryCaptureRepo  *repo.OdsRtSzdnSnapshotFlowAddcodeRepo
	provCaptureRepo    *repo.OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo
	fwqcllsRepo        *repo.OdsCxztFwqcllsRepo
	stationCaptureRepo *repo.OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo
	feeRecordsRepo     *repo.OdsLwzxsfsjFeeRecords01Repo
	feeEnterRepo       *repo.OdsLwzxsfsjFeeStationEnter01Repo
	feeExitRepo        *repo.OdsLwzxsfsjFeeStationExit01Repo
	dict               *DictRegistry
	cache              *cache.Client
	// env 对应 Java 的 @Value("${isLocalhost}"):"local" | "prod"（config.App.Env）。
	// 只影响「实时轨迹是否做 24h 新鲜度过滤」，见 track_sync.go 的 PARITY 第 1 条。
	env string
}

// NewSysUtilService 对应 14 个 @Autowired 字段的注入。
//
// DIFF: Spring 按类型装配，Go 只能逐个显式传入 —— 好处是看一眼构造就知道这个 Service 依赖哪些表。
func NewSysUtilService(
	trailRepo *repo.ZdataTrailTracksRepo,
	weightRepo *repo.OdsSzdnProvinceBorderVehicleWeightNewstructureRepo,
	gantryCaptureRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo,
	provCaptureRepo *repo.OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo,
	fwqcllsRepo *repo.OdsCxztFwqcllsRepo,
	stationCaptureRepo *repo.OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo,
	feeRecordsRepo *repo.OdsLwzxsfsjFeeRecords01Repo,
	feeEnterRepo *repo.OdsLwzxsfsjFeeStationEnter01Repo,
	feeExitRepo *repo.OdsLwzxsfsjFeeStationExit01Repo,
	dict *DictRegistry,
	cacheClient *cache.Client,
	env string,
) *SysUtilService {

	return &SysUtilService{
		trailRepo: trailRepo, weightRepo: weightRepo, gantryCaptureRepo: gantryCaptureRepo,
		provCaptureRepo: provCaptureRepo, fwqcllsRepo: fwqcllsRepo,
		stationCaptureRepo: stationCaptureRepo, feeRecordsRepo: feeRecordsRepo,
		feeEnterRepo: feeEnterRepo, feeExitRepo: feeExitRepo,
		dict: dict, cache: cacheClient, env: env,
	}
}

// SaveRedis 对应 saveRedis(SysUtil)（L191-274）。
//
// 原方法体从 L197 到 L271 全部是注释（JedisCluster 试验、zdata_trail_tracks 作废验证、
// 手工塞轨迹点的调试片段），实际只有一句 return AjaxResult.success()。
// 这里保持"空实现 + 成功"，handler 直接把 nil 翻译成 200 —— 不要在此补业务逻辑。
func (s *SysUtilService) SaveRedis(ctx context.Context) error {
	slog.Info("[SysUtil] saveRedis 为空实现：Java 侧方法体整体被注释，仅返回成功")
	return nil
}

// CarTrackQueryNew 对应 carTrackQueryNew(CarParaVO)（L1995-2004）：
// carlist 拍平成 carNoList，再查 zdata_trail_tracks。
func (s *SysUtilService) CarTrackQueryNew(ctx context.Context, vo *model.CarParaVO) ([]model.ZdataTrailTracks, error) {
	if vo == nil {
		return nil, fmt.Errorf("CarTrackQueryNew: carParaVO 不能为空")
	}
	flattenCarNoList(vo) // JAVA L1996-2000: carlist.stream().map(CarVO::getCarNo) → carNoList
	return s.trailRepo.GetHistoryTrail(ctx, vo, 0)
}

// CarTrackCountNew 与 CarTrackQueryNew 同谓词地数一遍总行数，对应 PageHelper 为
// `new PageInfo(list).getTotal()` 生成的 count 查询。
//
// PARITY: total 与行集必须出自同一套条件，所以两者共用 flattenCarNoList；
// 各自演化会让 total 比原来（用 len(rows)）更难察觉地错。
func (s *SysUtilService) CarTrackCountNew(ctx context.Context, vo *model.CarParaVO) (int64, error) {
	if vo == nil {
		return 0, fmt.Errorf("CarTrackCountNew: carParaVO 不能为空")
	}
	flattenCarNoList(vo)
	return s.trailRepo.CountHistoryTrail(ctx, vo)
}

// flattenCarNoList 把 vo.Carlist 拍平成 vo.CarNoList（就地改，与 Java 一致）。
func flattenCarNoList(vo *model.CarParaVO) {
	if len(vo.Carlist) == 0 {
		return
	}
	carNoList := make([]string, 0, len(vo.Carlist))
	for _, c := range vo.Carlist {
		if utils.IsNotBlank(c.CarNo) {
			carNoList = append(carNoList, c.CarNo)
		}
	}
	vo.CarNoList = carNoList
}

// BuildTrailInfos 把 Controller 里"查流水 → 解析轨迹点 → changeData"的循环收敛成一个方法。
//
// JAVA 对照: SysUtilController.java:77-157（carTrackQueryByCarNo / carTrackQueryByTime）
//   - SysUtilServiceImpl.java:1962-1987（carTrackQuery，未清空 trailPoints 的版本）
//
// clearTrailPoints：ByCarNo 显式 tracks.setTrailPoints("")（L93），ByTime 注释掉了（L141）。
func (s *SysUtilService) BuildTrailInfos(ctx context.Context, list []model.ZdataTrailTracks, clearTrailPoints bool) (
	[]model.TrailInfo, error) {

	out := make([]model.TrailInfo, 0, len(list))
	for i := range list {
		tracks := &list[i]
		if utils.IsBlank(model.Val(tracks.TrailPoints)) {
			continue
		}
		points := s.GetTrailBoList(model.Val(tracks.TrailPoints))
		if clearTrailPoints {
			tracks.TrailPoints = model.Str("")
		}
		info, err := s.ChangeData(ctx, tracks, points)
		if err != nil {
			return nil, err
		}
		info.TrailUuid = utils.IsNull(tracks.PlateKey)
		out = append(out, *info)
	}
	return out, nil
}

// getTrailBoListString 对应 getTrailBoListString(String)（L2011-2022）：
// 修掉 dws 里被二次转义/包成对象字面量的轨迹串，让它变成合法 JSON 数组。
func (s *SysUtilService) getTrailBoListString(paraTrailPoints string) string {
	trailPoints := utils.IsNull(paraTrailPoints)
	if utils.IsNotBlank(trailPoints) {
		trailPoints = strings.ReplaceAll(trailPoints, "\\", "")
		trailPoints = strings.ReplaceAll(trailPoints, "{\"{", "[{")
		trailPoints = strings.ReplaceAll(trailPoints, "}\"}", "}]")
		trailPoints = strings.ReplaceAll(trailPoints, "\",\"{", ",{")
		trailPoints = strings.ReplaceAll(trailPoints, "ZdTrails:", "")
	}
	return trailPoints
}

// GetTrailBoList 对应 getTrailBoList(String)（L2030-2084）：
// 轨迹 JSON 数组 → []TrailBo（按字段白名单手工赋值，忽略 JSON 里的富集字段），再去重合并。
func (s *SysUtilService) GetTrailBoList(paraTrailPoints string) []model.TrailBo {
	trailPoints := s.getTrailBoListString(paraTrailPoints)
	if utils.IsBlank(trailPoints) || trailPoints == "{}" {
		return s.mapTrailBoList(nil)
	}

	var arr []map[string]json.RawMessage
	if err := json.Unmarshal([]byte(trailPoints), &arr); err != nil {
		// JAVA L2076-2078: catch(Exception) 后仅打印堆栈 + 日志，返回空列表
		slog.Error("[轨迹查询] 轨迹点 JSON 解析失败", "err", err, "raw", trailPoints)
		return s.mapTrailBoList(nil)
	}

	list := make([]model.TrailBo, 0, len(arr))
	for _, obj := range arr {
		var bo model.TrailBo
		// PARITY: Java 只在含 "T" 时赋值 captureTime（L2054-2059），其余情况保持 null —— 照抄
		if captureTime := jsonString(obj, "captureTime"); strings.Contains(captureTime, "T") {
			if t, ok := parseCaptureTime(captureTime); ok {
				bo.CaptureTime = t.Format(layoutNormalTime)
			}
		}
		bo.StateType = jsonString(obj, "stateType")
		bo.Platenumber = jsonString(obj, "platenumber")
		bo.LocationId = jsonString(obj, "locationId")
		bo.LocationCode = jsonString(obj, "locationCode")
		bo.PointUuid = jsonString(obj, "pointUuid")
		bo.SectionCode = jsonString(obj, "sectionCode")
		bo.OrgCode = jsonString(obj, "orgCode")
		bo.Pileno = jsonString(obj, "pileNo")
		if lon := jsonString(obj, "lon"); utils.IsNotBlank(lon) {
			bo.Lon = parseFloatPtr(lon)
		}
		if lat := jsonString(obj, "lat"); utils.IsNotBlank(lat) {
			bo.Lat = parseFloatPtr(lat)
		}
		list = append(list, bo)
	}
	return s.mapTrailBoList(list)
}

// mapTrailBoList 对应 mapTrailBoList(List<TrailBo>)（L2092-2152）：
// 同一 stateType + locationCode 的抓拍，4 分钟内只保留一条，图片用逗号累加。
//
// PARITY: 只有 GANTRY_CAPTURE / STATION_CAPTURE 会被写回 map（L2145-2147），
// 因此服务区/省界/称重的重复点不会被合并 —— 保持一致。
// DIFF: 内部用 *TrailBo 组织结果，避免 Go 的 slice 值拷贝让"累加图片"改不到已输出的元素。
func (s *SysUtilService) mapTrailBoList(trailBoList []model.TrailBo) []model.TrailBo {
	out := make([]*model.TrailBo, 0, len(trailBoList))
	seen := make(map[string]*model.TrailBo, len(trailBoList))

	for i := range trailBoList {
		bo := &model.TrailBo{}
		*bo = trailBoList[i]

		stateType := utils.IsNull(bo.StateType)
		locationCode := utils.IsNull(bo.LocationCode)
		captureTime := utils.IsNull(bo.CaptureTime)
		imagesArry := utils.DeleteEnd(bo.ImagesArry)
		mapKey := stateType + locationCode

		if prev, ok := seen[mapKey]; ok {
			prevCaptureTime := utils.IsNull(prev.CaptureTime)
			if utils.IsNotBlank(captureTime) && utils.IsNotBlank(prevCaptureTime) {
				t1, err1 := time.ParseInLocation(layoutNormalTime, captureTime, time.Local)
				t2, err2 := time.ParseInLocation(layoutNormalTime, prevCaptureTime, time.Local)
				if err1 != nil || err2 != nil {
					out = append(out, bo)
					slog.Info("[轨迹查询] 日期解析失败", "captureTime", captureTime, "prev", prevCaptureTime)
				} else {
					diff := t2.Sub(t1)
					if diff < 0 {
						diff = -diff
					}
					if diff > trailDedupeWindow {
						out = append(out, bo)
					} else if imagesArry != "" {
						// 抓拍图片累加（JAVA L2124-2132）
						if prevImages := utils.DeleteEnd(prev.ImagesArry); prevImages == "" {
							prev.ImagesArry = imagesArry
						} else {
							prev.ImagesArry = prevImages + "," + imagesArry
						}
					}
				}
			} else {
				out = append(out, bo)
			}
		} else {
			out = append(out, bo)
		}

		if stateType == DataTypeGantryCapture || stateType == DataTypeStationCapture {
			seen[mapKey] = bo
		}
	}

	result := make([]model.TrailBo, 0, len(out))
	for _, bo := range out {
		result = append(result, *bo)
	}
	return result
}

// ChangeData 对应 changeData(ZdataTrailTracks, List<TrailBo>)（L396-962）：
// 逐点补齐设备编码/名称/经纬度/路线/路段/桩号，再按 flag 推导起终点与小数位经纬度。
func (s *SysUtilService) ChangeData(ctx context.Context, tracks *model.ZdataTrailTracks, points []model.TrailBo) (
	*model.TrailInfo, error) {

	trailInfo := &model.TrailInfo{}
	if tracks == nil {
		tracks = &model.ZdataTrailTracks{}
	}
	// JAVA L401-407: 轨迹点为空时原样返回 tracks + 空列表
	if len(points) == 0 {
		trailInfo.Tracks = tracks
		trailInfo.TrailList = []model.TrailBo{}
		return trailInfo, nil
	}

	// JAVA L428-443: 五张字典 map（Java 走 5 个 Service，Go 统一走 DictRegistry）
	stationMap, err := s.dict.StationIPMap(ctx) // 收费站 ip
	if err != nil {
		return nil, err
	}
	tollMap, err := s.dict.TollMap(ctx) // 收费站 code
	if err != nil {
		return nil, err
	}
	gantryMap, err := s.dict.GantryIPMap(ctx) // 门架 ip
	if err != nil {
		return nil, err
	}
	locationMap, err := s.dict.LocationDictMap(ctx) // 位置信息
	if err != nil {
		return nil, err
	}
	sectionMap, err := s.dict.SectionMap(ctx) // 路段 → 路线
	if err != nil {
		return nil, err
	}

	// JAVA L447-471: 这些变量在原实现里从未被赋值（入口站信息取自 tracks 本身），保留以对齐输出
	firtStationCode := ""
	firtStationName := ""
	firtStationTime := ""
	plateColor := ""
	carType := ""
	carVehicle := ""
	var carNum *int64
	passType := ""

	// PARITY: 见文件头说明第 2 条 —— indexType 在 Java 里声明于循环之外
	indexType := ""

	for i := range points {
		trailBo := &points[i]
		locationCode := utils.IsNull(trailBo.LocationCode) // 设备 IP 地址
		stateType := utils.IsNull(trailBo.StateType)       // 流水来源类型
		sectionCode := utils.IsNull(trailBo.SectionCode)
		pileno := utils.IsNull(trailBo.Pileno)
		lon := trailBo.Lon
		lat := trailBo.Lon // PARITY: 见文件头说明第 1 条（Java L482 的笔误）
		roadCode := ""

		// 路段 → 路线编号（JAVA L486-492）
		if utils.IsNotBlank(sectionCode) {
			if section, ok := sectionMap[sectionCode]; ok && section != nil {
				roadCode = utils.IsNull(section.RoadCode)
				trailBo.RoadCode = roadCode
			}
		}

		switch stateType {
		case DataTypeBorderWeighing, DataTypeGantryCapture, DataTypeProvCapture, DataTypeFeeRecord:
			indexType = indexTypeGantry // 门架
		case DataTypeServiceAreaCapture:
			indexType = indexTypeServiceArea // 服务区
		case DataTypeStationCapture, DataTypeFeeStationEnter, DataTypeFeeStationExit:
			indexType = indexTypeStation // 收费站
		}

		// 位置信息 → 设备 code（JAVA L530-535）
		devLocatCode := ""
		if loc, ok := locationMap[locationCode]; ok && loc != nil {
			devLocatCode = utils.IsNull(loc.StandardCode)
		}
		devCodeID := utils.IsNull(trailBo.DevCode)

		switch indexType {
		case indexTypeStation:
			// 三级兜底：位置信息 → 设备编码 → 当前位置（JAVA L537-560）
			station := pickFromMap(stationMap, devLocatCode, devCodeID, locationCode)
			if station != nil {
				trailBo.DevCode = station.TollCode
				trailBo.DevName = station.TollName
				if toll := station.OdsSzdnToll; toll != nil {
					if lon == nil && utils.IsNotBlank(model.Val(toll.Longitude)) {
						trailBo.Lon = parseFloatPtr(model.Val(toll.Longitude))
					}
					if lat == nil && utils.IsNotBlank(model.Val(toll.Latitude)) {
						trailBo.Lat = parseFloatPtr(model.Val(toll.Latitude))
					}
					if utils.IsBlank(roadCode) {
						trailBo.RoadCode = utils.IsNull(toll.RoadCode)
					}
					if utils.IsBlank(sectionCode) {
						trailBo.SectionCode = utils.IsNull(toll.SectionCode)
					}
					if utils.IsBlank(pileno) {
						trailBo.Pileno = utils.IsNull(toll.PileNo)
					}
				}
			}

		case indexTypeGantry:
			gantry := pickFromMap(gantryMap, devLocatCode, devCodeID, locationCode)
			if gantry != nil {
				trailBo.DevCode = gantry.GantryCode
				trailBo.DevName = gantry.GantryName
				if g := gantry.OdsSzdnGantry; g != nil {
					if lon == nil && utils.IsNotBlank(model.Val(g.Lon)) {
						trailBo.Lon = parseFloatPtr(model.Val(g.Lon))
					}
					if lat == nil && utils.IsNotBlank(model.Val(g.Lat)) {
						trailBo.Lat = parseFloatPtr(model.Val(g.Lat))
					}
					if utils.IsBlank(roadCode) {
						trailBo.RoadCode = utils.IsNull(g.RoadCode)
					}
					if utils.IsBlank(sectionCode) {
						trailBo.SectionCode = utils.IsNull(g.SectionCode)
					}
					if utils.IsBlank(pileno) {
						trailBo.Pileno = utils.IsNull(g.PileNo)
					}
					trailBo.Direction = model.Val(g.Direction)
					trailBo.IsVirtual = model.Val(g.IsVirtual) // 虚拟门架
				}
			}

		case indexTypeServiceArea:
			// JAVA L683: devip: → serviceip: 后再查位置字典
			locationCode = strings.ReplaceAll(locationCode, "devip:", "serviceip:")
			if loc, ok := locationMap[locationCode]; ok && loc != nil {
				trailBo.DevCode = model.Val(loc.StandardCode)
				trailBo.DevName = model.Val(loc.Name)
				if loc.Longitude != nil {
					trailBo.Lon = loc.Longitude
				}
				if loc.Latitude != nil {
					trailBo.Lat = loc.Latitude
				}
				trailBo.RoadCode = utils.IsNull(loc.Roadcode)
				trailBo.SectionCode = utils.IsNull(loc.Sectioncode)
				trailBo.Pileno = utils.IsNull(loc.PileNo)
				trailBo.Direction = model.AnyStrVal(loc.Direction)
			}
		}

		// 设备名称兜底：用位置 code（JAVA L739-741）
		if utils.IsBlank(trailBo.DevName) {
			trailBo.DevName = strings.ReplaceAll(utils.IsNull(locationCode), "serviceip:", "")
		}
	}

	// JAVA L746-753
	tracks.FirtStationCode = model.Str(firtStationCode)
	tracks.FirtStationName = model.Str(firtStationName)
	tracks.FirtStationTime = model.Str(firtStationTime)
	tracks.PlateColor = model.Str(plateColor)
	tracks.CarType = model.Str(carType)
	tracks.CarVehicle = model.Str(carVehicle)
	tracks.CarNum = carNum
	tracks.PassType = model.Str(passType)

	// JAVA L757-764: 只统计经纬度都齐的点，用于推导起终点
	jwdList := make([]*model.TrailBo, 0, len(points))
	for i := range points {
		if points[i].Lon != nil && points[i].Lat != nil {
			jwdList = append(jwdList, &points[i])
		}
	}

	if utils.IsNull(tracks.Flag) == trackFlagCurrent {
		// 实时轨迹：直接用首尾轨迹点（JAVA L767-784）
		if len(jwdList) > 0 {
			first := jwdList[0]
			tracks.Entollstationid = model.Str(utils.IsNull(first.DevCode))
			tracks.Entollstationname = model.Str(utils.IsNull(first.DevName))
			tracks.StartLon = model.Str(utils.IsNull(first.Lon))
			tracks.StratLat = model.Str(utils.IsNull(first.Lat))
			if len(jwdList) > 1 {
				last := jwdList[len(jwdList)-1]
				tracks.Extollstationid = model.Str(utils.IsNull(last.DevCode))
				tracks.Extollstationname = model.Str(utils.IsNull(last.DevName))
				tracks.EndLon = model.Str(utils.IsNull(last.Lon))
				tracks.EndLat = model.Str(utils.IsNull(last.Lat))
			}
		}
	} else {
		// 历史轨迹：先按 code 查收费站/门架，再按名称兜底（JAVA L785-923）
		firstCode := utils.IsNull(tracks.Entollstationid)
		firstName := utils.RepalaceSzdnTollName(model.Val(tracks.Entollstationname))
		endCode := utils.IsNull(tracks.Extollstationid)
		endName := utils.RepalaceSzdnTollName(model.Val(tracks.Extollstationname))

		if utils.IsNotBlank(firstCode) {
			if toll, ok := tollMap[firstCode]; ok && toll != nil {
				if utils.IsNotBlank(model.Val(toll.Longitude)) {
					tracks.StartLon = toll.Longitude
				}
				if utils.IsNotBlank(model.Val(toll.Latitude)) {
					tracks.StratLat = toll.Latitude
				}
				tracks.Entollstationid = model.Str(utils.IsNull(toll.TollCode))
			} else if gantry, ok := gantryMap[firstCode]; ok && gantry != nil {
				if g := gantry.OdsSzdnGantry; g != nil {
					if utils.IsNotBlank(model.Val(g.Lon)) {
						tracks.StartLon = g.Lon
					}
					if utils.IsNotBlank(model.Val(g.Lat)) {
						tracks.StratLat = g.Lat
					}
				}
			}
		}

		if utils.IsBlank(model.Val(tracks.StartLon)) && utils.IsNotBlank(firstName) {
			if station, ok := stationMap[firstName]; ok && station != nil {
				if toll := station.OdsSzdnToll; toll != nil {
					if utils.IsNotBlank(model.Val(toll.Longitude)) {
						tracks.StartLon = toll.Longitude
					}
					if utils.IsNotBlank(model.Val(toll.Latitude)) {
						tracks.StratLat = toll.Latitude
					}
				}
				tracks.Entollstationid = model.Str(utils.IsNull(station.TollCode))
			} else if gantry, ok := gantryMap[firstName]; ok && gantry != nil {
				if g := gantry.OdsSzdnGantry; g != nil {
					if utils.IsNotBlank(model.Val(g.Lon)) {
						tracks.StartLon = g.Lon
					}
					if utils.IsNotBlank(model.Val(g.Lat)) {
						tracks.StratLat = g.Lat
					}
				}
				tracks.Entollstationid = model.Str(utils.IsNull(gantry.GantryCode))
			}
		}

		if utils.IsNotBlank(endCode) {
			if toll, ok := tollMap[endCode]; ok && toll != nil {
				if utils.IsNotBlank(model.Val(toll.Longitude)) {
					tracks.EndLon = toll.Longitude
				}
				if utils.IsNotBlank(model.Val(toll.Latitude)) {
					tracks.EndLat = toll.Latitude
				}
				tracks.Extollstationid = model.Str(utils.IsNull(toll.TollCode))
			} else if gantry, ok := gantryMap[endCode]; ok && gantry != nil {
				if g := gantry.OdsSzdnGantry; g != nil {
					if utils.IsNotBlank(model.Val(g.Lon)) {
						tracks.EndLon = g.Lon
					}
					if utils.IsNotBlank(model.Val(g.Lat)) {
						tracks.EndLat = g.Lat
					}
				}
			}
		}

		if utils.IsBlank(model.Val(tracks.EndLon)) && utils.IsNotBlank(endName) {
			if station, ok := stationMap[endName]; ok && station != nil {
				if toll := station.OdsSzdnToll; toll != nil {
					if utils.IsNotBlank(model.Val(toll.Longitude)) {
						tracks.EndLon = toll.Longitude
					}
					if utils.IsNotBlank(model.Val(toll.Latitude)) {
						tracks.EndLat = toll.Latitude
					}
				}
				tracks.Extollstationid = model.Str(utils.IsNull(station.TollCode))
			} else if gantry, ok := gantryMap[endName]; ok && gantry != nil {
				if g := gantry.OdsSzdnGantry; g != nil {
					if utils.IsNotBlank(model.Val(g.Lon)) {
						tracks.EndLon = g.Lon
					}
					if utils.IsNotBlank(model.Val(g.Lat)) {
						tracks.EndLat = g.Lat
					}
				}
				tracks.Extollstationid = model.Str(utils.IsNull(gantry.GantryCode))
			}
		}
	}

	// JAVA L945-956: 字符串经纬度再转一份小数，供前端直接画图
	if utils.IsNotBlank(model.Val(tracks.StartLon)) {
		tracks.StartLonDec = parseFloatPtr(model.Val(tracks.StartLon))
	}
	if utils.IsNotBlank(model.Val(tracks.StratLat)) {
		tracks.StratLatDec = parseFloatPtr(model.Val(tracks.StratLat))
	}
	if utils.IsNotBlank(model.Val(tracks.EndLon)) {
		tracks.EndLonDec = parseFloatPtr(model.Val(tracks.EndLon))
	}
	if utils.IsNotBlank(model.Val(tracks.EndLat)) {
		tracks.EndLatDec = parseFloatPtr(model.Val(tracks.EndLat))
	}

	trailInfo.Tracks = tracks
	trailInfo.TrailList = points
	return trailInfo, nil
}

// GetByTrailBo 对应 getByTrailBo(TrailBo)（L969-1223）：
// 按 stateType 去对应流水表按 uuid 取抓拍对象，拼出图片地址，最后做一次域名替换。
func (s *SysUtilService) GetByTrailBo(ctx context.Context, trailBo *model.TrailBo) (*model.TrailBo, error) {
	if trailBo == nil {
		return &model.TrailBo{}, nil
	}
	target := *trailBo // DIFF: Java 就地修改入参，Go 返回副本

	// JAVA L984-999: 只取日期，扩成当天 00:00:00 ~ 23:59:59
	applyTime1, applyTime2 := "", ""
	captureTime := utils.IsNull(target.CaptureTime)
	if utils.IsNotBlank(captureTime) {
		if t, err := model.ParseTime(captureTime); err == nil && !t.IsZero() {
			day := t.Format(utils.LayoutDate)
			applyTime1 = day + " 00:00:00"
			applyTime2 = day + " 23:59:59"
		} else {
			slog.Info("[轨迹查询] 日期解析失败", "captureTime", captureTime)
		}
	}
	from, _ := model.ParseTime(applyTime1)
	to, _ := model.ParseTime(applyTime2)

	stateType := utils.IsNull(target.StateType)
	pointUuid := target.PointUuid

	switch stateType {
	case DataTypeBorderWeighing:
		if item := s.lookupWeight(ctx, pointUuid); item != nil {
			if imagesStr := utils.IsNull(item.WeighingImagesArry); utils.IsNotBlank(imagesStr) {
				imgs, err := weighingImages(imagesStr)
				if err != nil {
					slog.Warn("[轨迹查询] 省界称重图片 JSON 解析失败", "uuid", pointUuid, "err", err)
				} else {
					target.ImagesArry = utils.DeleteEnd(imgs)
				}
			}
		}

	case DataTypeGantryCapture:
		if item := s.lookupGantryCapture(ctx, pointUuid, from, to); item != nil {
			target.ImagesArry = model.Val(item.Snappicturepath)
			target.Platecolor = utils.IsNull(item.Platecolor)
		}

	case DataTypeProvCapture:
		if item := s.lookupProvCapture(ctx, pointUuid); item != nil {
			imagesSrc := ""
			if utils.IsNotBlank(model.Val(item.Plateimage)) {
				imagesSrc += model.Val(item.Plateimage) + ","
			}
			if utils.IsNotBlank(model.Val(item.Sideimage)) {
				imagesSrc += model.Val(item.Sideimage) + ","
			}
			if utils.IsNotBlank(model.Val(item.Headimage)) {
				imagesSrc += model.Val(item.Headimage) + ","
			}
			target.ImagesArry = utils.DeleteEnd(imagesSrc)
		}

	case DataTypeServiceAreaCapture:
		if item := s.lookupFwqclls(ctx, pointUuid); item != nil {
			imagesSrc := ""
			if utils.IsNotBlank(model.Val(item.Targetpicurl)) {
				imagesSrc += model.Val(item.Targetpicurl) + ","
			}
			if utils.IsNotBlank(model.Val(item.Platepicurl)) {
				imagesSrc += model.Val(item.Platepicurl) + ","
			}
			target.ImagesArry = utils.DeleteEnd(imagesSrc)
		}

	case DataTypeStationCapture:
		if item := s.lookupStationCapture(ctx, pointUuid, from, to); item != nil {
			target.ImagesArry = model.Val(item.Snappicturepath)
		}

	case DataTypeFeeRecord:
		if item := s.lookupFeeRecord(ctx, pointUuid, from, to); item != nil {
			target.DevCode = model.Val(item.Gantryid)
			target.ImagesArry = ""
		}

	case DataTypeFeeStationEnter:
		if item := s.lookupFeeEnter(ctx, pointUuid); item != nil {
			target.ImagesArry = ""
		}

	case DataTypeFeeStationExit:
		if item := s.lookupFeeExit(ctx, pointUuid); item != nil {
			target.ImagesArry = ""
		}
	}

	// JAVA L1218-1220: 收尾逗号 + 内网图片域名替换
	target.ImagesArry = utils.RepalacePicUrl(utils.DeleteEnd(target.ImagesArry))
	return &target, nil
}

// ---------- 抓拍对象缓存读取（对应 8 个 *ServiceImpl.selectXxxByQueryUuids 的循环体） ----------

// lookupByUUID 是 "ByQueryUuids" 的单条版本：先读 Redis，未命中回源；
// 回源为空时把"探测对象"写回缓存 —— 与 Java 完全一致（L79-81），
// 目的是让不存在的 uuid 也命中缓存，避免同一批轨迹反复打 8 亿级大表。
func lookupByUUID[T any](ctx context.Context, c *cache.Client, prefix, uuid string, probe T,
	load func(context.Context) (*T, error)) *T {

	if utils.IsBlank(uuid) {
		return nil
	}
	key := prefix + uuid
	if c != nil {
		var cached T
		if ok, err := c.GetJSON(ctx, key, &cached); err == nil && ok {
			return &cached
		}
	}
	item, err := load(ctx)
	if err != nil {
		slog.Warn("[轨迹查询] 抓拍对象回源失败", "key", key, "err", err)
		return nil
	}
	if item == nil {
		item = &probe
	}
	if c != nil {
		if err := c.SetJSON(ctx, key, item, 0); err != nil {
			slog.Warn("[轨迹查询] 抓拍对象写缓存失败", "key", key, "err", err)
		}
	}
	return item
}

func (s *SysUtilService) lookupWeight(ctx context.Context, uuid string) *model.OdsSzdnProvinceBorderVehicleWeightNewstructure {
	return lookupByUUID(ctx, s.cache, dateBorderWeighingPrefix, uuid,
		model.OdsSzdnProvinceBorderVehicleWeightNewstructure{Datauuid: model.Str(uuid)},
		func(ctx context.Context) (*model.OdsSzdnProvinceBorderVehicleWeightNewstructure, error) {
			list, err := s.weightRepo.ListByDatauuid(ctx, uuid)
			return firstOrNil(list, err)
		})
}

// WeightCaptureMap 对应
// OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl
// .selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(String)（L62-88）：
// 入参是逗号分隔的 uuid 串，返回「uuid → 抓拍对象」的 Map（/base/vehicleweight/map 用它）。
//
// DIFF: Java 把这个方法放在 weight 的 ServiceImpl 里；Go 侧归到 SysUtilService，因为
// 缓存读取/负缓存逻辑（lookupByUUID）都在这里，复制一份会让“缓存 key 拼错”出现两个副本。
//
// PARITY(照抄的奇效): Java 的 L71-72 会把“缓存里读到的对象”无条件放进 Map，
// 而负缓存写入的正是只带 datauuid 的“探测对象”——所以同一个空 uuid 第二次请求会从
// `{}` 变成 `{uuid: 探测对象}`。这里保持同样行为。
func (s *SysUtilService) WeightCaptureMap(ctx context.Context, uuids string) map[string]*model.OdsSzdnProvinceBorderVehicleWeightNewstructure {
	out := make(map[string]*model.OdsSzdnProvinceBorderVehicleWeightNewstructure)
	if utils.IsBlank(uuids) {
		return out
	}
	for _, uuid := range strings.Split(uuids, ",") {
		if uuid = strings.TrimSpace(uuid); uuid == "" {
			continue
		}
		key := dateBorderWeighingPrefix + uuid
		if s.cache != nil {
			var cached model.OdsSzdnProvinceBorderVehicleWeightNewstructure
			if ok, err := s.cache.GetJSON(ctx, key, &cached); err == nil && ok {
				out[uuid] = &cached
				continue
			}
		}
		list, err := s.weightRepo.ListByDatauuid(ctx, uuid)
		if err != nil {
			slog.Warn("[称重抓拍] 回源失败", "uuid", uuid, "err", err)
			continue
		}
		if len(list) > 0 {
			out[uuid] = &list[0]
			if s.cache != nil {
				_ = s.cache.SetJSON(ctx, key, &list[0], 0)
			}
			continue
		}
		// 未命中：只写负缓存，不进 Map（与 L80-82 一致）
		if s.cache != nil {
			_ = s.cache.SetJSON(ctx, key, &model.OdsSzdnProvinceBorderVehicleWeightNewstructure{Datauuid: model.Str(uuid)}, 0)
		}
	}
	return out
}

func (s *SysUtilService) lookupGantryCapture(ctx context.Context, uuid string, from, to time.Time) *model.OdsRtSzdnSnapshotFlowAddcode {
	return lookupByUUID(ctx, s.cache, dateGantryPrefix, uuid,
		model.OdsRtSzdnSnapshotFlowAddcode{Datauuid: model.Str(uuid)},
		func(ctx context.Context) (*model.OdsRtSzdnSnapshotFlowAddcode, error) {
			list, err := s.gantryCaptureRepo.ListByDatauuid(ctx, uuid, from, to)
			return firstOrNil(list, err)
		})
}

func (s *SysUtilService) lookupProvCapture(ctx context.Context, uuid string) *model.OdsRtSzdnSnapshotFlowProvcaptureAddcode {
	return lookupByUUID(ctx, s.cache, dateProvPrefix, uuid,
		model.OdsRtSzdnSnapshotFlowProvcaptureAddcode{Datauuid: model.Str(uuid)},
		func(ctx context.Context) (*model.OdsRtSzdnSnapshotFlowProvcaptureAddcode, error) {
			list, err := s.provCaptureRepo.ListByDatauuid(ctx, uuid)
			return firstOrNil(list, err)
		})
}

func (s *SysUtilService) lookupFwqclls(ctx context.Context, uuid string) *model.OdsCxztFwqclls {
	return lookupByUUID(ctx, s.cache, dateServiceAreaPrefix, uuid,
		model.OdsCxztFwqclls{Datauuid: model.Str(uuid)},
		func(ctx context.Context) (*model.OdsCxztFwqclls, error) {
			list, err := s.fwqcllsRepo.ListByDatauuid(ctx, uuid)
			return firstOrNil(list, err)
		})
}

func (s *SysUtilService) lookupStationCapture(ctx context.Context, uuid string, from, to time.Time) *model.OdsRtSzdnSnapshotFlowStationcaptureAddcode {
	return lookupByUUID(ctx, s.cache, dateStationPrefix, uuid,
		model.OdsRtSzdnSnapshotFlowStationcaptureAddcode{Datauuid: model.Str(uuid)},
		func(ctx context.Context) (*model.OdsRtSzdnSnapshotFlowStationcaptureAddcode, error) {
			list, err := s.stationCaptureRepo.ListByDatauuid(ctx, uuid, from, to)
			return firstOrNil(list, err)
		})
}

func (s *SysUtilService) lookupFeeRecord(ctx context.Context, cid string, from, to time.Time) *model.OdsLwzxsfsjFeeRecords01 {
	return lookupByUUID(ctx, s.cache, dateFeeRecordPrefix, cid,
		model.OdsLwzxsfsjFeeRecords01{Cid: model.Str(cid)},
		func(ctx context.Context) (*model.OdsLwzxsfsjFeeRecords01, error) {
			list, err := s.feeRecordsRepo.ListByCid(ctx, cid, from, to)
			return firstOrNil(list, err)
		})
}

func (s *SysUtilService) lookupFeeEnter(ctx context.Context, cid string) *model.OdsLwzxsfsjFeeStationEnter01 {
	return lookupByUUID(ctx, s.cache, dateFeeStationEnterPrefix, cid,
		model.OdsLwzxsfsjFeeStationEnter01{Cid: model.Str(cid)},
		func(ctx context.Context) (*model.OdsLwzxsfsjFeeStationEnter01, error) {
			list, err := s.feeEnterRepo.ListByCid(ctx, cid)
			return firstOrNil(list, err)
		})
}

func (s *SysUtilService) lookupFeeExit(ctx context.Context, cid string) *model.OdsLwzxsfsjFeeStationExit01 {
	return lookupByUUID(ctx, s.cache, dateFeeStationExitPrefix, cid,
		model.OdsLwzxsfsjFeeStationExit01{Cid: model.Str(cid)},
		func(ctx context.Context) (*model.OdsLwzxsfsjFeeStationExit01, error) {
			list, err := s.feeExitRepo.ListByCid(ctx, cid)
			return firstOrNil(list, err)
		})
}

// ---------- 通用小工具 ----------

// firstOrNil 对应 `list.size() > 0 ? list.get(0) : null`
func firstOrNil[T any](list []T, err error) (*T, error) {
	if err != nil {
		return nil, err
	}
	if len(list) == 0 {
		return nil, nil
	}
	return &list[0], nil
}

// pickFromMap 对应 Java 的三级兜底取值：按给定顺序找第一个非空 key 的命中项。
func pickFromMap[T any](m map[string]*T, keys ...string) *T {
	for _, k := range keys {
		if utils.IsBlank(k) {
			continue
		}
		if v, ok := m[k]; ok && v != nil {
			return v
		}
	}
	return nil
}

// jsonString 等价于 JSONObject.getString(key)：字符串直接取，数字/布尔退化成原样文本。
func jsonString(obj map[string]json.RawMessage, key string) string {
	raw, ok := obj[key]
	if !ok {
		return ""
	}
	var s string
	if err := json.Unmarshal(raw, &s); err == nil {
		return s
	}
	return strings.Trim(string(raw), `"`)
}

// weighingImages 对应 getByTrailBo L1118-1132：解析省界称重的图片数组，拼出逗号串。
func weighingImages(imagesStr string) (string, error) {
	var arr []struct {
		SnapPicturePath string `json:"snapPicturePath"`
	}
	if err := json.Unmarshal([]byte(imagesStr), &arr); err != nil {
		return "", err
	}
	var b strings.Builder
	for _, item := range arr {
		if src := utils.IsNull(item.SnapPicturePath); src != "" {
			b.WriteString(src)
			b.WriteString(",")
		}
	}
	return b.String(), nil
}
