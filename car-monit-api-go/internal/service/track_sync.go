package service

// JAVA 对照:
//
//	pro-business-api/.../service/impl/SysUtilServiceImpl.java:284-387    syncTrack（实时轨迹落缓存）
//	pro-business-api/.../service/impl/SysUtilServiceImpl.java:1962-1987  carTrackQuery（历史轨迹查询）
//	pro-business-api/src/main/java/com/ruoyi/base/task/TrackTask.java:54-59    syncCurrentTrack（每 3 分钟）
//	pro-business-api/src/main/java/com/ruoyi/base/task/TrackTask.java:84-160   syncHistroyTrack（每天 4 点）
//	pro-base-common/.../common/constant/Constants.java:274,285,314,320,326
//	                                                                     trail: / car_list_jc /
//	                                                                     car_history_trail: /
//	                                                                     car_sync_time: /
//	                                                                     car_curent_trail:
//
// 类/职责: 重点车辆（car_list_jc）的「实时轨迹」与「历史轨迹」落缓存链路
// 对应 Go 文件: internal/service/track_sync.go
//
// 关键映射:
//
//	redisCache.getCacheObject(car_list_jc)        → keyVehicles（GetJSON → []CarVO）
//	redisCache.getCacheObject("trail:"+carNo)     → s.cache.Get(trailKeyPrefix + carNo)
//	mapTrailBoList(josnList)                      → s.mapTrailBoList（同文件 235 行，4 分钟去重）
//	changeData(tracks, rtnList)                   → s.ChangeData（5 张字典富集）
//	redisCache.setCacheObject(car_curent_trail:*) → s.cache.SetJSON(carCurrentTrailPrefix+carNo, info)
//
// DIFF: Java 的 syncTrack / carTrackQuery 属于 SysUtilServiceImpl，而 syncHistroyTrack 的循环体
// 写在 @Component 的 TrackTask 里。Go 把三个方法都放在 service 包：scheduler 只负责「什么时候跑」，
// 「跑什么」留在 service —— 否则 scheduler 要反向依赖 Redis 序列化与轨迹富集的细节。
//
// PARITY(照抄不修):
//  1. Java 的 syncTrack 用 `redisSourceFactory.createSource(redisConfig)` 建 JedisCluster 读
//     `trail:{carNo}`（application.yml:138 rediscluster.clusterNodes），Go 侧还没有第二套集群客户端，
//     统一从主 Redis 读，并在非 local 环境打 WARN。接入该集群前，生产模式的实时轨迹会是空的。
//  2. Java 的变量名 threeMinutesInMillis 实际是 24 小时（L299），阈值按 24h 走，不按 3 分钟。
//  3. syncHistroyTrack 里 `carSynctime.equals("")` 的「同步时间存在 → yiyue（1 个月）」注释写着 1 月，
//     而 XML:148 的注释写「三天之前」，SQL 是 `now() - 3` —— 以 SQL 为准。
//  4. Java 拼的缓存键是 car_curent_trail（少一个 r），Go 原样保留，改名会让灰度期读不到旧键。
//  5. Java 的 syncTrack 不判空车牌，车牌为 null 时会去读键名就叫 "trail:" 的缓存；
//     Go 侧直接跳过空车牌——那是运维数据脏了，不应该变成一个全车共享的怪键。

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strconv"
	"strings"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// 缓存键，对应 Constants.java:274-326（拼写与 Java 完全一致）
const (
	// carListJCKey 重点车辆库（由运维任务写入）。PARITY: handler/sysutil.go 里有一份同值副本，
	// 因为那个包只读、且不希望为了一个字符串常量反向依赖 service —— 改键时两处都要动。
	carListJCKey          = "car_list_jc"
	trailKeyPrefix        = "trail:"
	carHistoryTrailPrefix = "car_history_trail:"
	carSyncTimePrefix     = "car_sync_time:"
	carCurrentTrailPrefix = "car_curent_trail:"

	// 实时轨迹点的新鲜度窗口：PARITY 见文件头第 2 条（Java 变量名写着 threeMinutes，值是 24h）
	realtimeTrailWindow = 24 * time.Hour

	// syncTrack 里 tracks.uuid 的后缀日期格式（JAVA L367）
	layoutDateCompact = "20060102"
)

// keyVehicles 对应 `(List<CarVO>) redisCache.getCacheObject(Constants.car_list_jc)`（L285-289 / L88-92）。
//
// PARITY: 缓存缺失或内容损坏时返回空列表。Java 会得到 null 或抛 ClassCastException，
// 在 @Scheduled 里被 Spring 吞成一条错误日志；Go 侧显式判空，等价于"这轮什么都不做"。
func (s *SysUtilService) keyVehicles(ctx context.Context) []model.CarVO {
	if s.cache == nil {
		return nil
	}
	var list []model.CarVO
	ok, err := s.cache.GetJSON(ctx, carListJCKey, &list)
	if err != nil {
		slog.Warn("[轨迹同步] 重点车辆缓存解析失败", "key", carListJCKey, "err", err)
		return nil
	}
	if !ok {
		slog.Info("[轨迹同步] 重点车辆缓存为空，本轮跳过", "key", carListJCKey)
		return nil
	}
	return list
}

// cachedTrailPoint 对应 Java 用 FastJson 手工解出来的那 10 个字段（L317-341）。
//
// 注意 Java 只赋值 pointUuid/stateType/captureTime/locationCode/locationName/
// standardCode/locationId/platenumber，外加 lon/lat 两个 BigDecimal —— 其余字段保持零值。
type cachedTrailPoint struct {
	PointUuid    string     `json:"pointUuid"`
	StateType    string     `json:"stateType"`
	CaptureTime  string     `json:"captureTime"`
	LocationCode string     `json:"locationCode"`
	LocationName string     `json:"locationName"`
	StandardCode string     `json:"standardCode"`
	LocationID   string     `json:"locationId"`
	PlateNumber  string     `json:"platenumber"`
	Longitude    flexString `json:"longitude"`
	Latitude     flexString `json:"latitude"`
}

// flexString 复刻 FastJson 的 JSONObject#getString：字符串原样返回，数字/布尔返回其字面量。
//
// DIFF: encoding/json 直接解到 string 会在 "longitude": 113.9 时报错，而 Java 不会。
type flexString string

func (f *flexString) UnmarshalJSON(b []byte) error {
	s := strings.TrimSpace(string(b))
	switch {
	case s == "" || s == "null":
		*f = ""
	case s[0] == '"':
		var v string
		if err := json.Unmarshal(b, &v); err != nil {
			return err
		}
		*f = flexString(v)
	default:
		*f = flexString(s)
	}
	return nil
}

func (f flexString) String() string { return string(f) }

// SyncTrack 对应 syncTrack(CarParaVO)（L284-387）：把 `trail:{carNo}` 里的原始轨迹点
// 富集成 TrailInfo 后写入 `car_curent_trail:{carNo}`，供实时轨迹页面直接读取。
//
// 入参：Java 的 `syncTrack(new CarParaVO())` 从未使用该参数，Go 侧直接省掉。
func (s *SysUtilService) SyncTrack(ctx context.Context) error {
	vehicles := s.keyVehicles(ctx)
	if len(vehicles) == 0 {
		return nil
	}

	now := time.Now()
	today := now.Format(layoutDateCompact)

	// JAVA L305 / L345：isLocalhost == "local" 时不做 24 小时新鲜度过滤
	local := strings.EqualFold(s.env, "local")
	if !local {
		slog.Warn("[实时轨迹同步] 当前 env 非 local，但 Go 侧尚未接入 rediscluster；trail:{carNo} 改为读主 Redis",
			"env", s.env)
	}

	slog.Info("[实时轨迹同步] 开始", "env", s.env, "cars", len(vehicles))
	synced := 0

	for _, car := range vehicles {
		if err := ctx.Err(); err != nil {
			return err
		}
		carNo := utils.IsNull(car.CarNo)
		if utils.IsBlank(carNo) {
			continue
		}

		keyValue, ok, err := s.cache.Get(ctx, trailKeyPrefix+carNo)
		if err != nil {
			slog.Warn("[实时轨迹同步] 读取原始轨迹失败", "carNo", carNo, "err", err)
			continue
		}
		if !ok || utils.IsBlank(keyValue) {
			continue
		}

		var raw []cachedTrailPoint
		if err := json.Unmarshal([]byte(keyValue), &raw); err != nil {
			// JAVA: JSON.parseArray 抛异常 → @Scheduled 整体中断；Go 侧降级为跳过该车
			slog.Warn("[实时轨迹同步] 轨迹点不是合法 JSON 数组，跳过该车", "carNo", carNo, "err", err)
			continue
		}

		points := make([]model.TrailBo, 0, len(raw))
		for _, p := range raw {
			bo := model.TrailBo{
				PointUuid:    p.PointUuid,
				StateType:    p.StateType,
				CaptureTime:  p.CaptureTime,
				LocationCode: p.LocationCode,
				LocationName: p.LocationName,
				StandardCode: p.StandardCode,
				LocationId:   p.LocationID,
				Platenumber:  p.PlateNumber,
				DevCode:      p.StandardCode, // JAVA L340
				DevName:      p.LocationName, // JAVA L341
			}
			if lon := p.Longitude.String(); utils.IsNotBlank(lon) {
				if v, err := strconv.ParseFloat(lon, 64); err == nil {
					bo.Lon = &v
				} else {
					// JAVA: new BigDecimal(lon) 会抛异常并中断整轮；这里只丢字段
					slog.Warn("[实时轨迹同步] 经度不是数字", "carNo", carNo, "lon", lon)
				}
			}
			if lat := p.Latitude.String(); utils.IsNotBlank(lat) {
				if v, err := strconv.ParseFloat(lat, 64); err == nil {
					bo.Lat = &v
				} else {
					slog.Warn("[实时轨迹同步] 纬度不是数字", "carNo", carNo, "lat", lat)
				}
			}

			// JAVA L344-360：local 全收；生产只保留与当前时间相差 24h 以内的点
			if local {
				points = append(points, bo)
				continue
			}
			if utils.IsBlank(bo.CaptureTime) {
				continue
			}
			capTime, err := time.ParseInLocation(layoutNormalTime, bo.CaptureTime, time.Local)
			if err != nil {
				// JAVA L356-358：解析失败只记日志，不中断
				slog.Info("[实时轨迹同步] 实时轨迹日期解析失败", "carNo", carNo, "captureTime", bo.CaptureTime)
				continue
			}
			if diff := now.Sub(capTime); diff <= realtimeTrailWindow && diff >= -realtimeTrailWindow {
				points = append(points, bo)
			}
		}

		// JAVA L363-381
		rtnList := s.mapTrailBoList(points)
		if len(rtnList) == 0 {
			continue
		}

		tracks := &model.ZdataTrailTracks{
			PlateKey: model.Str(carNo),
			Uuid:     model.Str(carNo + "@@" + today), // JAVA L372
			Flag:     model.Str(trackFlagCurrent),     // JAVA L373 —— "currentTrack"
		}
		info, err := s.ChangeData(ctx, tracks, rtnList)
		if err != nil {
			slog.Error("[实时轨迹同步] 设备富集失败", "carNo", carNo, "err", err)
			continue
		}
		info.TrailUuid = carNo // JAVA L377

		if err := s.cache.SetJSON(ctx, carCurrentTrailPrefix+carNo, info, 0); err != nil {
			slog.Error("[实时轨迹同步] 写缓存失败", "carNo", carNo, "err", err)
			continue
		}
		synced++
	}

	slog.Info("[实时轨迹同步] 结束", "cars", len(vehicles), "synced", synced)
	return nil
}

// CarTrackQuery 对应 carTrackQuery(CarParaVO)（L1962-1987）：
// carlist 拍平成 carNoList → 查 zdata_trail_fitting → 逐条富集成 TrailInfo。
//
// PARITY: 与 carTrackQueryNew 的差别只在返回值形态（TrailInfo 列表 vs tracks 列表），
// 检索条件完全相同，因此复用 BuildTrailInfos（clearTrailPoints=false，对应 L1978 那句被注释掉的
// `// tracks.setTrailPoints("")`）。
func (s *SysUtilService) CarTrackQuery(ctx context.Context, vo *model.CarParaVO) ([]model.TrailInfo, error) {
	if vo == nil {
		return nil, fmt.Errorf("CarTrackQuery: carParaVO 不能为空")
	}
	// JAVA L1964-1968：carlist → carNoList
	if len(vo.Carlist) > 0 {
		carNoList := make([]string, 0, len(vo.Carlist))
		for _, c := range vo.Carlist {
			if utils.IsNotBlank(c.CarNo) {
				carNoList = append(carNoList, c.CarNo)
			}
		}
		vo.CarNoList = carNoList
	}

	list, err := s.trailRepo.GetHistoryTrail(ctx, vo, 0)
	if err != nil {
		return nil, err
	}
	return s.BuildTrailInfos(ctx, list, false)
}

// SyncHistoryTrack 对应 TrackTask.syncHistroyTrack()（TrackTask.java:84-160）。
//
// 行为（逐段对齐 Java）：
//  1. 取 car_list_jc，为空直接返回；
//  2. 逐车：car_sync_time:{carNo} 不存在 → flag=bannian，存在 → flag=yiyue（对应 XML 的两个时间窗）；
//  3. carTrackQuery 查该车轨迹，只保留 trailList 非空的条目；
//  4. 与缓存里的 car_history_trail:{carNo} 按 tracks.uuid 去重合并（新数据优先）；
//  5. 回写合并结果，并把本次同步时间写进 car_sync_time:{carNo}。
//
// PARITY: Java 的 `carlist` 是从 Redis 反序列化出来的 List<CarVO>，Go 侧是 []CarVO（JSON）。
// 灰度期两套服务不能共用 car_history_trail:* / car_sync_time:* —— 序列化格式不兼容（见 README 第 10 节）。
func (s *SysUtilService) SyncHistoryTrack(ctx context.Context) error {
	vehicles := s.keyVehicles(ctx)
	if len(vehicles) == 0 {
		return nil
	}
	slog.Info("[历史轨迹同步] 开始", "cars", len(vehicles))
	done := 0

	for _, car := range vehicles {
		if err := ctx.Err(); err != nil {
			return err
		}
		carNo := utils.IsNull(car.CarNo)
		if utils.IsBlank(carNo) {
			continue
		}

		// --- JAVA L107-118：首次同步查半年，之后每次只补最近一个月 ---
		vo := &model.CarParaVO{CarNo: carNo}
		timeKey := carSyncTimePrefix + carNo
		lastSync, hasTime, err := s.cache.Get(ctx, timeKey)
		if err != nil {
			slog.Warn("[历史轨迹同步] 读取同步时间失败，按首次同步处理", "carNo", carNo, "err", err)
		}
		if hasTime && utils.IsNull(lastSync) != "" {
			vo.Flag = "yiyue"
		} else {
			vo.Flag = "bannian"
		}

		newList, err := s.CarTrackQuery(ctx, vo)
		if err != nil {
			slog.Error("[历史轨迹同步] 查询轨迹失败", "carNo", carNo, "flag", vo.Flag, "err", err)
			continue
		}

		// --- JAVA L120-131：只收 tracks 与 trailList 都非空的条目 ---
		historyKey := carHistoryTrailPrefix + carNo
		merged := make([]model.TrailInfo, 0, len(newList))
		uuids := make(map[string]struct{}, len(newList))
		for _, info := range newList {
			if info.Tracks == nil || len(info.TrailList) == 0 {
				continue
			}
			uuids[utils.IsNull(info.Tracks.Uuid)] = struct{}{}
			merged = append(merged, info)
		}

		// --- JAVA L133-146：旧缓存按 uuid 去重后追加 ---
		var old []model.TrailInfo
		if _, err := s.cache.GetJSON(ctx, historyKey, &old); err != nil {
			slog.Warn("[历史轨迹同步] 旧缓存解析失败，按空列表处理", "carNo", carNo, "err", err)
		}
		for _, info := range old {
			if info.Tracks == nil || len(info.TrailList) == 0 {
				continue
			}
			if _, dup := uuids[utils.IsNull(info.Tracks.Uuid)]; dup {
				continue
			}
			merged = append(merged, info)
		}

		// --- JAVA L148-153：先回写轨迹，再记同步时间 ---
		if err := s.cache.SetJSON(ctx, historyKey, merged, 0); err != nil {
			slog.Error("[历史轨迹同步] 写历史轨迹缓存失败", "carNo", carNo, "err", err)
			continue
		}
		if err := s.cache.Set(ctx, timeKey, model.FormatDateTime(time.Now())); err != nil {
			slog.Error("[历史轨迹同步] 写同步时间失败", "carNo", carNo, "err", err)
			continue
		}
		done++
	}

	slog.Info("[历史轨迹同步] 结束", "cars", len(vehicles), "synced", done)
	return nil
}
