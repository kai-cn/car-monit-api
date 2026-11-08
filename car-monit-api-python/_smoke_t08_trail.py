# -*- coding: utf-8 -*-
"""t08 单文件校验：TrailAggregationService（桩服务 + 真实 domain + 真实 JSON）。

覆盖：位置富集（字典/门架/收费站）、深拷贝隔离、缺字段兜底、补点检测阈值、
新版本构建、质量评分四档、多轨迹合并。
"""
import logging
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.alibaba.fastjson2.JSON import JSON  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnGantryIp import OdsSzdnGantryIp  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnToll import OdsSzdnToll  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnTollStationIp import OdsSzdnTollStationIp  # noqa: E402
from com.ruoyi.base.domain.TrailBo import TrailBo  # noqa: E402
from com.ruoyi.base.domain.TrailInfo import TrailInfo  # noqa: E402
from com.ruoyi.base.domain.ZdataLocationDict import ZdataLocationDict  # noqa: E402
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks  # noqa: E402
from com.ruoyi.base.service.impl.TrailAggregationService import (  # noqa: E402
    TrailAggregationService,
    TrailQuality,
)

failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


def check_true(label, actual):
    check(label, bool(actual), True)


records = []


class _Capture(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


app_logger = logging.getLogger("com.ruoyi.base.service.impl.TrailAggregationService")
app_logger.setLevel(logging.DEBUG)
app_logger.addHandler(_Capture())


def logged(fragment):
    return any(fragment in message for message in records)


# ---------------------------------------------------------------- 桩服务
def location(code, lon, lat, road, section, name, standard):
    row = ZdataLocationDict()
    # getRedisList() 的 key 取的是 rawCode（对应轨迹表/实时轨迹 code）
    row.setRawCode(code)
    row.setLongitude(lon)
    row.setLatitude(lat)
    row.setRoadcode(road)
    row.setSectioncode(section)
    row.setName(name)
    row.setStandardCode(standard)
    return row


def gantry_ip(location_code, gantry_code, gantry_name, gantry=None):
    row = OdsSzdnGantryIp()
    row.setIp(location_code)
    row.setGantryCode(gantry_code)
    row.setGantryName(gantry_name)
    row.setOdsSzdnGantry(gantry)
    return row


def toll_ip(location_code, toll_code, toll_name, toll=None):
    row = OdsSzdnTollStationIp()
    row.setIp(location_code)
    row.setTollCode(toll_code)
    row.setTollName(toll_name)
    row.setOdsSzdnToll(toll)
    return row


class _StubLocationDictService(object):
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def getRedisList(self):
        self.calls += 1
        return {row.getRawCode(): row for row in self.rows}


class _StubGantryIpService(object):
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def selectOdsSzdnGantryIpMap(self):
        self.calls += 1
        return {row.getIp(): row for row in self.rows}


class _StubStationIpService(object):
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def selectStationIpMap(self):
        self.calls += 1
        return {row.getIp(): row for row in self.rows}


class _StubSectionService(object):
    def __init__(self):
        self.calls = 0

    def getSectionMap(self):
        self.calls += 1
        return {}


def point(uuid, capture_time, location_code=None, **kwargs):
    row = TrailBo()
    row.setPointUuid(uuid)
    row.setCaptureTime(capture_time)
    if location_code is not None:
        row.setLocationCode(location_code)
    for key, value in kwargs.items():
        # camelCase 属性名不是 dataclass 字段名，必须走 JavaBean 的 setter（roadCode → road_code）
        setter = getattr(row, "set" + key[:1].upper() + key[1:], None)
        if setter is not None:
            setter(value)
        else:
            setattr(row, key, value)
    return row


gantry = OdsSzdnGantry()
gantry.setLon("113.123456")
gantry.setLat("23.654321")
gantry.setRoadCode("G001")
gantry.setSectionCode("S001")
gantry.setPileNo("K12+300")
gantry.setDirection(None)          # String.valueOf(null) → "null"
gantry.setIsVirtual("0")

toll = OdsSzdnToll()
toll.setLongitude("114.000001")
toll.setLatitude("")               # 空串：isNotBlank 为假 → 不填 lat
toll.setRoadCode("G002")
toll.setSectionCode("S002")

loc_service = _StubLocationDictService([
    location("10.0.0.1", 113.0, 23.0, "G999", "S999", "字典设备", "STD-1"),
])
gantry_service = _StubGantryIpService([
    gantry_ip("10.0.0.2", "GC-1", "门架一", gantry),
])
station_service = _StubStationIpService([
    toll_ip("10.0.0.3", "TC-1", "收费站一", toll),
])
section_service = _StubSectionService()
service = TrailAggregationService(locationDictService=loc_service,
                                  gantryIpService=gantry_service,
                                  tollStationIpService=station_service,
                                  sectionService=section_service)

# ---------------------------------------------------------------- 1) 位置富集
p_dict = point("P-DICT", "2026-01-01 10:00:00", "10.0.0.1")
p_gantry = point("P-GANTRY", "2026-01-01 10:10:00", "10.0.0.2")
p_station = point("P-STATION", "2026-01-01 10:20:00", "10.0.0.3")
p_none = point("P-NONE", "2026-01-01 10:30:00", "10.0.0.9")
p_blank = point("P-BLANK", "2026-01-01 10:40:00", "")

enriched = service.enrichLocationInfo([p_dict, p_gantry, p_station, p_none, p_blank])
check("preload locationDict", loc_service.calls, 1)
check("preload gantry", gantry_service.calls, 1)
check("preload station", station_service.calls, 1)
check("preload section", section_service.calls, 1)
check("enriched size", len(enriched), 5)

# 深拷贝：原对象不被污染
check("deep copy keeps original lon", p_dict.getLon(), None)
check_true("deep copy new instance", enriched[0] is not p_dict)

# 位置字典
d = enriched[0]
check("dict lon", d.getLon(), 113.0)
check("dict lat", d.getLat(), 23.0)
check("dict roadCode", d.getRoadCode(), "G999")
check("dict sectionCode", d.getSectionCode(), "S999")
check("dict devName", d.getDevName(), "字典设备")
check("dict standardCode", d.getStandardCode(), "STD-1")
check("dict locationFlag", d.getLocationFlag(), None)  # 字典分支不设 flag

# 门架
g = enriched[1]
check("gantry devCode", g.getDevCode(), "GC-1")
check("gantry devName", g.getDevName(), "门架一")
check("gantry lon decimal", g.getLon(), Decimal("113.123456"))
check("gantry lat decimal", g.getLat(), Decimal("23.654321"))
check("gantry roadCode", g.getRoadCode(), "G001")
check("gantry sectionCode", g.getSectionCode(), "S001")
check("gantry pileno", g.getPileno(), "K12+300")
check("gantry direction null", g.getDirection(), "null")
check("gantry isVirtual", g.getIsVirtual(), "0")
check("gantry locationFlag", g.getLocationFlag(), "1")
check_true("gantry BO field", g.getGantryIpBO() is not None)

# 收费站
s = enriched[2]
check("station devCode", s.getDevCode(), "TC-1")
check("station devName", s.getDevName(), "收费站一")
check("station lon decimal", s.getLon(), Decimal("114.000001"))
check("station lat blank skipped", s.getLat(), None)
check("station roadCode", s.getRoadCode(), "G002")
check("station sectionCode", s.getSectionCode(), "S002")
check("station locationFlag", s.getLocationFlag(), "1")
check_true("station BO field", s.getStationIpBO() is not None)

# 未命中
check("unknown code untouched", enriched[3].getLon(), None)
check("blank code untouched", enriched[4].getDevCode(), None)

# 已有值不被覆盖
p_keep = point("P-KEEP", "2026-01-01 11:00:00", "10.0.0.1", lon=1.5, lat=2.5,
               roadCode="R0", sectionCode="S0", devName="已有设备")
kept = service.enrichLocationInfo([p_keep])[0]
check("keep lon", kept.getLon(), 1.5)
check("keep lat", kept.getLat(), 2.5)
check("keep roadCode", kept.getRoadCode(), "R0")
check("keep sectionCode", kept.getSectionCode(), "S0")
check("keep devName", kept.getDevName(), "已有设备")

# ---------------------------------------------------------------- 2) 补点检测
# 空 sectionCode → 直接返回空
check("fill between blank section", service.tryFillBetween(
    point("A", "2026-01-01 10:00:00", sectionCode=""), point("B", "2026-01-01 10:40:00", sectionCode="S1")), [])
# 不同路段 → 空
check("fill between diff section", service.tryFillBetween(
    point("A", "2026-01-01 10:00:00", sectionCode="S1"),
    point("B", "2026-01-01 10:40:00", sectionCode="S2")), [])
# 同路段 45 分钟 → 仅打 debug 日志，返回空（TODO 未实现）
check("fill between same section", service.tryFillBetween(
    point("A", "2026-01-01 10:00:00", sectionCode="S1"),
    point("B", "2026-01-01 10:45:00", sectionCode="S1")), [])
check_true("fill between debug log", logged("timeDiff=45min"))
# 不足 30 分钟 → 不打印
records.clear()
check("fill between 10min", service.tryFillBetween(
    point("C", "2026-01-01 10:00:00", sectionCode="S1"),
    point("D", "2026-01-01 10:10:00", sectionCode="S1")), [])
check("no debug under 30min", logged("timeDiff=10min"), False)

# 少于 2 个点：返回入参本身（Java 同一引用）
single = [point("ONLY", "2026-01-01 10:00:00")]
check_true("fill single returns same list", service.fillMissingPoints(single) is single)

# 多点：当前实现无补点，元素顺序不变
multi = [point("M1", "2026-01-01 10:00:00", sectionCode="S1"),
         point("M2", "2026-01-01 10:45:00", sectionCode="S1"),
         point("M3", "2026-01-01 11:00:00", sectionCode="S2")]
filled = service.fillMissingPoints(multi)
check("fill keeps order", [item.getPointUuid() for item in filled], ["M1", "M2", "M3"])
check_true("fill returns new list", filled is not multi)

# ---------------------------------------------------------------- 3) 补点主流程
tracks = ZdataTrailTracks()
tracks.setUuid("T-UUID-1")
tracks.setPointCount(3)
tracks.setType(0)
trail = TrailInfo()
trail.setTrailUuid("T-UUID-1")
trail.setTracks(tracks)
trail.setTrailList([
    point("L3", "2026-01-01 12:00:00", "10.0.0.1"),
    point("L1", "2026-01-01 10:00:00", "10.0.0.2"),
    point("L5", "2026-01-01 14:00:00", "10.0.0.3"),
    point("L2", "2026-01-01 11:00:00", "10.0.0.4"),
    point("L4", "2026-01-01 13:00:00", "10.0.0.5"),
])
fitted = service.performTrailFitting(trail)
check("fitting keeps uuid", fitted.getTrailUuid(), "T-UUID-1")
check("fitting sorted", [p.getPointUuid() for p in fitted.getTrailList()],
      ["L1", "L2", "L3", "L4", "L5"])
new_tracks = fitted.getTracks()
check("fitting pointCount", new_tracks.getPointCount(), 5)
check("fitting enterTime", new_tracks.getEnterTime(), datetime(2026, 1, 1, 10, 0, 0))
check("fitting exitTime", new_tracks.getExitTime(), datetime(2026, 1, 1, 14, 0, 0))
check("fitting type complete", new_tracks.getType(), 1)
check("fitting tracks uuid", new_tracks.getUuid(), "T-UUID-1")
check_true("fitting trailPoints json", '"pointUuid":"L1"' in new_tracks.getTrailPoints())
check_true("fitting log", logged("新增=0"))

# 空 trackList（非 null）→ 点数 0，type 保持原值
empty_track = ZdataTrailTracks()
empty_track.setUuid("T-EMPTY")
empty_track.setType(0)
empty_trail = TrailInfo()
empty_trail.setTrailUuid("T-EMPTY")
empty_trail.setTracks(empty_track)
empty_trail.setTrailList([])
empty_fitted = service.performTrailFitting(empty_trail)
check("empty fitting pointCount", empty_fitted.getTracks().getPointCount(), 0)
check("empty fitting type unchanged", empty_fitted.getTracks().getType(), 0)
check("empty fitting enterTime", empty_fitted.getTracks().getEnterTime(), None)

# trailList 为 null → 原样返回（warn 分支）
null_list_trail = TrailInfo()
null_list_trail.setTrailUuid("T-NULL")
check_true("null trailList returns input",
           service.performTrailFitting(null_list_trail) is null_list_trail)
check_true("null trailList warning", logged("原始轨迹为空，跳过"))

# 原工程缺陷：入参为 null 时先取 UUID → AttributeError（等价 Java NPE）
npe = None
try:
    service.performTrailFitting(None)
except AttributeError:
    npe = "AttributeError"
check("null trail raises NPE-like", npe, "AttributeError")

# ---------------------------------------------------------------- 4) 质量评估
empty_quality = service.assessTrailQuality(TrailInfo())
check("quality empty score", empty_quality.getScore(), 0)
check("quality empty level", empty_quality.getLevel(), "EMPTY")


def quality_trail(count, start, step_minutes, with_location):
    rows = []
    moment = start
    for index in range(count):
        kwargs = {}
        if with_location:
            kwargs["lon"] = 113.0
            kwargs["lat"] = 23.0
        rows.append(point("Q%d" % index, moment.strftime("%Y-%m-%d %H:%M:%S"), **kwargs))
        moment = moment + timedelta(minutes=step_minutes)
    result = TrailInfo()
    result.setTrailUuid("Q")
    result.setTrailList(rows)
    return result


# 10 点 / 跨度 2h（10 点 × 12min = 108min < 2h）→ 30 + 27 + 40 = 97 → EXCELLENT
excellent = service.assessTrailQuality(
    quality_trail(10, datetime(2026, 2, 1, 8, 0, 0), 13, True))
check("quality excellent level", excellent.getLevel(), "EXCELLENT")
check("quality excellent points", excellent.getPointCount(), 10)
check("quality excellent rate", excellent.getLocationCompleteRate(), 1.0)
check_true("quality excellent score", excellent.getScore() >= 90)

# 6 点 / 跨度 2h（24min × 5）/ 全位置 → 18 + 30 + 40 = 88 → GOOD
good = service.assessTrailQuality(
    quality_trail(6, datetime(2026, 2, 1, 8, 0, 0), 24, True))
check("quality good level", good.getLevel(), "GOOD")
check_true("quality good score range", 70 <= good.getScore() < 90)

# 5 点 / 跨度 10min / 全位置 → 15 + 2.5 + 40 = 57.5 → FAIR
fair = service.assessTrailQuality(
    quality_trail(5, datetime(2026, 2, 1, 8, 0, 0), 2, True))
check("quality fair level", fair.getLevel(), "FAIR")
check_true("quality fair score range", 50 <= fair.getScore() < 70)

# 2 点 / 跨度 1min / 无位置 → 6 + 0.25 + 0 = 6.25 → POOR
poor = service.assessTrailQuality(
    quality_trail(2, datetime(2026, 2, 1, 8, 0, 0), 1, False))
check("quality poor level", poor.getLevel(), "POOR")
check("quality poor rate", poor.getLocationCompleteRate(), 0.0)
check("quality poor hours", round(poor.getDurationHours(), 6), round(1 / 60.0, 6))
check_true("quality log", logged("[轨迹质量] 评估完成"))

# ---------------------------------------------------------------- 5) 轨迹合并
check("merge null", service.mergeTrails(None), None)
check("merge empty", service.mergeTrails([]), None)

only = TrailInfo()
only.setTrailUuid("ONLY")
check_true("merge single returns same", service.mergeTrails([only]) is only)


def trail_of(uuid, rows):
    item = TrailInfo()
    item.setTrailUuid(uuid)
    item_tracks = ZdataTrailTracks()
    item_tracks.setUuid(uuid)
    item_tracks.setPlateKey("赣A" + uuid)
    item.setTracks(item_tracks)
    item.setTrailList(rows)
    return item


first = trail_of("T1", [point("A1", "2026-03-01 09:00:00"),
                        point("A2", "2026-03-01 11:00:00")])
second = trail_of("T2", [point("B1", "2026-03-01 10:00:00"),
                         point("B2", "2026-03-01 12:00:00"),
                         point("B3", "2026-03-01 13:00:00")])
no_list = TrailInfo()
no_list.setTrailUuid("T3")  # trailList 为 null → 被 filter 掉

merged = service.mergeTrails([first, second, no_list])
check("merge sorted", [p.getPointUuid() for p in merged.getTrailList()],
      ["A1", "B1", "A2", "B2", "B3"])
check("merge trailUuid from first tracks", merged.getTrailUuid(), "T1")
check("merge tracks uuid", merged.getTracks().getUuid(), "T1")
check("merge tracks plateKey", merged.getTracks().getPlateKey(), "赣AT1")
check("merge pointCount", merged.getTracks().getPointCount(), 5)
check("merge type", merged.getTracks().getType(), 1)
check("merge enterTime", merged.getTracks().getEnterTime(), datetime(2026, 3, 1, 9, 0, 0))
check("merge exitTime", merged.getTracks().getExitTime(), datetime(2026, 3, 1, 13, 0, 0))
check_true("merge log", logged("originalCount=3, mergedPoints=5"))

# 少于 5 点 → type 0
small = service.mergeTrails([trail_of("S1", [point("S1A", "2026-03-02 09:00:00")]),
                             trail_of("S2", [point("S2A", "2026-03-02 10:00:00")])])
check("merge small type", small.getTracks().getType(), 0)
check("merge small count", small.getTracks().getPointCount(), 2)

# ---------------------------------------------------------------- 6) 静态内部类别名
check_true("TrailQuality alias", TrailAggregationService.TrailQuality is TrailQuality)
check("TrailQuality default level", TrailAggregationService.TrailQuality().getLevel(), None)

print("checks:", total[0] - len(failures), "/", total[0])
for failure in failures:
    print("FAIL", failure)
