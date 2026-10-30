# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.TrailAggregationService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/TrailAggregationService.java

轨迹聚合服务：轨迹补点（位置富集 + 缺失点检测）、质量评估、多轨迹合并。

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → `logging.getLogger(__name__)` + 普通类；
   `log.info("...{}", a, b)` 的 `{}` 占位符 → `%s`。
2) 4 个 `@Autowired` 成员 → 构造器可选参数；缺省分别 `new` 对应 `XxxServiceImpl()`
   （Spring 里 `IZdataLocationDictService` 等只有唯一实现 Bean）。
3) `public static class TrailQuality`（`@lombok.Data` 静态内部类）→ 模块级
   `@dataclass TrailQuality(JavaBean)`；文件末尾再挂到
   `TrailAggregationService.TrailQuality`，保持 Java 的
   `TrailAggregationService.TrailQuality` 访问路径不变。
4) `points.stream().map(...).collect(Collectors.toList())` → for 循环 + `append`。
   Stream 是惰性的，但这里末端 collect 立即求值，等价于普通循环。
5) 深拷贝 `JSON.parseObject(JSON.toJSONString(point), TrailBo.class)`
   → `JSON.parseObject(JSON.toJSONString(point), TrailBo)`：
   Java 传 `TrailBo.class`（Class 对象），Python 直接传类对象本身。
6) `new BigDecimal(String)` → `float(...)`：本工程的 `BigDecimal` 字段统一映射为
   Python `float`（TrailBo.lon/lat 已在 t05 声明为 `Optional[float]`）。
   注意 `new BigDecimal(null)` 在 Java 抛 NPE；`float(None)` 在 Python 抛 TypeError，
   两者同为“运行期异常”，语义一致。
7) `String.valueOf(Object)` 语义为 **null → "null"**，而 Python `str(None)` 是
   `"None"`，二者不同 → 统一走本文件的 `_javaStr()`。
8) `Comparator.comparing(TrailBo::getCaptureTime)` → `key=lambda p: p.capture_time`。
   `captureTime` 是 String，Java `String.compareTo` 与 Python 字符串比较对
   `yyyy-MM-dd HH:mm:ss` 这类 ASCII 串结果完全一致。
9) `fittedPoints.sort(...)` / `allPoints` 是 `List#sort`（**原地**排序）
   → Python `list.sort()`（同样原地）；**不能**换成 `sorted()`（返回新列表）。
10) `result.addAll(result.size() - 1, fillPoints)` → 切片赋值 `result[n-1:n-1] = fillPoints`，
    同样把补点插到“最后一个元素（即 curr）之前”。
11) `currTime.getTime() - prevTime.getTime()`（epoch 毫秒）→ `_epochMillis(dt)`；
    `timeDiff / 60000` 是 **long 除法** → Python 用 `//`（`/` 会得到 float）。
    `duration / (1000.0 * 60 * 60)` 是 double 除法 → Python 直接 `/`。
12) `trails.stream().filter(...).flatMap(...).sorted(...).collect(...)`
    → 双 for 循环 + `list.extend` + `list.sort`（flatMap 不复制元素，仅展平引用，
    与 Python `extend` 语义一致）。
13) `TrailBo` 的 `gantryIpBO` / `stationIpBO` 在原 Java 里**没有 `private` 修饰符**
    （包级私有字段），Lombok `@Data` 依旧为其生成 setter；`TrailBo.py` 已同步保留
    这两个字段（字段名 `gantry_ip_bo` / `station_ip_bo`），故这里的
    `point.setGantryIpBO(...)` 可正常调用（JavaBean 对缩写命名做忽略大小写解析）。
14) **原工程缺陷（忠实保留）**：`performTrailFitting` 第一行先
    `originalTrail.getTrailUuid()` 再判 `originalTrail == null`，
    入参为 null 时必然先 NPE；Python 同样先取属性（会 AttributeError）。
15) `tryFillBetween(...)` 的参数 `Map<String, OdsSzdnSection> sectionMap`
    在方法体内**从未使用**（Java 里也有 unused 警告），原样保留并标 `noqa`。
16) `buildNewTrailVersion` 中若 `original.getTracks()` 为 null，
    `JSON.parseObject("null", ZdataTrailTracks.class)` 返回 null，
    随后 `newTracks.setPointCount(...)` 必 NPE；Python 对应 AttributeError。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional

from com.alibaba.fastjson2.JSON import JSON
import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.domain.OdsSzdnGantryIp import OdsSzdnGantryIp
from com.ruoyi.base.domain.OdsSzdnSection import OdsSzdnSection
from com.ruoyi.base.domain.OdsSzdnToll import OdsSzdnToll
from com.ruoyi.base.domain.OdsSzdnTollStationIp import OdsSzdnTollStationIp
from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.TrailInfo import TrailInfo
from com.ruoyi.base.domain.ZdataLocationDict import ZdataLocationDict
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.service.IOdsSzdnGantryIpService import IOdsSzdnGantryIpService
from com.ruoyi.base.service.IOdsSzdnSectionService import IOdsSzdnSectionService
from com.ruoyi.base.service.IOdsSzdnTollStationIpService import IOdsSzdnTollStationIpService
from com.ruoyi.base.service.IZdataLocationDictService import IZdataLocationDictService
from com.ruoyi.base.service.impl.OdsSzdnGantryIpServiceImpl import OdsSzdnGantryIpServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnSectionServiceImpl import OdsSzdnSectionServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnTollStationIpServiceImpl import OdsSzdnTollStationIpServiceImpl
from com.ruoyi.base.service.impl.ZdataLocationDictServiceImpl import ZdataLocationDictServiceImpl
from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.utils.DateUtils import DateUtils

__all__ = ["TrailAggregationService", "TrailQuality"]

log = logging.getLogger(__name__)


def _javaStr(value: Any) -> str:
    """等价 `String.valueOf(Object)`：null → ``"null"``。

    【Java→Python】Python 的 `str(None)` 是 ``"None"``，与 Java 不同，必须显式转换。
    """
    return "null" if value is None else str(value)


def _epochMillis(value: Optional[datetime]) -> int:
    """等价 `Date#getTime()`（epoch 毫秒）。

    【Java→Python】naive `datetime.timestamp()` 按本地时区换算，
    与 Java `Date.getTime()`（UTC 基准毫秒）结果一致；值本身为 None 时
    Java 会 NPE，这里同样抛 AttributeError。
    """
    return int(value.timestamp() * 1000)


# 【Java→Python】`@lombok.Data public static class TrailQuality` → 模块级 dataclass。
# Java 里 `new TrailQuality()` 的字段默认值即 0 / null / 0.0，这里保持一致。
@dataclass
class TrailQuality(JavaBean):
    """轨迹质量评估结果（Java 静态内部类 TrailQuality 的等价物）。"""

    score: float = 0.0  # Java: private double score;
    level: Optional[str] = None  # Java: private String level;
    point_count: int = 0  # Java: private int pointCount;
    duration_hours: float = 0.0  # Java: private double durationHours;
    location_complete_rate: float = 0.0  # Java: private double locationCompleteRate;


class TrailAggregationService(object):
    """轨迹聚合服务（`@Service`）。"""

    def __init__(self,
                 locationDictService: Optional[IZdataLocationDictService] = None,
                 gantryIpService: Optional[IOdsSzdnGantryIpService] = None,
                 tollStationIpService: Optional[IOdsSzdnTollStationIpService] = None,
                 sectionService: Optional[IOdsSzdnSectionService] = None) -> None:
        # 【Java→Python】@Autowired 缺省依赖按 Spring 单例关系兜底
        self.locationDictService: IZdataLocationDictService = (
            locationDictService or ZdataLocationDictServiceImpl())
        self.gantryIpService: IOdsSzdnGantryIpService = (
            gantryIpService or OdsSzdnGantryIpServiceImpl())
        self.tollStationIpService: IOdsSzdnTollStationIpService = (
            tollStationIpService or OdsSzdnTollStationIpServiceImpl())
        self.sectionService: IOdsSzdnSectionService = (
            sectionService or OdsSzdnSectionServiceImpl())

    # ==================== 轨迹补点算法 ====================

    def performTrailFitting(self, originalTrail: Optional[TrailInfo]) -> Optional[TrailInfo]:
        """执行轨迹补点。

        思路：
        1. 分析现有轨迹点，识别缺失位置
        2. 根据位置字典和路段信息，尝试补全缺失点
        3. 生成补点后的新版本轨迹（保持UUID不变）

        目的：提升轨迹完整性，支撑逃费分析等业务场景

        :param originalTrail: 原始轨迹
        :return: 补点后的轨迹
        """
        # 【Java→Python】原文先取 UUID 再判 null（见文件头第 14 条），顺序原样保留
        log.info("[轨迹补点] 开始补点：trailUuid=%s", originalTrail.getTrailUuid())

        if originalTrail is None or originalTrail.getTrailList() is None:
            log.warning("[轨迹补点] 原始轨迹为空，跳过")
            return originalTrail

        originalPoints: List[TrailBo] = originalTrail.getTrailList()
        originalCount = len(originalPoints)

        # 步骤1：预处理轨迹点，补充位置信息
        enrichedPoints: List[TrailBo] = self.enrichLocationInfo(originalPoints)

        # 步骤2：检测并补全缺失点
        fittedPoints: List[TrailBo] = self.fillMissingPoints(enrichedPoints)

        # 步骤3：重新排序和格式化
        # 【Java→Python】List#sort 是原地排序 → list.sort（不是 sorted）
        # captureTime 为 String，两种语言的字典序对时间串等价
        fittedPoints.sort(key=lambda p: p.capture_time)

        # 步骤4：构建新版本轨迹
        newTrail: TrailInfo = self.buildNewTrailVersion(originalTrail, fittedPoints)

        addedCount = len(fittedPoints) - originalCount
        log.info("[轨迹补点] 补点完成：trailUuid=%s, 原始=%s, 补点后=%s, 新增=%s",
                 originalTrail.getTrailUuid(), originalCount, len(fittedPoints), addedCount)

        return newTrail

    def enrichLocationInfo(self, points: List[TrailBo]) -> List[TrailBo]:
        """富集位置信息。

        思路：根据设备IP查询字典数据，补全经纬度、路段等信息
        目的：让轨迹点携带完整的位置属性
        """
        # 预加载字典数据（无论 points 是否为空都会先查 4 次，与 Java Stream 前求值一致）
        locationDict: dict[str, ZdataLocationDict] = self.locationDictService.getRedisList()
        gantryIpMap: dict[str, OdsSzdnGantryIp] = self.gantryIpService.selectOdsSzdnGantryIpMap()
        stationIpMap: dict[str, OdsSzdnTollStationIp] = self.tollStationIpService.selectStationIpMap()
        sectionMap: dict[str, OdsSzdnSection] = self.sectionService.getSectionMap()

        # 【Java→Python】Stream.map(...).collect(toList()) → 普通 for 循环
        enrichedPoints: List[TrailBo] = []
        for point in points:
            # 深拷贝：Java 用 JSON 往返实现，Python 传类对象（非 Class 字面量）
            enrichedPoint: TrailBo = JSON.parseObject(JSON.toJSONString(point), TrailBo)

            # 尝试通过locationCode查询位置信息
            locationCode: Optional[str] = enrichedPoint.getLocationCode()
            if CommonUtil.isNotBlank(locationCode):
                # 查询位置字典
                location: Optional[ZdataLocationDict] = locationDict.get(locationCode)
                if location is not None:
                    self.enrichFromLocationDict(enrichedPoint, location)

                # 查询门架IP
                gantryIp: Optional[OdsSzdnGantryIp] = gantryIpMap.get(locationCode)
                if gantryIp is not None:
                    self.enrichFromGantryIp(enrichedPoint, gantryIp, sectionMap)

                # 查询收费站IP
                stationIp: Optional[OdsSzdnTollStationIp] = stationIpMap.get(locationCode)
                if stationIp is not None:
                    self.enrichFromStationIp(enrichedPoint, stationIp)

            enrichedPoints.append(enrichedPoint)
        return enrichedPoints

    def enrichFromLocationDict(self, point: TrailBo, location: ZdataLocationDict) -> None:
        """从位置字典富集信息。"""
        if point.getLon() is None:
            point.setLon(location.getLongitude())
        if point.getLat() is None:
            point.setLat(location.getLatitude())
        if CommonUtil.isBlank(point.getRoadCode()):
            point.setRoadCode(location.getRoadcode())
        if CommonUtil.isBlank(point.getSectionCode()):
            point.setSectionCode(location.getSectioncode())
        if CommonUtil.isBlank(point.getDevName()):
            point.setDevName(location.getName())
        point.setStandardCode(location.getStandardCode())

    def enrichFromGantryIp(self,
                           point: TrailBo,
                           gantryIp: OdsSzdnGantryIp,
                           sectionMap: dict[str, OdsSzdnSection]) -> None:  # noqa: ARG002
        """从门架IP信息富集。

        【Java→Python】`sectionMap` 在方法体内从未使用（原文如此），保留参数以对齐签名。
        """
        # 门架IP对象（字段无 private 修饰符，Lombok 仍生成 setter）
        point.setGantryIpBO(gantryIp)
        point.setDevCode(gantryIp.getGantryCode())
        point.setDevName(gantryIp.getGantryName())

        gantry: Optional[OdsSzdnGantry] = gantryIp.getOdsSzdnGantry()
        if gantry is not None:
            if point.getLon() is None:
                # Java: new BigDecimal(gantry.getLon()) —— lon 是 String
                point.setLon(float(gantry.getLon()))
            if point.getLat() is None:
                # Java: new BigDecimal(gantry.getLat())
                point.setLat(float(gantry.getLat()))
            if CommonUtil.isBlank(point.getRoadCode()):
                point.setRoadCode(gantry.getRoadCode())
            if CommonUtil.isBlank(point.getSectionCode()):
                point.setSectionCode(gantry.getSectionCode())
            if CommonUtil.isBlank(point.getPileno()):
                point.setPileno(gantry.getPileNo())
            # 【Java→Python】String.valueOf(null) == "null"，不能用 str()（得到 "None"）
            point.setDirection(_javaStr(gantry.getDirection()))
            point.setIsVirtual(_javaStr(gantry.getIsVirtual()))

        point.setLocationFlag("1")

    def enrichFromStationIp(self, point: TrailBo, stationIp: OdsSzdnTollStationIp) -> None:
        """从收费站IP信息富集。"""
        # 收费站IP对象（字段无 private 修饰符，Lombok 仍生成 setter）
        point.setStationIpBO(stationIp)
        point.setDevCode(stationIp.getTollCode())
        point.setDevName(stationIp.getTollName())

        toll: Optional[OdsSzdnToll] = stationIp.getOdsSzdnToll()
        if toll is not None:
            if point.getLon() is None and CommonUtil.isNotBlank(toll.getLongitude()):
                # Java: new java.math.BigDecimal(toll.getLongitude())
                point.setLon(float(toll.getLongitude()))
            if point.getLat() is None and CommonUtil.isNotBlank(toll.getLatitude()):
                point.setLat(float(toll.getLatitude()))
            if CommonUtil.isBlank(point.getRoadCode()):
                point.setRoadCode(toll.getRoadCode())
            if CommonUtil.isBlank(point.getSectionCode()):
                point.setSectionCode(toll.getSectionCode())

        point.setLocationFlag("1")

    def fillMissingPoints(self, points: List[TrailBo]) -> List[TrailBo]:
        """补全缺失点。

        思路：
        1. 分析相邻点之间的路段关系
        2. 如果两点在同一路段但距离较远，尝试补点
        3. 使用路段上的门架序列进行补全

        目的：让轨迹更完整，反映真实行驶路径
        """
        if len(points) < 2:
            return points

        result: List[TrailBo] = []
        result.append(points[0])

        for i in range(1, len(points)):
            prev: TrailBo = points[i - 1]
            curr: TrailBo = points[i]

            # 添加当前点
            result.append(curr)

            # 检查是否需要补点
            fillPoints: List[TrailBo] = self.tryFillBetween(prev, curr)
            if fillPoints is not None and len(fillPoints) > 0:
                # 【Java→Python】ArrayList.addAll(size-1, fillPoints)：插到最后一项（curr）之前
                insertAt = len(result) - 1
                result[insertAt:insertAt] = fillPoints

        return result

    def tryFillBetween(self, prev: TrailBo, curr: TrailBo) -> List[TrailBo]:
        """尝试在两点之间补点（当前仅检测、不真正补点，与原文 TODO 一致）。"""
        fillPoints: List[TrailBo] = []

        # 检查是否在同一路段
        if CommonUtil.isBlank(prev.getSectionCode()) or CommonUtil.isBlank(curr.getSectionCode()):
            return fillPoints

        # 【Java→Python】String#equals 内容比较 → Python 的 ==（内容比较，语义一致）
        if prev.getSectionCode() != curr.getSectionCode():
            return fillPoints

        # 计算时间差
        prevTime: Optional[datetime] = DateUtils.parseDate(prev.getCaptureTime())
        currTime: Optional[datetime] = DateUtils.parseDate(curr.getCaptureTime())
        timeDiff = int(abs(_epochMillis(currTime) - _epochMillis(prevTime)))

        # 时间差超过30分钟，考虑补点
        if timeDiff > 30 * 60 * 1000:
            # 【Java→Python】`timeDiff / 60000` 是 long 整除 → `//`（`/` 会得到 30.0）
            log.debug("[轨迹补点] 发现可能缺失点：prev=%s, curr=%s, timeDiff=%smin",
                      prev.getPointUuid(), curr.getPointUuid(), timeDiff // 60000)
            # TODO: 这里可以接入路段门架序列，生成虚拟补点

        return fillPoints

    def buildNewTrailVersion(self, original: TrailInfo, newPoints: List[TrailBo]) -> TrailInfo:
        """构建新版本轨迹。

        思路：保持UUID不变，更新轨迹数据，生成新版本
        目的：实现轨迹版本管理，支持数据追溯
        """
        newTrail = TrailInfo()

        # 复制原轨迹ID（保持不变，实现版本追溯）
        newTrail.setTrailUuid(original.getTrailUuid())

        # 复制并更新轨迹头信息（JSON 往返深拷贝；tracks 为 null 时返回 None，见文件头第 16 条）
        newTracks: ZdataTrailTracks = JSON.parseObject(
            JSON.toJSONString(original.getTracks()), ZdataTrailTracks)

        # 更新点数量（Java: (long) newPoints.size() → Python 无 long，int 即任意精度）
        newTracks.setPointCount(len(newPoints))

        # 更新起止时间
        if len(newPoints) > 0:
            newTracks.setEnterTime(DateUtils.parseDate(newPoints[0].getCaptureTime()))
            newTracks.setExitTime(DateUtils.parseDate(newPoints[len(newPoints) - 1].getCaptureTime()))

        # 标记为完整轨迹（如果点数足够）
        if len(newPoints) >= 5:
            newTracks.setType(1)

        # 更新完整JSON
        newTracks.setTrailPoints(JSON.toJSONString(newPoints))

        newTrail.setTracks(newTracks)
        newTrail.setTrailList(newPoints)

        return newTrail

    # ==================== 轨迹质量评估 ====================

    def assessTrailQuality(self, trail: TrailInfo) -> TrailQuality:
        """评估轨迹质量。

        思路：从多个维度评估轨迹完整性和可用性
        目的：为业务应用提供质量参考
        """
        quality = TrailQuality()

        points: List[TrailBo] = trail.getTrailList()
        if points is None or len(points) == 0:
            quality.setScore(0)
            quality.setLevel("EMPTY")
            return quality

        # 点数量评分
        pointCount = len(points)
        # 【Java→Python】`pointCount / 10.0` 在 Java 是 double 除法 → Python `/` 同样得 float
        pointScore = min(1.0, pointCount / 10.0) * 30

        # 时间跨度评分
        firstTime: Optional[datetime] = DateUtils.parseDate(points[0].getCaptureTime())
        lastTime: Optional[datetime] = DateUtils.parseDate(points[len(points) - 1].getCaptureTime())
        duration = _epochMillis(lastTime) - _epochMillis(firstTime)
        # Java: duration / (1000.0 * 60 * 60) —— double 除法，保留小数
        durationHours = duration / (1000.0 * 60 * 60)
        durationScore = min(1.0, durationHours / 2.0) * 30

        # 位置完整度评分
        # 【Java→Python】Stream.filter(...).count() → for + 计数器
        locationCompleteCount = 0
        for p in points:
            if p.getLon() is not None and p.getLat() is not None:
                locationCompleteCount += 1
        locationScore = (locationCompleteCount * 1.0 / pointCount) * 40

        # 总分
        totalScore = pointScore + durationScore + locationScore
        quality.setScore(totalScore)

        # 质量等级
        if totalScore >= 90:
            quality.setLevel("EXCELLENT")
        elif totalScore >= 70:
            quality.setLevel("GOOD")
        elif totalScore >= 50:
            quality.setLevel("FAIR")
        else:
            quality.setLevel("POOR")

        quality.setPointCount(pointCount)
        quality.setDurationHours(durationHours)
        quality.setLocationCompleteRate(locationCompleteCount * 1.0 / pointCount)

        log.debug("[轨迹质量] 评估完成：score=%s, level=%s, points=%s",
                  totalScore, quality.getLevel(), pointCount)

        return quality

    # ==================== 轨迹合并处理 ====================

    def mergeTrails(self, trails: Optional[List[TrailInfo]]) -> Optional[TrailInfo]:
        """合并多条轨迹。

        思路：当发现多条轨迹属于同一辆车的连续行程时，进行合并
        目的：还原完整的出行链路
        """
        if trails is None or len(trails) == 0:
            return None

        if len(trails) == 1:
            return trails[0]

        log.info("[轨迹合并] 开始合并：count=%s", len(trails))

        # 收集所有轨迹点
        # 【Java→Python】filter + flatMap + sorted + collect → 双循环展平后原地排序；
        # flatMap 只展平引用不做拷贝，这里 extend 同样不拷贝元素
        allPoints: List[TrailBo] = []
        for t in trails:
            if t.getTrailList() is not None:
                allPoints.extend(t.getTrailList())
        allPoints.sort(key=lambda p: p.getCaptureTime())

        # 创建合并后的轨迹
        mergedTrail = TrailInfo()
        mergedTracks = ZdataTrailTracks()

        # 使用第一条轨迹的UUID
        mergedTracks.setUuid(trails[0].getTracks().getUuid())
        mergedTracks.setPlateKey(trails[0].getTracks().getPlateKey())

        # 更新时间范围
        mergedTracks.setEnterTime(DateUtils.parseDate(allPoints[0].getCaptureTime()))
        mergedTracks.setExitTime(
            DateUtils.parseDate(allPoints[len(allPoints) - 1].getCaptureTime()))
        mergedTracks.setPointCount(len(allPoints))
        mergedTracks.setTrailPoints(JSON.toJSONString(allPoints))
        # Java: allPoints.size() >= 5 ? 1 : 0 → Python 三元表达式
        mergedTracks.setType(1 if len(allPoints) >= 5 else 0)

        mergedTrail.setTrailUuid(mergedTracks.getUuid())
        mergedTrail.setTracks(mergedTracks)
        mergedTrail.setTrailList(allPoints)

        log.info("[轨迹合并] 合并完成：originalCount=%s, mergedPoints=%s",
                 len(trails), len(allPoints))

        return mergedTrail


# 【Java→Python】保持 Java 中 `TrailAggregationService.TrailQuality` 的访问路径
TrailAggregationService.TrailQuality = TrailQuality
