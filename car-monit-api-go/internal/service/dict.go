package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/ZdataLocationDictServiceImpl.java:55-82
//           pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsSzdnGantryIpServiceImpl.java:66-138
//           pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsSzdnTollStationIpServiceImpl.java:66-95
//           pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsSzdnSectionServiceImpl.java:55-84
// 类/职责: DictRegistry — 四张"设备/位置字典"的 Redis 缓存 + 内存 Map 装配（原分散在 4 个 ServiceImpl）
// 对应 Go 文件: internal/service/dict.go
// 关键映射:
//   redisCache.getCacheObject(Constants.dev_post)       → dictKeyLocation
//   redisCache.getCacheObject(Constants.gantry_ip)      → dictKeyGantryIP
//   redisCache.getCacheObject(Constants.station_ip)     → dictKeyStationIP
//   redisCache.getCacheObject(Constants.SECTION_ROAD_MAP) → dictKeySection
//   updateRedis() 里"列表 + 关联表 in-memory join"       → loadGantryIPs / loadStationIPs
//   CommonUtil.isNull(x) 做 map key                      → utils.IsNull
//
// DIFF: Java 四个 ServiceImpl 各自持有一份 RedisCache + Mapper，互相之间靠 @Autowired 复用
// （TrailAggregationService 因此注入了 4 个 Service）。Go 侧收敛成一个 DictRegistry ——
// 轨迹富集只需要"四张 map"，不该为了拿 map 去依赖四个业务 Service（否则依赖图会绕回自己）。
//
// PARITY: 缓存 key 名与 Java 保持一致（dev_post / gantry_ip / station_ip / section_road_map），
// 但值是 Go 的 JSON 数组，不是 Java 的 JDK 序列化字节；切换版本前请 DEL 这四个 key（README「升级注意」）。

import (
	"context"
	"encoding/json"
	"log/slog"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// 缓存 key，对应 Constants.java:297-358
const (
	dictKeyLocation    = "dev_post"
	dictKeyGantryIP    = "gantry_ip"
	dictKeyStationIP   = "station_ip"
	dictKeySection     = "section_road_map"
	dictKeyStationInfo = "station_info"
	dictKeyGantryList  = "gantry_list"
)

// DictRegistry 字典注册表
type DictRegistry struct {
	locationRepo  *repo.ZdataLocationDictRepo
	gantryIPRepo  *repo.OdsSzdnGantryIpRepo
	gantryRepo    *repo.OdsSzdnGantryRepo
	stationIPRepo *repo.OdsSzdnTollStationIpRepo
	tollRepo      *repo.OdsSzdnTollRepo
	sectionRepo   *repo.OdsSzdnSectionRepo
	cache         *cache.Client
}

// NewDictRegistry 构造
func NewDictRegistry(locationRepo *repo.ZdataLocationDictRepo, gantryIPRepo *repo.OdsSzdnGantryIpRepo,
	gantryRepo *repo.OdsSzdnGantryRepo, stationIPRepo *repo.OdsSzdnTollStationIpRepo,
	tollRepo *repo.OdsSzdnTollRepo, sectionRepo *repo.OdsSzdnSectionRepo,
	cacheClient *cache.Client) *DictRegistry {

	return &DictRegistry{
		locationRepo: locationRepo, gantryIPRepo: gantryIPRepo, gantryRepo: gantryRepo,
		stationIPRepo: stationIPRepo, tollRepo: tollRepo, sectionRepo: sectionRepo, cache: cacheClient,
	}
}

// RefreshAll 对应四个 ServiceImpl 里的 updateRedis()：强制回源重建四份缓存。
//
// 用途：字典表在库里变更后由运维手动触发（原系统靠重启或直接调 updateRedis）。
// DIFF: 额外带上 TollMap（Constants.station_info），因为 changeData 的历史轨迹分支要用它查收费站坐标。
func (r *DictRegistry) RefreshAll(ctx context.Context) error {
	if _, err := r.LocationDictMap(ctx); err != nil {
		return err
	}
	if _, err := r.GantryIPMap(ctx); err != nil {
		return err
	}
	if _, err := r.StationIPMap(ctx); err != nil {
		return err
	}
	if _, err := r.SectionMap(ctx); err != nil {
		return err
	}
	if _, err := r.TollMap(ctx); err != nil {
		return err
	}
	if _, err := r.GantryMap(ctx); err != nil {
		return err
	}
	return nil
}

// LocationDictMap 对应 ZdataLocationDictServiceImpl.getRedisList()：
// key = raw_code（空值归一成 ""，与 Java 的 CommonUtil.isNull 一致）。
func (r *DictRegistry) LocationDictMap(ctx context.Context) (map[string]*model.ZdataLocationDict, error) {
	list, err := loadOrCache(ctx, r.cache, dictKeyLocation, r.locationRepo.ListAll)
	if err != nil {
		return nil, err
	}
	m := make(map[string]*model.ZdataLocationDict, len(list))
	for i := range list {
		item := &list[i]
		m[utils.IsNull(item.RawCode)] = item
	}
	return m, nil
}

// GantryIPMap 对应 OdsSzdnGantryIpServiceImpl.selectOdsSzdnGantryIpMap()：
// 同一行按 "裸 code/id + 4 种业务前缀" 注册多份 key，供不同上游事件用不同前缀查询。
//
// PARITY: Java 用 ""+rtn.getId() 把 *Long 转字符串；Go 的 Id 是 *int64，用 utils.IsNull 同样处理。
func (r *DictRegistry) GantryIPMap(ctx context.Context) (map[string]*model.OdsSzdnGantryIp, error) {
	list, err := r.loadGantryIPs(ctx)
	if err != nil {
		return nil, err
	}
	m := make(map[string]*model.OdsSzdnGantryIp, len(list)*6)
	for i := range list {
		item := &list[i]
		id := utils.IsNull(item.Id)
		code := utils.IsNull(item.GantryCode)
		for _, prefix := range []string{"gantryip:", "bwlocation:", "gantryid:", "gantry:"} {
			m[prefix+id] = item
			m[prefix+code] = item
		}
		m[id] = item
		m[code] = item
	}
	return m, nil
}

// StationIPMap 对应 OdsSzdnTollStationIpServiceImpl.selectStationIpMap()：
// 裸 ip / 裸 tollCode / 归一化站名，再各配 "stationip:"、"station:" 前缀。
func (r *DictRegistry) StationIPMap(ctx context.Context) (map[string]*model.OdsSzdnTollStationIp, error) {
	list, err := r.loadStationIPs(ctx)
	if err != nil {
		return nil, err
	}
	m := make(map[string]*model.OdsSzdnTollStationIp, len(list)*6)
	for i := range list {
		item := &list[i]
		ip := utils.IsNull(item.Ip)
		code := utils.IsNull(item.TollCode)
		for _, prefix := range []string{"stationip:", "station:"} {
			m[prefix+ip] = item
			m[prefix+code] = item
		}
		m[ip] = item
		m[code] = item
		m[utils.RepalaceSzdnTollName(item.TollName)] = item
	}
	return m, nil
}

// TollMap 对应 OdsSzdnTollServiceImpl.getRedisMap()（L88-107）：
// 同一行按 "收费站业务编码 toll_code" 与 "国网编码 state_code_merge" 注册两份 key。
//
// DIFF: Java 的 updateRedis() 把整个 List 写进 Constants.station_info，再在 getRedisMap 里现拼 Map；
// Go 侧同样“先缓存列表、再转 Map”，只是缓存值换成 JSON（切换版本前需 DEL station_info）。
func (r *DictRegistry) TollMap(ctx context.Context) (map[string]*model.OdsSzdnToll, error) {
	list, err := loadOrCache(ctx, r.cache, dictKeyStationInfo, r.tollRepo.ListAll)
	if err != nil {
		return nil, err
	}
	m := make(map[string]*model.OdsSzdnToll, len(list)*2)
	for i := range list {
		item := &list[i]
		m[utils.IsNull(item.TollCode)] = item
		m[utils.IsNull(item.StateCodeMerge)] = item
	}
	return m, nil
}

// GantryMap 对应 OdsSzdnGantryServiceImpl.getGantryRedis()（L74-83）+ 列表转 Map：
// key = gantry_code。
//
// 用途：/base/feerecords 列表在返回前要用「门架编号 → 门架名称/路段编码」回填两列，
// Java 侧每次请求都调 getGantryRedis()（Redis 未命中才回源），这里保持同样的读取路径。
func (r *DictRegistry) GantryMap(ctx context.Context) (map[string]*model.OdsSzdnGantry, error) {
	list, err := loadOrCache(ctx, r.cache, dictKeyGantryList, r.gantryRepo.ListAll)
	if err != nil {
		return nil, err
	}
	m := make(map[string]*model.OdsSzdnGantry, len(list))
	for i := range list {
		item := &list[i]
		m[utils.IsNull(item.GantryCode)] = item
	}
	return m, nil
}

// SectionMap 对应 OdsSzdnSectionServiceImpl.getSectionMap()：key = section_code
func (r *DictRegistry) SectionMap(ctx context.Context) (map[string]*model.OdsSzdnSection, error) {
	list, err := loadOrCache(ctx, r.cache, dictKeySection, r.sectionRepo.ListAll)
	if err != nil {
		return nil, err
	}
	m := make(map[string]*model.OdsSzdnSection, len(list))
	for i := range list {
		item := &list[i]
		m[utils.IsNull(item.SectionCode)] = item
	}
	return m, nil
}

// loadGantryIPs 对应 OdsSzdnGantryIpServiceImpl.updateRedis()：门架 IP 列表 + 按 gantry_code 关联门架主表。
func (r *DictRegistry) loadGantryIPs(ctx context.Context) ([]model.OdsSzdnGantryIp, error) {
	return loadOrCache(ctx, r.cache, dictKeyGantryIP, func(ctx context.Context) ([]model.OdsSzdnGantryIp, error) {
		list, err := r.gantryIPRepo.ListAll(ctx)
		if err != nil {
			return nil, err
		}
		gantries, err := r.gantryRepo.ListAll(ctx)
		if err != nil {
			return nil, err
		}
		byCode := make(map[string]*model.OdsSzdnGantry, len(gantries))
		for i := range gantries {
			byCode[utils.IsNull(gantries[i].GantryCode)] = &gantries[i]
		}
		for i := range list {
			if g, ok := byCode[utils.IsNull(list[i].GantryCode)]; ok {
				list[i].OdsSzdnGantry = g
			}
		}
		return list, nil
	})
}

// loadStationIPs 对应 OdsSzdnTollStationIpServiceImpl.updateRedis()：收费站 IP 列表 + 按 toll_code 关联收费站主表。
func (r *DictRegistry) loadStationIPs(ctx context.Context) ([]model.OdsSzdnTollStationIp, error) {
	return loadOrCache(ctx, r.cache, dictKeyStationIP, func(ctx context.Context) ([]model.OdsSzdnTollStationIp, error) {
		list, err := r.stationIPRepo.ListAll(ctx)
		if err != nil {
			return nil, err
		}
		tolls, err := r.tollRepo.ListAll(ctx)
		if err != nil {
			return nil, err
		}
		byCode := make(map[string]*model.OdsSzdnToll, len(tolls))
		for i := range tolls {
			byCode[utils.IsNull(tolls[i].TollCode)] = &tolls[i]
		}
		for i := range list {
			if t, ok := byCode[utils.IsNull(list[i].TollCode)]; ok {
				list[i].OdsSzdnToll = t
			}
		}
		return list, nil
	})
}

// loadOrCache 是 getRedisList() 的泛型版：先读 Redis（JSON），未命中则回源并写回。
//
// DIFF: Java 用 RedisCache.setCacheObject（JDK 序列化、无 TTL），Go 用 JSON + 无 TTL 的 SET,
// 语义一致（永不过期，靠 RefreshAll 手动重建）。
// 缓存读失败或反序列化失败都当作未命中回源 —— 缓存不该成为可用性的单点。
func loadOrCache[T any](ctx context.Context, c *cache.Client, key string,
	loader func(context.Context) ([]T, error)) ([]T, error) {

	if c != nil {
		if raw, ok, err := c.Get(ctx, key); err == nil && ok && raw != "" {
			var list []T
			if err := json.Unmarshal([]byte(raw), &list); err == nil {
				return list, nil
			}
			slog.Warn("[字典] 缓存反序列化失败，回源重建", "key", key)
		}
	}

	list, err := loader(ctx)
	if err != nil {
		return nil, err
	}
	if c != nil {
		if raw, err := json.Marshal(list); err == nil {
			if err := c.Set(ctx, key, string(raw)); err != nil {
				slog.Warn("[字典] 写缓存失败", "key", key, "err", err)
			}
		}
	}
	slog.Info("[字典] 缓存已重建", "key", key, "count", len(list))
	return list, nil
}
