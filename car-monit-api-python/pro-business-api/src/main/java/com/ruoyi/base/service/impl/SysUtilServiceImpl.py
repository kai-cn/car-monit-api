# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.SysUtilServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java
（2692 行，本工程最大的服务实现）

可疑车辆/轨迹相关的核心工具服务：解析轨迹点 JSON、补全设备经纬度、按门架抓拍与
门架交易流水比对判定"全程/部分屏蔽"逃费场景，并把结果写入 Redis。

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → 模块级 `logging.getLogger(__name__)` + 普通类。
2) 21 个注入点（20 个 `@Autowired` + 2 个 `@Resource`，其中 redisConfig 同时是 `@Resource`）
   → 构造器可选参数；缺省按 Spring 单例关系 `new XxxServiceImpl()`。
3) `@Value("${isLocalhost}")`（无默认值）→ `Environment().value("${isLocalhost}", str)`。
4) `CommonUtil.isNull(x)` 的语义是 **null → ""，否则 `str(x).strip()`**（不是返回 "null"），
   直接用同名函数，不要替换成 `str()`。
5) `String.split(regex)` 是**正则且丢弃尾部空串**（`"_".split("_")` 在 Java 里长度为 0，
   `arr[0]` 抛 ArrayIndexOutOfBoundsException）→ 统一用 `StringUtils._java_split(sep, text)`；
   Python 的 `str.split` 会保留空串，直接替换会改变行为。
6) `switch (String)`（Java 7+ 语法）→ `if/elif`。注意 Java 的 `switch(null)` 抛 NPE，
   但本文件的 stateType 都先过 `CommonUtil.isNull(...)`，不会是 None。
7) `BigDecimal` → `java.math.BigDecimal` 替身（内部为 decimal.Decimal）：
   `compareTo` 忽略 scale，`divide(divisor, scale, ROUND_HALF_UP)` 精确到指定小数位；
   `BigDecimal.ROUND_HALF_UP` 保留为 **int 常量 4**（Java 8 的旧常量），替身同时接受 int 与枚举名。
8) **t05 已把实体的 BigDecimal 字段统一映射为 float**（TrailBo.lon/lat、
   ZdataTrailTracks.startLonDec 等）。本文件在赋值处用 `_bdFloat()`：先按 BigDecimal
   计算/校验，再落成 float。Java 侧保留 BigDecimal 精度，Python 侧是 double 近似，
   属于既定映射差异（比较与格式化结果可能有末位差异）。
9) `Map<ZdataTrailTracks, List<TrailBo>>` 的 key 在 Java 里靠 Lombok `@Data` 的
   `hashCode/equals`（字段比较）；Python dataclass 默认 `__hash__ = None` **不可哈希**，
   不能直接当 dict key。本文件该方法只返回空 HashMap（原文如此），如需真做 key
   必须改用 uuid/plateKey 之类的字符串键。
10) `redisCache.getCacheObject(key)` 在替身里返回 **deepcopy**（模拟 Redis 序列化往返）。
    原文 `List oldList = get(...); List keyList = oldList; keyList.add(x); set(key, keyList);`
    在 Java 里是"取引用→改→写回"，Python 里同样要"取出→修改→写回"，
    **不能只改列表不复写**，否则 Redis 里的值不会更新（本文件的 `setCacheObject` 已写回）。
11) `stream().sorted(Comparator.comparing(X::getYyy))` → `list.sort(key=...)`；
    Java 的 `sorted` 返回新列表，Python 的 `sort` 原地排序（本文件排序结果会覆盖原变量，
    与原文"重新赋值"一致）。
12) `Collection<String> keys = redisCache.keys(pattern)` 可能为 null → 替身返回 `set`（空集表示无），
    判断统一用 `keys is not None and len(keys) > 0`，与原文保持一致（不做 None 合并）。
13) `List#subList(from, to)` 返回**视图**（原列表结构变化会失效）→ Python 切片返回新列表；
    本文件只用于批量查询的入参，语义等价。
14) `new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss")` → `strptime("%Y-%m-%dT%H:%M:%S")`；
    `format.parse` 的 `ParseException` → `ValueError`。原文多处 `catch (Exception e)` 后
    只打日志继续，Python 同样用 `except Exception`。
15) `e.printStackTrace()` → `traceback.print_exc()`（保持控制台堆栈输出）；
    日志里 `e.toString()` → `str(e)`。
16) `JSON.parseArray(text)` → `JSON.parseArray(text)`（替身返回 JSONArray=dict 列表）；
    `JSON.parseArray(text, TrailBo.class)` → 带实体转换的重载（字段名 camelCase→snake_case）。
17) `Integer.parseInt(str)` → `int(str)`（空串/非数字抛 ValueError，对应 NumberFormatException）。
18) `for (int i = startNum; i <= endNum; i++)` → `range(startNum, endNum + 1)`（含右端点）。
19) `System.currentTimeMillis()` → `java.lang.System` 替身（time.time()*1000 取整）。
20) `@Resource HttpSysUtilApiService`（Forest 动态代理）→ `forest.HttpSysUtilApiService`
    的默认离线实现（不发真实 HTTP，返回 code=200）。
21) 【忠实保留的原工程缺陷】
    a. `String lat = trailBo.getLon();` —— 纬度取的是**经度**字段（changeData 中），
       导致"经度为 null 才补纬度"的判断错位；
    b. `getTrailBoList` 中只有 `captureTime` 含 `"T"` 时才设置 captureTime，
       普通 `yyyy-MM-dd HH:mm:ss` 的时间会被**丢弃**；
    c. `syncSuspiciousCarQutazNew` 的 `queryStartDate` 会在循环内被轨迹 enterTime
       逐步提前（跨页累积），并不重置为当天 0 点；
    d. `saveRedis`、`syncSuspiciousCarQutaz`/`New` 里大量 `gantryMao`/`locationMap`/
       `sectionMap` 计算后未使用（原样保留，未加 noqa 的地方在注释里标注）。
    e. `getByTrailBo` 中 FeeRecord/FeeStationEnter/FeeStationExit 三支的
       `xxUUids += pointUuid + ","` 被整行注释 → 这 3 张表永远不查询、3 个分支永远不可达；
    f. `separateUnfiitingList` 的"部分屏蔽"（escapedTfcj="2"）**恒不可达**：
       `costBite = conutFeeRecord / sussFeeRecord`，而 `sussFeeRecord <= conutFeeRecord`，
       故 costBite >= 1 而 bite 硬编码 0.5，`bite.compareTo(costBite) >= 0` 永远为 false；
    g. `separateSnapshotFlowTimeList` 的 `thirtyMinutesInMillis = 60 * 60 * 1000` 实际是
       **1 小时**（变量名与注释写"30 分钟"）；
    h. `syncSnapshotFlow` 的结束日志文案也写成"开始查询"，且 `syncFeeRecords` 同样如此，
       均为原文不动。
22) `syncSuspiciousCar` 返回 `new HashMap<>()`（原文空实现），Python 返回 `{}`。
23) `@Override` 注解在 Python 中无对应物（接口一致性靠 ABC 的 abstractmethod 保证）；
    文件末尾的 `_assert_interface_implemented()` 在导入时对比 `__abstractmethods__`，
    一旦漏实现立即抛 ImportError（Java 靠编译器，Python 靠这一步）。
24) `trailBo.setDirection(odsSzdnGantry.getDirection())` 等 setter 由 JavaBean 动态提供，
    `@Accessors(chain = true)` 的链式返回 self，但原文都用语句调用，不使用返回值。
25) **JSONArray 迭代语义**：Java `for (Object o : array)` 得到的是 JSONObject/JSONArray；
    Python 替身的 `JSONArray` 继承 list，已重写 `__iter__` 做 `_wrap`，否则
    `o.getString(...)` 会 AttributeError（本文件 `changeData`/`getTrailBoList` 均依赖此行为）。
26) Java 用 `list` 作为局部变量名的地方（`syncSnapshotFlow`/`syncFeeRecords`/
    `carTrackQueryNew`），Python 改名为 `list_`，避免遮蔽内置 `list` 导致后续
    `list(...)` 调用报 TypeError。
27) `List#subList(from, to)` → Python 切片（新列表而非视图）；`Math.min` → 内置 `min`；
    `Math.abs` → 内置 `abs`；`Comparator.comparing(X::getYyy)` → `list.sort(key=...)`。
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime, timedelta
from typing import Any, List, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.alibaba.fastjson2.JSON import JSON
from com.alibaba.fastjson2.JSONArray import JSONArray
from com.alibaba.fastjson2.JSONObject import JSONObject
from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.CarVO import CarVO
from com.ruoyi.base.domain.OdsCxztFwqclls import OdsCxztFwqclls
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01 import OdsLwzxsfsjFeeStationEnter01
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01 import OdsLwzxsfsjFeeStationExit01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode import (
    OdsRtSzdnSnapshotFlowProvcaptureAddcode,
)
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode import (
    OdsRtSzdnSnapshotFlowStationcaptureAddcode,
)
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.domain.OdsSzdnGantryIp import OdsSzdnGantryIp
from com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure import (
    OdsSzdnProvinceBorderVehicleWeightNewstructure,
)
from com.ruoyi.base.domain.OdsSzdnSection import OdsSzdnSection
from com.ruoyi.base.domain.OdsSzdnToll import OdsSzdnToll
from com.ruoyi.base.domain.OdsSzdnTollStationIp import OdsSzdnTollStationIp
from com.ruoyi.base.domain.SuspiciousCarVO import SuspiciousCarVO
from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.TrailInfo import TrailInfo
from com.ruoyi.base.domain.TrailTracksVo import TrailTracksVo
from com.ruoyi.base.domain.ZdataLocationDict import ZdataLocationDict
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.forest.HttpSysUtilApiService import (
    ForestHttpSysUtilApiService,
    HttpSysUtilApiService,
)
from com.ruoyi.base.service.IOdsCxztFwqcllsService import IOdsCxztFwqcllsService
from com.ruoyi.base.service.IDwdLcztFwqjcxxService import IDwdLcztFwqjcxxService
from com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service import IOdsLwzxsfsjFeeRecords01Service
from com.ruoyi.base.service.IOdsLwzxsfsjFeeStationEnter01Service import (
    IOdsLwzxsfsjFeeStationEnter01Service,
)
from com.ruoyi.base.service.IOdsLwzxsfsjFeeStationExit01Service import (
    IOdsLwzxsfsjFeeStationExit01Service,
)
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService import (
    IOdsRtSzdnSnapshotFlowAddcodeService,
)
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService import (
    IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService,
)
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService import (
    IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService,
)
from com.ruoyi.base.service.IOdsSzdnGantryIpService import IOdsSzdnGantryIpService
from com.ruoyi.base.service.IOdsSzdnGantryService import IOdsSzdnGantryService
from com.ruoyi.base.service.IOdsSzdnProvinceBorderVehicleWeightNewstructureService import (
    IOdsSzdnProvinceBorderVehicleWeightNewstructureService,
)
from com.ruoyi.base.service.IOdsSzdnSectionService import IOdsSzdnSectionService
from com.ruoyi.base.service.IOdsSzdnTollService import IOdsSzdnTollService
from com.ruoyi.base.service.IOdsSzdnTollStationIpService import IOdsSzdnTollStationIpService
from com.ruoyi.base.service.ISysUtilService import ISysUtilService
from com.ruoyi.base.service.IZdataLocationDictService import IZdataLocationDictService
from com.ruoyi.base.service.IZdataTrailTracksService import IZdataTrailTracksService
from com.ruoyi.base.service.impl.DwdLcztFwqjcxxServiceImpl import DwdLcztFwqjcxxServiceImpl
from com.ruoyi.base.service.impl.OdsCxztFwqcllsServiceImpl import OdsCxztFwqcllsServiceImpl
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeRecords01ServiceImpl import (
    OdsLwzxsfsjFeeRecords01ServiceImpl,
)
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeStationEnter01ServiceImpl import (
    OdsLwzxsfsjFeeStationEnter01ServiceImpl,
)
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeStationExit01ServiceImpl import (
    OdsLwzxsfsjFeeStationExit01ServiceImpl,
)
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowAddcodeServiceImpl import (
    OdsRtSzdnSnapshotFlowAddcodeServiceImpl,
)
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl import (
    OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl,
)
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl import (
    OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl,
)
from com.ruoyi.base.service.impl.OdsSzdnGantryIpServiceImpl import OdsSzdnGantryIpServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnGantryServiceImpl import OdsSzdnGantryServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl import (
    OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl,
)
from com.ruoyi.base.service.impl.OdsSzdnSectionServiceImpl import OdsSzdnSectionServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnTollServiceImpl import OdsSzdnTollServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnTollStationIpServiceImpl import (
    OdsSzdnTollStationIpServiceImpl,
)
from com.ruoyi.base.service.impl.ZdataLocationDictServiceImpl import ZdataLocationDictServiceImpl
from com.ruoyi.base.service.impl.ZdataTrailTracksServiceImpl import ZdataTrailTracksServiceImpl
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.constant.HttpStatus import HttpStatus
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.redis.RedisCache import RedisCache
from com.ruoyi.common.core.redis.RedisConfig import RedisConfig
from com.ruoyi.common.core.redis.RedisSourceFactory import JedisCluster, RedisSourceFactory
from com.ruoyi.common.utils.SecuritySHA1Utils import SecuritySHA1Utils
from com.ruoyi.common.utils.StringUtils import StringUtils, _java_split
from java.lang.System import System
from java.math.BigDecimal import BigDecimal
from org.springframework.core.env.Environment import Environment

__all__ = ["SysUtilServiceImpl"]

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ 辅助函数
def _bd(value: Any) -> BigDecimal:
    """等价 `new BigDecimal(value)`（String/int 精确，float 走 valueOf 语义）。"""
    return BigDecimal(value)


def _bdFloat(value: Any) -> float:
    """BigDecimal 结果落到 float 字段（t05 的统一映射：BigDecimal → float）。

    【Java→Python】Java 的实体字段是 BigDecimal，赋值不丢精度；
    Python 侧实体字段已声明为 float，这里显式转换，避免把 BigDecimal 对象塞进 float 字段
    导致后续 JSON 序列化出现非预期结构。
    """
    return float(BigDecimal(value))


def _javaDateToString(value: Optional[datetime]) -> str:
    """等价 `String.valueOf(Date)` → `Date#toString()`（EEE MMM dd HH:mm:ss zzz yyyy）。"""
    if value is None:
        return "null"
    return value.strftime("%a %b %d %H:%M:%S %Z %Y")


def _epochMillis(value: Optional[datetime]) -> int:
    """等价 `Date#getTime()`（epoch 毫秒）。"""
    return int(value.timestamp() * 1000)


def _parseDateTime(text: str) -> datetime:
    """等价 `new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").parse(text)`。"""
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def _formatDateTime(value: datetime) -> str:
    """等价 `new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(value)`。"""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _javaStr(value: Any) -> str:
    """等价 `String.valueOf(Object)`：null → "null"，否则 toString()。"""
    return "null" if value is None else str(value)


class SysUtilServiceImpl(ISysUtilService):
    """`SysUtilServiceImpl implements ISysUtilService`。

    【Java→Python】Python 的 ABC 要求实现接口全部 abstractmethod（见文件末尾
    `_bind_missing_abstract_methods`），Spring 的单例注入用构造器默认值表达。
    """

    # ==================== 常量（一字不改保留原拼写） ====================
    BORDER_WEIGHING_CAPTURE = "BorderWeighingCapture"
    GANTRY_CAPTURE = "GantryCapture"
    PROV_CAPTURE = "ProvCapture"
    SERVICE_AREA_CAPTURE = "ServiceAreaCapture"
    STATION_CAPTURE = "StationCapture"

    FeeRecord = "FeeRecord"
    FeeStationEnter = "FeeStationEnter"
    FeeStationExit = "FeeStationExit"

    redisBiteKey = "sys_config:syncSuspiciousCar_bite"  # 比例默认为0.5
    redisTimeKey = "sys_config:syncSuspiciousCar_time"  # 默认2天
    supoer_mjnum = "sys_config:supoer_mjnum"  # 跨省：门架数量 5个
    road_supoer_mjnum = "sys_config:road_supoer_mjnum"  # 路段：门架数量 3个

    jholiday_time = "sys_config:jholiday_time"  # 节假日时间

    # ==================== 构造器（替代 21 个注入点） ====================
    def __init__(self,
                 redisCache: Optional[RedisCache] = None,
                 redisSourceFactory: Optional[RedisSourceFactory] = None,
                 redisConfig: Optional[RedisConfig] = None,
                 zdataTrailTracksService: Optional[IZdataTrailTracksService] = None,
                 provinceBorderVehicleWeightNewstructureService: Optional[
                     IOdsSzdnProvinceBorderVehicleWeightNewstructureService] = None,
                 snapshotFlowAddcodeService: Optional[IOdsRtSzdnSnapshotFlowAddcodeService] = None,
                 provcaptureAddcodeService: Optional[
                     IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService] = None,
                 stationcaptureAddcodeService: Optional[
                     IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService] = None,
                 odsSzdnTollStationIpService: Optional[IOdsSzdnTollStationIpService] = None,
                 odsSzdnGantryIpService: Optional[IOdsSzdnGantryIpService] = None,
                 feeRecords01Service: Optional[IOdsLwzxsfsjFeeRecords01Service] = None,
                 feeStationEnter01Service: Optional[IOdsLwzxsfsjFeeStationEnter01Service] = None,
                 feeStationExit01Service: Optional[IOdsLwzxsfsjFeeStationExit01Service] = None,
                 zdataLocationDictService: Optional[IZdataLocationDictService] = None,
                 fwqcllsService: Optional[IOdsCxztFwqcllsService] = None,
                 fwqjcxxService: Optional[IDwdLcztFwqjcxxService] = None,
                 sectionService: Optional[IOdsSzdnSectionService] = None,
                 environment: Optional[Environment] = None,
                 odsSzdnGantryService: Optional[IOdsSzdnGantryService] = None,
                 odsSzdnTollService: Optional[IOdsSzdnTollService] = None,
                 httpSysUtilApiService: Optional[HttpSysUtilApiService] = None) -> None:
        # 【Java→Python】`@Autowired` 字段：Spring 按类型注入单例；Python 用可选参数 +
        # 缺省 `new XxxServiceImpl()` 保持"总有一个可用实现"的语义。
        self.redisCache: RedisCache = redisCache if redisCache is not None else RedisCache()
        self.redisSourceFactory: RedisSourceFactory = (
            redisSourceFactory if redisSourceFactory is not None else RedisSourceFactory())
        # Java: @Resource RedisConfig（按名称/类型注入；这里等价为直接 new）
        self.redisConfig: RedisConfig = redisConfig if redisConfig is not None else RedisConfig()
        self.zdataTrailTracksService: IZdataTrailTracksService = (
            zdataTrailTracksService if zdataTrailTracksService is not None
            else ZdataTrailTracksServiceImpl())
        self.provinceBorderVehicleWeightNewstructureService: (
            IOdsSzdnProvinceBorderVehicleWeightNewstructureService) = (
            provinceBorderVehicleWeightNewstructureService
            if provinceBorderVehicleWeightNewstructureService is not None
            else OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl())
        self.snapshotFlowAddcodeService: IOdsRtSzdnSnapshotFlowAddcodeService = (
            snapshotFlowAddcodeService if snapshotFlowAddcodeService is not None
            else OdsRtSzdnSnapshotFlowAddcodeServiceImpl())
        self.provcaptureAddcodeService: IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService = (
            provcaptureAddcodeService if provcaptureAddcodeService is not None
            else OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl())
        self.stationcaptureAddcodeService: (
            IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService) = (
            stationcaptureAddcodeService if stationcaptureAddcodeService is not None
            else OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl())
        self.odsSzdnTollStationIpService: IOdsSzdnTollStationIpService = (
            odsSzdnTollStationIpService if odsSzdnTollStationIpService is not None
            else OdsSzdnTollStationIpServiceImpl())
        self.odsSzdnGantryIpService: IOdsSzdnGantryIpService = (
            odsSzdnGantryIpService if odsSzdnGantryIpService is not None
            else OdsSzdnGantryIpServiceImpl())
        self.feeRecords01Service: IOdsLwzxsfsjFeeRecords01Service = (
            feeRecords01Service if feeRecords01Service is not None
            else OdsLwzxsfsjFeeRecords01ServiceImpl())
        self.feeStationEnter01Service: IOdsLwzxsfsjFeeStationEnter01Service = (
            feeStationEnter01Service if feeStationEnter01Service is not None
            else OdsLwzxsfsjFeeStationEnter01ServiceImpl())
        self.feeStationExit01Service: IOdsLwzxsfsjFeeStationExit01Service = (
            feeStationExit01Service if feeStationExit01Service is not None
            else OdsLwzxsfsjFeeStationExit01ServiceImpl())
        self.zdataLocationDictService: IZdataLocationDictService = (
            zdataLocationDictService if zdataLocationDictService is not None
            else ZdataLocationDictServiceImpl())
        self.fwqcllsService: IOdsCxztFwqcllsService = (
            fwqcllsService if fwqcllsService is not None else OdsCxztFwqcllsServiceImpl())
        self.fwqjcxxService: IDwdLcztFwqjcxxService = (
            fwqjcxxService if fwqjcxxService is not None else DwdLcztFwqjcxxServiceImpl())
        self.sectionService: IOdsSzdnSectionService = (
            sectionService if sectionService is not None else OdsSzdnSectionServiceImpl())
        self.odsSzdnGantryService: IOdsSzdnGantryService = (
            odsSzdnGantryService if odsSzdnGantryService is not None
            else OdsSzdnGantryServiceImpl())
        self.odsSzdnTollService: IOdsSzdnTollService = (
            odsSzdnTollService if odsSzdnTollService is not None else OdsSzdnTollServiceImpl())
        # Java: @Resource HttpSysUtilApiService（Forest 动态代理）
        self.httpSysUtilApiService: HttpSysUtilApiService = (
            httpSysUtilApiService if httpSysUtilApiService is not None
            else ForestHttpSysUtilApiService())

        env = environment if environment is not None else Environment()
        # Java: @Value("${isLocalhost}") —— 无默认值，配置缺失时容器启动失败；
        # 这里用 Environment 替身：缺失会抛 KeyError（等价行为）。
        self.isLocalhost: Optional[str] = env.value("${isLocalhost}", str)

    # ==================== 缓存 key 生成 ====================
    def getCacheKey(self, configKey: str) -> str:
        """设置cache key。"""
        return Constants.trail + configKey

    def getSuspiciousKey(self, curData: str, configKey: str) -> str:
        """可疑车辆 key。"""
        return Constants.car_uspicious + curData + ":" + configKey

    def snapshotFlowListKey(self, curData: str, configKey: str) -> str:
        """门架抓拍流水 key。"""
        return Constants.snapshotFlowList + curData + ":" + configKey

    def feeRecordsListKey(self, curData: str, configKey: str) -> str:
        """门架流水 key。"""
        return Constants.feeRecordsList + curData + ":" + configKey

    def trailFittingKey(self, curData: str, configKey: str) -> str:
        """轨迹点 key：有轨迹。"""
        return Constants.trailFittingList + curData + ":" + configKey

    def trailUnFittingKey(self, curData: str, configKey: str) -> str:
        """轨迹点 key：无轨迹。"""
        return Constants.trailUnFittingList + curData + ":" + configKey

    # ==================== 新增或者修改车辆信息 ====================
    def saveRedis(self, sysUtil: Any) -> AjaxResult:
        """新增或者修改车辆信息。

        【Java→Python】原文方法体几乎全是注释掉的调试代码，只保留配置日志与 success 返回。
        `redisConfig.getClusterNodes()` 返回 String，字符串拼接 null 得 "null"（用 _javaStr）。
        """
        log.info("获取的配置信息：" + _javaStr(self.redisConfig.getClusterNodes())
                 + "--本地配置：" + _javaStr(self.isLocalhost))
        return AjaxResult.success()

    # ==================== 同步轨迹 ====================
    def syncTrack(self, carParaVO: CarParaVO) -> None:
        """同步轨迹。

        【Java→Python】
        - `Object obj = redisCache.getCacheObject(...); if (null != obj) carlist = (List) obj;`
          → 类型强转在 Python 里是直接赋值 + isinstance 校验（保留"不是 List 就当空"的语义）。
        - 生产分支用 JedisCluster 读**另一个 Redis 集群**，本地分支读本进程 Redis。
        - `Math.abs(now - captureTime) <= 24h` 过滤 24 小时内的轨迹点（仅生产分支）。
        """
        carlist: List[Any] = []
        obj = self.redisCache.getCacheObject(Constants.car_list_jc)
        if obj is not None:
            # Java: carlist = (List) obj;  —— 运行时强转，不是 List 会抛 ClassCastException
            if not isinstance(obj, list):
                raise TypeError("java.lang.ClassCastException: cannot cast to java.util.List")
            carlist = obj

        # Java: Map<ZdataTrailTracks, List<TrailBo>> mapCar = new HashMap<>();（原文未使用）
        mapCar: dict[Any, List[TrailBo]] = {}

        if carlist is not None and len(carlist) > 0:
            log.info("获取的配置信息：" + _javaStr(self.redisConfig.getClusterNodes())
                     + "--本地配置：" + _javaStr(self.isLocalhost)
                     + "--同步车辆数量：" + str(len(carlist)))
            jedisCluster: JedisCluster = self.redisSourceFactory.createSource(self.redisConfig)

            # 去掉重合的
            # Java: new SimpleDateFormat("yyyy-MM-dd HH:mm:ss")
            threeMinutesInMillis = 24 * 60 * 60 * 1000  # 24小时转换为毫秒

            for carVO in carlist:
                carNo = CommonUtil.isNull(carVO.getCarNo())
                keyValue = ""

                if CommonUtil.isNull(self.isLocalhost) == "local":
                    # 本地
                    keyValue = self.redisCache.getCacheObject(self.getCacheKey(carNo))
                else:
                    # 生产 ------------
                    keyValue = jedisCluster.get(self.getCacheKey(carNo))

                josnList: List[TrailBo] = []
                if CommonUtil.isNotBlank(keyValue):
                    # 先转josn数组 然后循环 一个一个手动赋值
                    array: JSONArray = JSON.parseArray(keyValue)
                    for o in array:
                        jsonObj: JSONObject = o
                        trailBo = TrailBo()
                        trailBo.setPointUuid(jsonObj.getString("pointUuid"))
                        trailBo.setStateType(jsonObj.getString("stateType"))
                        trailBo.setCaptureTime(jsonObj.getString("captureTime"))
                        trailBo.setLocationCode(jsonObj.getString("locationCode"))
                        trailBo.setLocationName(jsonObj.getString("locationName"))
                        trailBo.setStandardCode(jsonObj.getString("standardCode"))
                        trailBo.setLocationId(jsonObj.getString("locationId"))
                        trailBo.setPlatenumber(jsonObj.getString("platenumber"))

                        lon = jsonObj.getString("longitude")
                        lat = jsonObj.getString("latitude")

                        if CommonUtil.isNotBlank(lon):
                            trailBo.setLon(_bdFloat(lon))
                        if CommonUtil.isNotBlank(lat):
                            trailBo.setLat(_bdFloat(lat))

                        trailBo.setDevCode(trailBo.getStandardCode())
                        trailBo.setDevName(trailBo.getLocationName())

                        # 判断和当前时间相差24小时就不加
                        if CommonUtil.isNull(self.isLocalhost) == "local":
                            josnList.append(trailBo)
                        else:
                            if CommonUtil.isNotBlank(trailBo.getCaptureTime()):
                                try:
                                    captureTimeDate1 = _parseDateTime(trailBo.getCaptureTime())
                                    captureTimeDate2 = datetime.now()
                                    diff = abs(_epochMillis(captureTimeDate2) - _epochMillis(captureTimeDate1))
                                    if diff <= threeMinutesInMillis:
                                        josnList.append(trailBo)
                                except Exception as error:  # noqa: BLE001 - 对应 catch (Exception e)
                                    log.info("实时轨迹日期解析失败------------" + str(error))

                    # 最后一个轨迹点需要查询
                    rtnList: List[TrailBo] = self.mapTrailBoList(josnList)
                    if rtnList is not None and len(rtnList) > 0:
                        # Java: new SimpleDateFormat("yyyyMMdd").format(new Date())
                        formattedDate = datetime.now().strftime("%Y%m%d")

                        tracks = ZdataTrailTracks()
                        tracks.setPlateKey(carNo)
                        tracks.setUuid(carNo + "@@" + formattedDate)
                        tracks.setFlag("currentTrack")  # 实时轨迹

                        trailInfo: TrailInfo = self.changeData(tracks, rtnList)  # 获取设备的经纬度
                        trailInfo.setTrailUuid(carNo)

                        key = Constants.car_curent_trail + carNo
                        self.redisCache.setCacheObject(key, trailInfo)

    # ==================== 数据转换（核心：补全设备经纬度） ====================
    def changeData(self, tracks: ZdataTrailTracks, josnList: List[TrailBo]) -> TrailInfo:
        """数据转换：把轨迹点的设备 IP/编码补全成门架/收费站信息与经纬度。

        【Java→Python】方法体近 600 行，全部是 if/else 与 setter 调用，
        switch (String) → if/elif；其余逐句对应。
        """
        trailInfo = TrailInfo()

        if not (josnList is not None and len(josnList) > 0):
            # Java: if (...) {} else { ...; return trailInfo; }
            trailInfo.setTracks(tracks)
            tempList: List[TrailBo] = []
            trailInfo.setTrailList(tempList)
            return trailInfo

        serviceAreaCaptureUUids = ""  # 服务区抓拍

        for trailBo in josnList:
            pointUuid = trailBo.getPointUuid()
            stateType = CommonUtil.isNull(trailBo.getStateType())
            if stateType == SysUtilServiceImpl.SERVICE_AREA_CAPTURE:
                serviceAreaCaptureUUids += _javaStr(pointUuid) + ","

        # 服务区抓拍（原文已注释掉查询，保留变量拼装逻辑）
        # Map<String, OdsCxztFwqclls> fwqcllsMap = new HashMap<>();
        # serviceAreaCaptureUUids = CommonUtil.deleteEnd(serviceAreaCaptureUUids);
        # if (CommonUtil.isNotBlank(serviceAreaCaptureUUids)) { ... }

        # 收费站ip
        szdnTollMap: dict[str, OdsSzdnTollStationIp] = (
            self.odsSzdnTollStationIpService.selectStationIpMap())

        # 收费站code
        odsSzdnTollMap: dict[str, OdsSzdnToll] = self.odsSzdnTollService.getRedisMap()

        # 门架IP
        szdnGantryMap: dict[str, OdsSzdnGantryIp] = (
            self.odsSzdnGantryIpService.selectOdsSzdnGantryIpMap())

        # 位置信息
        locationMap: dict[str, ZdataLocationDict] = self.zdataLocationDictService.getRedisList()

        # 根据路段查询路线map
        sectionMap: dict[str, OdsSzdnSection] = self.sectionService.getSectionMap()

        firtStationCode = ""  # 入栈口编号（原文未赋值）
        firtStationName = ""  # 入栈口名称（原文未赋值）
        firtStationTime = ""  # 入栈口时间（原文未赋值）

        plateColor = ""  # 车牌颜色（字典：1白色2黑色）
        carType = ""  # 车型
        carVehicle = ""  # 车种
        carNum: Optional[int] = None  # 轴数
        passType = ""  # 1-OBU 2-CPC卡 3-纸券 9-无通行介质,4- M1卡
        indexType = ""  # 查询类型

        for trailBo in josnList:
            # -------------- 抓拍信息
            pointUuid = trailBo.getPointUuid()
            locationCode = CommonUtil.isNull(trailBo.getLocationCode())  # 设备IP地址
            stateType = CommonUtil.isNull(trailBo.getStateType())  # 流水来源类型标识

            sectionCode = CommonUtil.isNull(trailBo.getSectionCode())
            pileno = CommonUtil.isNull(trailBo.getPileno())
            lon = trailBo.getLon()
            # 【忠实保留原缺陷】纬度取的是 getLon()（原文写错）
            lat = trailBo.getLon()
            roadCode = ""

            # 这个要查询数据库拿---
            if CommonUtil.isNotBlank(sectionCode):
                if sectionCode in sectionMap:
                    section = sectionMap[sectionCode]
                    roadCode = CommonUtil.isNull(section.getRoadCode())
                    trailBo.setRoadCode(roadCode)

            if stateType == SysUtilServiceImpl.BORDER_WEIGHING_CAPTURE:
                # 省界称重
                indexType = "gantryType"  # 门架
            elif stateType == SysUtilServiceImpl.GANTRY_CAPTURE:
                # 门架抓拍
                indexType = "gantryType"  # 门架
            elif stateType == SysUtilServiceImpl.PROV_CAPTURE:
                # 省界抓拍
                indexType = "gantryType"  # 门架
            elif stateType == SysUtilServiceImpl.SERVICE_AREA_CAPTURE:
                # 服务区抓拍
                indexType = "service_area"  # 服务区
            elif stateType == SysUtilServiceImpl.STATION_CAPTURE:
                # 收费站抓拍
                indexType = "stationType"  # 收费站
            elif stateType == SysUtilServiceImpl.FeeRecord:
                # 卡口流水
                indexType = "gantryType"  # 门架
            elif stateType == SysUtilServiceImpl.FeeStationEnter:
                # 收费站入口流水
                indexType = "stationType"  # 收费站
            elif stateType == SysUtilServiceImpl.FeeStationExit:
                # 收费站出口流水
                indexType = "stationType"  # 收费站

            # ---------------通过位置信息查询设备
            devLocatCode = ""
            if locationCode in locationMap:
                devLocatCode = CommonUtil.isNull(locationMap[locationCode].getStandardCode())

            devCodeId = CommonUtil.isNull(trailBo.getDevCode())  # 通过设备编码先查询

            if indexType == "stationType":
                # 收费站ip 或者CODE查询
                stationIpBO: Optional[OdsSzdnTollStationIp] = None

                # 从位置信息
                if CommonUtil.isNotBlank(devLocatCode):
                    stationIpBO = szdnTollMap.get(devLocatCode)

                # 从设备id拿
                if stationIpBO is None:
                    if CommonUtil.isNotBlank(devCodeId):
                        stationIpBO = szdnTollMap.get(devCodeId)

                # 从当前位置拿
                if stationIpBO is None:
                    if CommonUtil.isNotBlank(locationCode):
                        stationIpBO = szdnTollMap.get(locationCode)

                if stationIpBO is not None:
                    trailBo.setDevCode(stationIpBO.getTollCode())  # 设备编号
                    trailBo.setDevName(stationIpBO.getTollName())  # 设备名称

                    odsSzdnToll: Optional[OdsSzdnToll] = stationIpBO.getOdsSzdnToll()
                    if odsSzdnToll is not None:
                        if lon is None:
                            # 经度
                            if CommonUtil.isNotBlank(odsSzdnToll.getLongitude()):
                                trailBo.setLon(_bdFloat(odsSzdnToll.getLongitude()))

                        if lat is None:
                            # 纬度（原文注释写"经度"，沿用原写法）
                            if CommonUtil.isNotBlank(odsSzdnToll.getLatitude()):
                                trailBo.setLat(_bdFloat(odsSzdnToll.getLatitude()))

                        if CommonUtil.isBlank(roadCode):
                            # 路线编号
                            trailBo.setRoadCode(CommonUtil.isNull(odsSzdnToll.getRoadCode()))

                        if CommonUtil.isBlank(sectionCode):
                            # 路段
                            trailBo.setSectionCode(CommonUtil.isNull(odsSzdnToll.getSectionCode()))

                        if CommonUtil.isBlank(pileno):
                            # 桩号
                            trailBo.setPileno(CommonUtil.isNull(odsSzdnToll.getPileNo()))

            elif indexType == "gantryType":
                # 门架ip
                gantryIpBO: Optional[OdsSzdnGantryIp] = None

                # 从位置信息
                if CommonUtil.isNotBlank(devLocatCode):
                    gantryIpBO = szdnGantryMap.get(devLocatCode)

                # 从设备id拿
                if gantryIpBO is None:
                    if CommonUtil.isNotBlank(devCodeId):
                        gantryIpBO = szdnGantryMap.get(devCodeId)

                # 从当前位置拿
                if gantryIpBO is None:
                    if CommonUtil.isNotBlank(locationCode):
                        gantryIpBO = szdnGantryMap.get(locationCode)

                if gantryIpBO is not None:
                    trailBo.setDevCode(gantryIpBO.getGantryCode())  # 设备编号
                    trailBo.setDevName(gantryIpBO.getGantryName())  # 设备名称

                    odsSzdnGantry: Optional[OdsSzdnGantry] = gantryIpBO.getOdsSzdnGantry()
                    if odsSzdnGantry is not None:
                        if lon is None:
                            # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.getLon()):
                                trailBo.setLon(_bdFloat(odsSzdnGantry.getLon()))

                        if lat is None:
                            # 纬度（原文注释写"经度"）
                            if CommonUtil.isNotBlank(odsSzdnGantry.getLat()):
                                trailBo.setLat(_bdFloat(odsSzdnGantry.getLat()))

                        if CommonUtil.isBlank(roadCode):
                            # 路线编号
                            trailBo.setRoadCode(CommonUtil.isNull(odsSzdnGantry.getRoadCode()))

                        if CommonUtil.isBlank(sectionCode):
                            # 路段编号
                            trailBo.setSectionCode(CommonUtil.isNull(odsSzdnGantry.getSectionCode()))

                        if CommonUtil.isBlank(pileno):
                            # 桩号
                            trailBo.setPileno(CommonUtil.isNull(odsSzdnGantry.getPileNo()))

                        trailBo.setDirection(odsSzdnGantry.getDirection())  # 方向
                        trailBo.setIsVirtual(odsSzdnGantry.getIsVirtual())  # 虚拟门架

            elif indexType == "service_area":
                # 服务区
                locationCode = locationCode.replace("devip:", "serviceip:")
                if locationCode in locationMap:
                    locationDict: ZdataLocationDict = locationMap[locationCode]

                    trailBo.setDevCode(locationDict.getStandardCode())  # 设备编号
                    trailBo.setDevName(locationDict.getName())  # 设备名称

                    # 经度
                    if locationDict.getLongitude() is not None:
                        trailBo.setLon(locationDict.getLongitude())

                    # 纬度（原文注释写"经度"）
                    if locationDict.getLatitude() is not None:
                        trailBo.setLat(locationDict.getLatitude())

                    # 路线编号
                    trailBo.setRoadCode(CommonUtil.isNull(locationDict.getRoadcode()))

                    # 路段
                    trailBo.setSectionCode(CommonUtil.isNull(locationDict.getSectioncode()))

                    # 桩号
                    trailBo.setPileno(CommonUtil.isNull(locationDict.getPileNo()))

                    trailBo.setDirection(locationDict.getDirection())  # 方向

            # 设备名称没有默认位置信息--------------
            if CommonUtil.isBlank(trailBo.getDevName()):
                trailBo.setDevName(CommonUtil.isNull(locationCode).replace("serviceip:", ""))

        tracks.setFirtStationCode(firtStationCode)
        tracks.setFirtStationName(firtStationName)
        tracks.setFirtStationTime(firtStationTime)
        tracks.setPlateColor(plateColor)
        tracks.setCarType(carType)
        tracks.setCarVehicle(carVehicle)
        tracks.setCarNum(carNum)
        tracks.setPassType(passType)

        # ------------------------- 获取起点 终点 的经纬度
        jwdList: List[TrailBo] = []
        if josnList is not None and len(josnList) > 0:
            for trailBo in josnList:
                if trailBo.getLon() is not None and trailBo.getLat() is not None:
                    jwdList.append(trailBo)

        if CommonUtil.isNull(tracks.getFlag()) == "currentTrack":
            # 实时轨迹
            if jwdList is not None and len(jwdList) > 0:
                firstTrailBo: TrailBo = jwdList[0]

                tracks.setEntollstationid(CommonUtil.isNull(firstTrailBo.getDevCode()))
                tracks.setEntollstationname(CommonUtil.isNull(firstTrailBo.getDevName()))
                tracks.setStartLon(CommonUtil.isNull(firstTrailBo.getLon()))  # 经度
                tracks.setStratLat(CommonUtil.isNull(firstTrailBo.getLat()))  # 纬度

                if len(jwdList) > 1:
                    endTrailBo: TrailBo = jwdList[len(jwdList) - 1]
                    tracks.setExtollstationid(CommonUtil.isNull(endTrailBo.getDevCode()))
                    tracks.setExtollstationname(CommonUtil.isNull(endTrailBo.getDevName()))
                    tracks.setEndLon(CommonUtil.isNull(endTrailBo.getLon()))  # 经度
                    tracks.setEndLat(CommonUtil.isNull(endTrailBo.getLat()))  # 纬度
        else:
            # 历史轨迹：
            firstCode = CommonUtil.isNull(tracks.getEntollstationid())  # 入口收费站编号
            firstName = CommonUtil.repalaceSzdnTollName(tracks.getEntollstationname())
            endCode = CommonUtil.isNull(tracks.getExtollstationid())  # 出口收费站编号
            endName = CommonUtil.repalaceSzdnTollName(tracks.getExtollstationname())

            if CommonUtil.isNotBlank(firstCode):
                # 收费站ip
                if firstCode in odsSzdnTollMap:
                    odsSzdnToll: Optional[OdsSzdnToll] = odsSzdnTollMap[firstCode]
                    if odsSzdnToll is not None:
                        if CommonUtil.isNotBlank(odsSzdnToll.getLongitude()):
                            tracks.setStartLon(odsSzdnToll.getLongitude())  # 经度
                        if CommonUtil.isNotBlank(odsSzdnToll.getLatitude()):
                            tracks.setStratLat(odsSzdnToll.getLatitude())  # 纬度
                        tracks.setEntollstationid(CommonUtil.isNull(odsSzdnToll.getTollCode()))
                else:
                    # 门架
                    if firstCode in szdnGantryMap:
                        gantryIpBO: OdsSzdnGantryIp = szdnGantryMap[firstCode]
                        odsSzdnGantry: Optional[OdsSzdnGantry] = gantryIpBO.getOdsSzdnGantry()
                        if odsSzdnGantry is not None:
                            if CommonUtil.isNotBlank(odsSzdnGantry.getLon()):
                                tracks.setStartLon(odsSzdnGantry.getLon())  # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.getLat()):
                                tracks.setStratLat(odsSzdnGantry.getLat())  # 纬度

            # --------- 如果拿不到就根据名称来拿
            if CommonUtil.isBlank(tracks.getStartLon()):
                if CommonUtil.isNotBlank(firstName):
                    # 收费站ip
                    if firstName in szdnTollMap:
                        stationIpBO: OdsSzdnTollStationIp = szdnTollMap[firstName]
                        odsSzdnToll: Optional[OdsSzdnToll] = stationIpBO.getOdsSzdnToll()
                        if odsSzdnToll is not None:
                            if CommonUtil.isNotBlank(odsSzdnToll.getLongitude()):
                                tracks.setStartLon(odsSzdnToll.getLongitude())  # 经度
                            if CommonUtil.isNotBlank(odsSzdnToll.getLatitude()):
                                tracks.setStratLat(odsSzdnToll.getLatitude())  # 纬度
                        tracks.setEntollstationid(CommonUtil.isNull(stationIpBO.getTollCode()))
                    else:
                        # 门架
                        if firstName in szdnGantryMap:
                            gantryIpBO: OdsSzdnGantryIp = szdnGantryMap[firstName]
                            odsSzdnGantry: Optional[OdsSzdnGantry] = gantryIpBO.getOdsSzdnGantry()
                            if odsSzdnGantry is not None:
                                if CommonUtil.isNotBlank(odsSzdnGantry.getLon()):
                                    tracks.setStartLon(odsSzdnGantry.getLon())  # 经度
                                if CommonUtil.isNotBlank(odsSzdnGantry.getLat()):
                                    tracks.setStratLat(odsSzdnGantry.getLat())  # 纬度
                            tracks.setEntollstationid(CommonUtil.isNull(gantryIpBO.getGantryCode()))

            if CommonUtil.isNotBlank(endCode):
                # 收费站ip
                if endCode in odsSzdnTollMap:
                    odsSzdnToll: Optional[OdsSzdnToll] = odsSzdnTollMap[endCode]
                    if odsSzdnToll is not None:
                        if CommonUtil.isNotBlank(odsSzdnToll.getLongitude()):
                            tracks.setEndLon(odsSzdnToll.getLongitude())  # 经度
                        if CommonUtil.isNotBlank(odsSzdnToll.getLatitude()):
                            tracks.setEndLat(odsSzdnToll.getLatitude())  # 纬度
                        tracks.setExtollstationid(CommonUtil.isNull(odsSzdnToll.getTollCode()))
                else:
                    # 门架
                    if endCode in szdnGantryMap:
                        gantryIpBO: OdsSzdnGantryIp = szdnGantryMap[endCode]
                        odsSzdnGantry: Optional[OdsSzdnGantry] = gantryIpBO.getOdsSzdnGantry()
                        if odsSzdnGantry is not None:
                            if CommonUtil.isNotBlank(odsSzdnGantry.getLon()):
                                tracks.setEndLon(odsSzdnGantry.getLon())  # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.getLat()):
                                tracks.setEndLat(odsSzdnGantry.getLat())  # 纬度

            # --------- 如果拿不到就根据名称来拿
            if CommonUtil.isBlank(tracks.getEndLon()):
                if CommonUtil.isNotBlank(endName):
                    # 收费站ip
                    if endName in szdnTollMap:
                        stationIpBO: OdsSzdnTollStationIp = szdnTollMap[endName]
                        odsSzdnToll: Optional[OdsSzdnToll] = stationIpBO.getOdsSzdnToll()
                        if odsSzdnToll is not None:
                            if CommonUtil.isNotBlank(odsSzdnToll.getLongitude()):
                                tracks.setEndLon(odsSzdnToll.getLongitude())  # 经度
                            if CommonUtil.isNotBlank(odsSzdnToll.getLatitude()):
                                tracks.setEndLat(odsSzdnToll.getLatitude())  # 纬度
                        tracks.setExtollstationid(CommonUtil.isNull(stationIpBO.getTollCode()))
                    else:
                        # 门架
                        if endName in szdnGantryMap:
                            gantryIpBO: OdsSzdnGantryIp = szdnGantryMap[endName]
                            odsSzdnGantry: Optional[OdsSzdnGantry] = gantryIpBO.getOdsSzdnGantry()
                            if odsSzdnGantry is not None:
                                if CommonUtil.isNotBlank(odsSzdnGantry.getLon()):
                                    tracks.setEndLon(odsSzdnGantry.getLon())  # 经度
                                if CommonUtil.isNotBlank(odsSzdnGantry.getLat()):
                                    tracks.setEndLat(odsSzdnGantry.getLat())  # 纬度
                            tracks.setExtollstationid(CommonUtil.isNull(gantryIpBO.getGantryCode()))

        # 【Java→Python】new BigDecimal(String) → 先 _bd 校验，再落 float 字段
        if CommonUtil.isNotBlank(tracks.getStartLon()):
            tracks.setStartLonDec(_bdFloat(tracks.getStartLon()))
        if CommonUtil.isNotBlank(tracks.getStratLat()):
            tracks.setStratLatDec(_bdFloat(tracks.getStratLat()))
        if CommonUtil.isNotBlank(tracks.getEndLon()):
            tracks.setEndLonDec(_bdFloat(tracks.getEndLon()))
        if CommonUtil.isNotBlank(tracks.getEndLat()):
            tracks.setEndLatDec(_bdFloat(tracks.getEndLat()))

        trailInfo.setTracks(tracks)
        trailInfo.setTrailList(josnList)

        return trailInfo


    # ==================================================================
    # Java L969-L1223：获取抓拍对象
    # ==================================================================
    def getByTrailBo(self, trailBo: Optional[TrailBo]) -> TrailBo:
        """按轨迹点的 stateType 到对应抓拍/流水表补齐图片、车牌颜色、设备编号。

        【Java→Python 关键差异】
        1) 8 个 `String xxUUids = ""` 是"同类 uuid 用逗号拼接"的累加器，仍是**字符串拼接**；
           `pointUuid` 可能为 null，Java 拼出来是 "null"，这里用 `_javaStr` 复刻该语义。
        2) `switch (stateType)`（Java 对 String 的 switch）→ if/elif；原文没有 default 分支，
           Python 也不写 else（未知 stateType 什么都不做）。
        3) 【忠实保留的缺陷】`case FeeRecord/FeeStationEnter/FeeStationExit` 三支的
           `xxUUids += pointUuid + ","` **在原 Java 中被整行注释掉**，因此这三个累加器
           永远保持 ""，对应的 3 张表永远不会查询，第 2 个 switch 的这 3 个分支永远走不到。
           此处原样保留（不补全拼接语句），仅用 pass 占位并标注。
        4) 8 个子查询返回 `Map<String, Xxx>` → `dict`；uuid 为空时**不查询**，保持空 dict。
        5) `JSON.parseArray(text)` → 替身 JSONArray，逐项取 `snapPicturePath` 子字段。
        6) 末尾 `CommonUtil.deleteEnd` 去掉最后一个逗号，再 `repalacePicUrl` 做图片域名替换。
        """
        if trailBo is None:
            # Java: if (null == trailBo) { return new TrailBo(); }
            return TrailBo()

        borderWeighingCaptureUUids = ""  # 省界称重
        gantryCaptureUUids = ""  # 门架抓拍
        provCaptureUUids = ""  # 省界抓拍
        serviceAreaCaptureUUids = ""  # 服务区抓拍
        stationCaptureUUids = ""  # 收费站抓拍
        feeRecordUUids = ""  # 卡口流水
        feeStationEnterUUids = ""  # 收费站入口流水
        feeStationExitUUids = ""  # 收费站出口流水

        captureTime = CommonUtil.isNull(trailBo.getCaptureTime())
        applyTime1 = ""
        applyTime2 = ""
        if CommonUtil.isNotBlank(captureTime):
            # 获取开始时间
            try:
                # 【Java→Python】`SimpleDateFormat("yyyy-MM-dd")` 是 lenient 且**只消费前缀**：
                # 传入 "2026-06-01 12:00:00" 也能解析成功；`strptime` 要求整串匹配，
                # 故显式截取日期前缀（前 10 位）后再解析，与原实现等价。
                captureTimeDate1 = datetime.strptime(captureTime[:10], "%Y-%m-%d")
                baseQueryTime = captureTimeDate1.strftime("%Y-%m-%d")
                applyTime1 = baseQueryTime + " 00:00:00"
                applyTime2 = baseQueryTime + " 23:59:59"
            except Exception as e:
                # Java: catch (Exception e) { log.info("日期解析失败------------" + e.toString()); }
                log.info("日期解析失败------------" + str(e))

        stateType = CommonUtil.isNull(trailBo.getStateType())
        pointUuid = trailBo.getPointUuid()

        # ---------------- switch (stateType)：第 1 段，按类型收集 uuid ----------------
        if stateType == self.BORDER_WEIGHING_CAPTURE:
            # 省界称重
            borderWeighingCaptureUUids += _javaStr(pointUuid) + ","
        elif stateType == self.GANTRY_CAPTURE:
            # 门架抓拍
            gantryCaptureUUids += _javaStr(pointUuid) + ","
        elif stateType == self.PROV_CAPTURE:
            # 省界抓拍
            provCaptureUUids += _javaStr(pointUuid) + ","
        elif stateType == self.SERVICE_AREA_CAPTURE:
            # 服务区抓拍
            serviceAreaCaptureUUids += _javaStr(pointUuid) + ","
        elif stateType == self.STATION_CAPTURE:
            # 收费站抓拍
            stationCaptureUUids += _javaStr(pointUuid) + ","
        elif stateType == self.FeeRecord:
            # 卡口流水：原文 `// feeRecordUUids += pointUuid + ",";` 被注释 → 永远不查询
            pass
        elif stateType == self.FeeStationEnter:
            # 收费站入口流水：原文拼接语句被注释 → 永远不查询
            pass
        elif stateType == self.FeeStationExit:
            # 收费站出口流水：原文拼接语句被注释 → 永远不查询
            pass

        # 省界称重
        weightNewstructureMap: dict[str, OdsSzdnProvinceBorderVehicleWeightNewstructure] = {}
        borderWeighingCaptureUUids = CommonUtil.deleteEnd(borderWeighingCaptureUUids)
        if CommonUtil.isNotBlank(borderWeighingCaptureUUids):
            weightNewstructureMap = (
                self.provinceBorderVehicleWeightNewstructureService.
                selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(
                    borderWeighingCaptureUUids))

        # 门架抓拍
        snapshotFlowAddcodeMap: dict[str, OdsRtSzdnSnapshotFlowAddcode] = {}
        gantryCaptureUUids = CommonUtil.deleteEnd(gantryCaptureUUids)
        if CommonUtil.isNotBlank(gantryCaptureUUids):
            snapshotFlowAddcodeMap = (
                self.snapshotFlowAddcodeService.
                selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(
                    gantryCaptureUUids, applyTime1, applyTime2))

        # 省界抓拍
        provcaptureAddcodeMap: dict[str, OdsRtSzdnSnapshotFlowProvcaptureAddcode] = {}
        provCaptureUUids = CommonUtil.deleteEnd(provCaptureUUids)
        if CommonUtil.isNotBlank(provCaptureUUids):
            provcaptureAddcodeMap = (
                self.provcaptureAddcodeService.
                selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(provCaptureUUids))

        # 服务区抓拍
        fwqcllsMap: dict[str, OdsCxztFwqclls] = {}
        serviceAreaCaptureUUids = CommonUtil.deleteEnd(serviceAreaCaptureUUids)
        if CommonUtil.isNotBlank(serviceAreaCaptureUUids):
            fwqcllsMap = (
                self.fwqcllsService.
                selectOdsCxztFwqcllsByQueryUuids(serviceAreaCaptureUUids))

        # 收费站抓拍
        stationcaptureAddcodeMap: dict[str, OdsRtSzdnSnapshotFlowStationcaptureAddcode] = {}
        stationCaptureUUids = CommonUtil.deleteEnd(stationCaptureUUids)
        if CommonUtil.isNotBlank(stationCaptureUUids):
            stationcaptureAddcodeMap = (
                self.stationcaptureAddcodeService.
                selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(
                    stationCaptureUUids, applyTime1, applyTime2))

        # 卡口流水（原文未收集 uuid → 恒为空，不会查询）
        feeRecordMap: dict[str, OdsLwzxsfsjFeeRecords01] = {}
        feeRecordUUids = CommonUtil.deleteEnd(feeRecordUUids)
        if CommonUtil.isNotBlank(feeRecordUUids):
            feeRecordMap = (
                self.feeRecords01Service.
                selectOdsLwzxsfsjFeeRecords01ByQueryUuids(feeRecordUUids, applyTime1, applyTime2))

        # 收费站入口流水（原文未收集 uuid → 恒为空，不会查询）
        feeStationEnterMap: dict[str, OdsLwzxsfsjFeeStationEnter01] = {}
        feeStationEnterUUids = CommonUtil.deleteEnd(feeStationEnterUUids)
        if CommonUtil.isNotBlank(feeStationEnterUUids):
            feeStationEnterMap = (
                self.feeStationEnter01Service.
                selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids(feeStationEnterUUids))

        # 收费站出口流水（原文未收集 uuid → 恒为空，不会查询）
        feeStationExitMap: dict[str, OdsLwzxsfsjFeeStationExit01] = {}
        feeStationExitUUids = CommonUtil.deleteEnd(feeStationExitUUids)
        if CommonUtil.isNotBlank(feeStationExitUUids):
            feeStationExitMap = (
                self.feeStationExit01Service.
                selectOdsLwzxsfsjFeeStationExit01ByQueryUuids(feeStationExitUUids))

        # 以下 4 段（收费站ip / 门架IP / 位置信息 / 服务区信息）在原 Java 中整块被注释掉，
        # 保留注释位置说明依赖仍在构造器中（未删除注入点，避免破坏 Spring 装配关系）。

        # ---------------- switch (stateType)：第 2 段，回填抓拍图片/车牌颜色/设备编号 ----------------
        if stateType == self.BORDER_WEIGHING_CAPTURE:
            # 省界称重
            if pointUuid in weightNewstructureMap:
                borderWeighingCaptureBO = weightNewstructureMap[pointUuid]

                # 抓拍照片
                imagesStr = CommonUtil.isNull(borderWeighingCaptureBO.getWeighingImagesArry())
                if CommonUtil.isNotBlank(imagesStr):
                    imagesSrc = ""
                    imgesJsonArray: JSONArray = JSON.parseArray(imagesStr)
                    for zz in range(imgesJsonArray.size()):
                        imageTempJosn = imgesJsonArray.getJSONObject(zz)
                        if imageTempJosn is not None:
                            tempImageSrc = CommonUtil.isNull(
                                imageTempJosn.getString("snapPicturePath"))
                            if CommonUtil.isNotBlank(tempImageSrc):
                                imagesSrc += tempImageSrc + ","
                    trailBo.setImagesArry(CommonUtil.deleteEnd(imagesSrc))  # 抓拍照片
        elif stateType == self.GANTRY_CAPTURE:
            if pointUuid in snapshotFlowAddcodeMap:
                gantryCaptureBO = snapshotFlowAddcodeMap[pointUuid]
                trailBo.setImagesArry(gantryCaptureBO.getSnappicturepath())  # 抓拍照片

                # 车牌颜色
                trailBo.setPlatecolor(CommonUtil.isNull(gantryCaptureBO.getPlatecolor()))
        elif stateType == self.PROV_CAPTURE:
            # 省界抓拍
            if pointUuid in provcaptureAddcodeMap:
                imagesSrc = ""
                provCaptureBO = provcaptureAddcodeMap[pointUuid]
                # 车牌图路径
                if CommonUtil.isNotBlank(provCaptureBO.getPlateimage()):
                    imagesSrc += provCaptureBO.getPlateimage() + ","

                # 车身图路径
                if CommonUtil.isNotBlank(provCaptureBO.getSideimage()):
                    imagesSrc += provCaptureBO.getSideimage() + ","

                # 车头图路径
                if CommonUtil.isNotBlank(provCaptureBO.getHeadimage()):
                    imagesSrc += provCaptureBO.getHeadimage() + ","
                trailBo.setImagesArry(CommonUtil.deleteEnd(imagesSrc))  # 抓拍照片
        elif stateType == self.SERVICE_AREA_CAPTURE:
            # 服务区抓拍
            if pointUuid in fwqcllsMap:
                fwqclls = fwqcllsMap[pointUuid]
                imagesSrc = ""
                # 抓拍照片url
                if CommonUtil.isNotBlank(fwqclls.getTargetpicurl()):
                    imagesSrc += fwqclls.getTargetpicurl() + ","

                # 车牌照片
                if CommonUtil.isNotBlank(fwqclls.getPlatepicurl()):
                    imagesSrc += fwqclls.getPlatepicurl() + ","

                # 抓拍照片
                trailBo.setImagesArry(CommonUtil.deleteEnd(imagesSrc))  # 抓拍照片
        elif stateType == self.STATION_CAPTURE:
            # 收费站抓拍
            if pointUuid in stationcaptureAddcodeMap:
                stationCapture = stationcaptureAddcodeMap[pointUuid]
                trailBo.setImagesArry(stationCapture.getSnappicturepath())  # 抓拍照片
        elif stateType == self.FeeRecord:
            # 卡口流水（因 uuid 未收集，map 恒为空 → 该分支实际不可达，原样保留）
            if pointUuid in feeRecordMap:
                feeRecords = feeRecordMap[pointUuid]
                trailBo.setDevCode(feeRecords.getGantryid())  # 设备编号
                trailBo.setImagesArry("")  # 抓拍照片
        elif stateType == self.FeeStationEnter:
            # 收费站入口流水（同上，不可达）
            if pointUuid in feeStationEnterMap:
                feeStationEnter = feeStationEnterMap[pointUuid]
                trailBo.setImagesArry("")  # 抓拍照片
        elif stateType == self.FeeStationExit:
            # 收费站出口流水（同上，不可达）
            if pointUuid in feeStationExitMap:
                feeStationExit = feeStationExitMap[pointUuid]
                trailBo.setImagesArry("")  # 抓拍照片

        # 图片替换----
        imagesArry = CommonUtil.deleteEnd(trailBo.getImagesArry())
        trailBo.setImagesArry(CommonUtil.repalacePicUrl(imagesArry))

        return trailBo

    # ==================================================================
    # Java L1233-L1236：同步可疑车辆（原方法体为空实现）
    # ==================================================================
    def syncSuspiciousCar(self, carParaVO: CarParaVO) -> dict[ZdataTrailTracks, List[TrailBo]]:
        """【Java→Python】原文就只 `return new HashMap<>();`（未实现），此处忠实返回 `{}`。

        注意 `Map<ZdataTrailTracks, List<TrailBo>>` 的 key 在 Java 靠 Lombok 的
        hashCode/equals；Python dataclass 默认不可哈希，这里返回空 dict 不受影响，
        若将来要真正填充，必须改用可哈希的 key（如 plateKey + enterTime 拼串）。
        """
        return {}

    # ==================================================================
    # Java L1245-L1635：同步可疑车辆（跨省全程屏蔽 + 关注路段屏蔽）
    # ==================================================================
    def syncSuspiciousCarQutaz(self, startNum: int, endNum: int) -> None:
        """从 Redis 取配置 → 按天分页拉轨迹 → 判"跨省全程屏蔽"/"关注路段屏蔽" → 写 Redis。

        【Java→Python 关键差异】
        1) `new BigDecimal("0.3")` → `_bd("0.3")`；`Integer.parseInt(str)` → `int(str)`
           （非数字抛 ValueError，对应 NumberFormatException）。
        2) `Calendar.getInstance(); calendar.add(DAY_OF_MONTH, -starTime)` →
           `datetime.now() - timedelta(days=starTime)`（都是"当前时间往前推 N 天"）。
        3) Java 的 `log.info("..." + obj)` 对 null 输出 "null"、对 Date 输出 Date#toString()，
           这里统一包 `_javaStr` / `_javaDateToString` 保持日志文本一致。
        4) `List#add` → `list.append`；`redisCache.getCacheObject` 返回 **deepcopy**，
           "取出→append→setCacheObject 写回"才能更新缓存（原文就是这么写的）。
        5) 【忠实保留】`gantryMao` / `locationMap` / `sectionMap` 计算后**从未使用**，
           原文如此；`firstCode`/`endCode` 亦未参与判断，仅用于名称解析前的占位。
        6) `for (int i = startNum; i <= endNum; i++)` → `range(startNum, endNum + 1)`（含右端）。
        7) `bite` 变量在原逻辑中只出现在被注释的"部分屏蔽"判断里（`bite.compareTo(costBite)`），
           保留读取配置与日志，但当前**不参与判定**。
        """
        pageSize = 10
        starTime = 2
        endTime = 4
        bite = _bd("0.3")  # 门架抓拍和流水抓拍占比（原注释写 0.3，常量注释写 0.5）

        supoerMjnum = 5  # 跨省：同步可疑车辆门架抓拍数量5个以上
        roadSupoerMjnum = 3  # 路段：门架抓拍数量和门架流水数量对比

        # -------------- 从缓存取得对应的配置
        redisTimeValue = self.redisCache.getCacheObject(self.redisTimeKey)  # 默认2天
        if CommonUtil.isNotBlank(redisTimeValue):
            starTime = int(redisTimeValue)
            log.info("从缓存取得时间配置--------：" + _javaStr(redisTimeValue))

        redisBiteValue = self.redisCache.getCacheObject(self.redisBiteKey)  # 比例默认为0.3
        if CommonUtil.isNotBlank(redisBiteValue):
            bite = _bd(redisBiteValue)
            log.info("从缓存取得占比配置------：" + _javaStr(bite))

        supoerMjnumValue = self.redisCache.getCacheObject(self.supoer_mjnum)  # 比例默认为5
        if CommonUtil.isNotBlank(supoerMjnumValue):
            supoerMjnum = int(supoerMjnumValue)
            log.info("从缓存取得跨省：门架抓拍数量------：" + _javaStr(supoerMjnum))

        roadSupoeMjnumValue = self.redisCache.getCacheObject(self.road_supoer_mjnum)  # 比例默认为3
        if CommonUtil.isNotBlank(roadSupoeMjnumValue):
            roadSupoerMjnum = int(roadSupoeMjnumValue)
            log.info("从缓存路段：取得门架抓拍数量------：" + _javaStr(roadSupoeMjnumValue))

        # 判断节假日
        jholidayTimeValue = CommonUtil.isNull(self.redisCache.getCacheObject(self.jholiday_time))
        log.info("从缓存路段：取得节假日------：" + jholidayTimeValue)

        if CommonUtil.isNull(self.isLocalhost) == "local":
            log.info("本地配置------：" + CommonUtil.isNull(self.isLocalhost))
            # 本地  分页1000条 30 到 1 天
            pageSize = 2000
            endTime = starTime * 2
        else:
            log.info("生产配置------：" + CommonUtil.isNull(self.isLocalhost))
            # 生产------------- 分页1000条 14 到 7 天
            pageSize = 2000
            endTime = starTime * 2

        log.info("分页配置：" + _javaStr(pageSize) + "--时间范围" + _javaStr(starTime) + "到"
                 + _javaStr(endTime))

        carParaVO = CarParaVO()
        # ----------7 到 14天
        carParaVO.setStarTime(starTime)
        carParaVO.setEndTime(endTime)

        gantryList = self.odsSzdnGantryService.getGantryRedis()
        gantryMao: dict[str, OdsSzdnGantry] = {}
        for rtnOdsSzdnGantry in gantryList:
            gantryMao[CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode())] = rtnOdsSzdnGantry

        # 位置信息
        locationMap: dict[str, ZdataLocationDict] = self.zdataLocationDictService.getRedisList()

        # 根据路段查询路线map
        sectionMap: dict[str, OdsSzdnSection] = self.sectionService.getSectionMap()

        # 查询路段list
        sectionlist = self.sectionService.getSectionList()

        # 筛选的路段信息-------------
        # String indexRoadCode = "G45"; // 大广高速
        indexSectionCode = "200R500450649000"  # 泰赣路段编码
        indexSectionName = "泰赣路段"  # 泰赣路段
        indexRoadCodeMap: dict[str, str] = {}
        sectionsQueryList: List[str] = []
        for odsSzdnSection in sectionlist:
            roadCode = CommonUtil.isNull(odsSzdnSection.getRoadCode())  # 路线
            sectionCode = CommonUtil.isNull(odsSzdnSection.getSectionCode())  # 路段编码
            if CommonUtil.isNotBlank(roadCode) and CommonUtil.isNotBlank(sectionCode):
                # 大广高速
                if sectionCode == indexSectionCode:
                    sectionsQueryList.append(sectionCode)
                    indexRoadCodeMap[sectionCode] = roadCode

        sectionCodeList: List[str] = []
        sectionCodeList.append(indexSectionCode)

        # -------可疑车辆存储时间
        now = datetime.now()
        formattedDate = now.strftime("%Y%m%d")

        # -------获取当前时间的前2天
        currentDate = datetime.now()
        # 【Java→Python】Calendar.getInstance() + add(DAY_OF_MONTH, -starTime) → 时间运算
        twoDaysAgo = currentDate - timedelta(days=starTime)
        queryDate = twoDaysAgo.strftime("%Y-%m-%d")

        queryStartTime = queryDate + " 00:00:00"
        queryEndTime = queryDate + " 23:59:59"
        log.info("查询时间范围" + queryStartTime + "到" + queryEndTime)

        # 门架抓拍流水
        snapshotFlow = OdsRtSzdnSnapshotFlowAddcode()
        snapshotFlow.setPlatecolor("黄色")
        snapshotFlow.setSectionList(sectionCodeList)
        snapshotFlow.setApplyTime1(queryStartTime)
        snapshotFlow.setApplyTime2(queryEndTime)

        # 门架交易流水
        feeRecords01 = OdsLwzxsfsjFeeRecords01()
        feeRecords01.setPlateColor("_1")
        feeRecords01.setSectionList(sectionCodeList)
        feeRecords01.setInApplyTime1(queryStartTime)
        feeRecords01.setInApplyTime2(queryEndTime)

        # 是否不是节假日
        isNotExitsjholidayFlag = True
        if jholidayTimeValue.find(queryDate) > -1:
            isNotExitsjholidayFlag = False

        for i in range(startNum, endNum + 1):
            # ----- 分页范围 ： 2000一次性查询
            carParaVO.setStartNum(pageSize)
            if i > 1:
                endRange = (i - 1) * pageSize  # 当前页 -1
                carParaVO.setEndNum(endRange)

            # 查询门架抓拍流水
            snapshotFlow.setStartNum(carParaVO.getStartNum())
            snapshotFlow.setEndNum(carParaVO.getEndNum())
            self.syncSnapshotFlow(snapshotFlow)

            # 门架交易流水
            feeRecords01.setStartNum(carParaVO.getStartNum())
            feeRecords01.setEndNum(carParaVO.getEndNum())
            self.syncFeeRecords(feeRecords01)

            # -------------轨迹点6000一次查询
            pageSizeNew = 6000
            carParaVO.setStartNum(pageSizeNew)
            if i > 1:
                endRange = (i - 1) * pageSizeNew  # 当前页 -1
                carParaVO.setEndNum(endRange)

            carParaVO.setApplyTime1(queryStartTime)
            carParaVO.setApplyTime2(queryEndTime)
            log.info("轨迹点SQL开始查询----------" + _javaDateToString(datetime.now()))
            carlistAll = self.zdataTrailTracksService.getLatestTrail(carParaVO)
            log.info("轨迹点SQL结束查询----------" + _javaDateToString(datetime.now())
                     + "--数据：" + _javaStr(len(carlistAll)))

            # ---------------------------------- 跨省全程屏蔽
            carlistQspb: List[ZdataTrailTracks] = []
            # ---------------------------------- 关注路段屏蔽
            carlistLdpb: List[ZdataTrailTracks] = []

            for zdataTrailTracksVo in carlistAll:
                trailtype = CommonUtil.isNull(zdataTrailTracksVo.getTrailtype())

                firstCode = CommonUtil.isNull(zdataTrailTracksVo.getEntollstationid())  # 入口收费站编号
                firstName = CommonUtil.repalaceSzdnTollName(
                    zdataTrailTracksVo.getEntollstationname())  # 入口收费站名称
                endCode = CommonUtil.isNull(zdataTrailTracksVo.getExtollstationid())  # 出口收费站编号
                endName = CommonUtil.repalaceSzdnTollName(
                    zdataTrailTracksVo.getExtollstationname())  # 出口收费站名称

                carNo = CommonUtil.isNull(zdataTrailTracksVo.getPlateKey())

                # 外省进 外省出的车
                if (trailtype == "0" and firstName.find("门架") > -1
                        and endName.find("门架") > -1):
                    if isNotExitsjholidayFlag:
                        carlistQspb.append(zdataTrailTracksVo)
                else:
                    # 判断是否包含大广路段
                    keyValue = zdataTrailTracksVo.getTrailPoints()  # 行驶轨迹
                    if CommonUtil.isNotBlank(keyValue):
                        exflag = False
                        for sectionCodeValue in sectionsQueryList:
                            if keyValue.find(sectionCodeValue) > -1:
                                exflag = True
                        if exflag:
                            if isNotExitsjholidayFlag:
                                carlistLdpb.append(zdataTrailTracksVo)
                            trailTracksVo = TrailTracksVo()
                            trailTracksVo.setPlateKey(carNo)
                            trailTracksVo.setEnterTime(zdataTrailTracksVo.getEnterTime())
                            trailTracksVo.setExitTime(zdataTrailTracksVo.getExitTime())

                            # 按照车牌存放当天轨迹
                            keyList: List[TrailTracksVo] = []

                            trailFittingRedisKey = self.trailFittingKey(formattedDate, carNo)
                            oldFittingList = self.redisCache.getCacheObject(trailFittingRedisKey)
                            if oldFittingList is not None and len(oldFittingList) > 0:
                                keyList = oldFittingList
                            keyList.append(trailTracksVo)

                            self.redisCache.setCacheObject(trailFittingRedisKey, keyList)

            # ---------------------------------- 跨省全程屏蔽
            if carlistQspb is not None and len(carlistQspb) > 0:
                for tracks in carlistQspb:
                    carNo = CommonUtil.isNull(tracks.getPlateKey())
                    keyValue = tracks.getTrailPoints()  # 行驶轨迹
                    escapedType = ""
                    josnList: List[TrailBo] = []
                    if CommonUtil.isNotBlank(keyValue):
                        josnList = self.getTrailBoList(keyValue)
                        tracks.setTrailPoints("")  # 行驶轨迹
                        # ---------------------------分析场景: 门架抓拍和流水抓拍 占比
                        conutGantryCapture = 0
                        conutFeeRecord = 0
                        for rtnTrailBo in josnList:
                            stateType = CommonUtil.isNull(rtnTrailBo.getStateType())
                            if stateType == self.GANTRY_CAPTURE:
                                # 门架抓拍
                                conutGantryCapture += 1
                            elif stateType == self.FeeRecord:
                                # 卡口流水
                                conutFeeRecord += 1

                        # ---------------屏蔽:
                        if conutGantryCapture > supoerMjnum:
                            escapedTypeRemark = ""
                            addFlag = False
                            if conutFeeRecord == 0:
                                escapedTypeRemark = ("跨省全程屏蔽：其中门架牌识流水数量:"
                                                     + _javaStr(conutGantryCapture)
                                                     + "，门架交易流水数量:"
                                                     + _javaStr(conutFeeRecord) + "。")
                                addFlag = True
                            if addFlag:
                                escapedType = Constants.escapedType_20
                                tracks.setEscapedType(escapedType)  # 屏蔽
                                tracks.setEscapedTypeRemark(escapedTypeRemark)
                                tracks.setEscapedTfcj("1")  # 逃费场景

                                trailInfo = self.changeData(tracks, josnList)  # 获取设备的经纬度

                                # 判断门架抓拍是否经过了虚拟门架
                                if self.getIsVirtualFlag(trailInfo.getTrailList()):
                                    # 车牌颜色
                                    tracks.setPlateColor(
                                        self.getPlateColor(trailInfo.getTrailList()))
                                    trailInfo.setTrailUuid(carNo)

                                    key = self.getSuspiciousKey(formattedDate, carNo)
                                    self.redisCache.setCacheObject(key, trailInfo)

            # ---------------------------------- 关注路段屏蔽
            if carlistLdpb is not None and len(carlistLdpb) > 0:
                for tracks in carlistLdpb:
                    carNo = CommonUtil.isNull(tracks.getPlateKey())
                    keyValue = tracks.getTrailPoints()  # 行驶轨迹
                    escapedType = ""
                    josnList: List[TrailBo] = []
                    if CommonUtil.isNotBlank(keyValue):
                        josnList = self.getTrailBoList(keyValue)
                        tracks.setTrailPoints("")  # 行驶轨迹

                        # ---------------------------分析场景: 路段抓拍和流水抓拍 占比
                        conutGantryCapture = 0
                        conutFeeRecord = 0

                        for rtnTrailBo in josnList:
                            sectionCode = CommonUtil.isNull(rtnTrailBo.getSectionCode())  # 路段信息
                            stateType = CommonUtil.isNull(rtnTrailBo.getStateType())
                            # 原文此处还有一段 locationCode/devLocatCode 的注释代码
                            # （locationMap 查询），保留不实现。

                            if CommonUtil.isNotBlank(sectionCode):
                                if sectionCode in indexRoadCodeMap:
                                    if stateType == self.GANTRY_CAPTURE:
                                        # 门架抓拍
                                        conutGantryCapture += 1
                                        # 原文此处还有"是否虚拟门架"的判断，整块被注释
                                    elif stateType == self.FeeRecord:
                                        # 卡口流水
                                        conutFeeRecord += 1
                        # 该路段门架比例一定的数值
                        # conutGantryCapture > 0 && conutGantryCapture > conutFeeRecord
                        if conutGantryCapture > roadSupoerMjnum:
                            # BigDecimal costBite = new BigDecimal(conutFeeRecord)
                            #     .divide(new BigDecimal(conutGantryCapture), 4, ROUND_HALF_UP);
                            escapedTypeRemark = ""
                            addFlag = False
                            if conutFeeRecord == 0:
                                escapedTypeRemark = (indexSectionName + "全程屏蔽：其中门架牌识流水数量:"
                                                     + _javaStr(conutGantryCapture)
                                                     + "，门架交易流水数量:"
                                                     + _javaStr(conutFeeRecord) + "。")
                                addFlag = True
                            # 原文此处还有 else 分支的"部分屏蔽"判断（使用 bite/costBite），
                            # 整块被注释 → 当前只判定"全程屏蔽"。

                            if addFlag:
                                escapedType = Constants.escapedType_20
                                tracks.setEscapedType(escapedType)  # 屏蔽
                                tracks.setEscapedTypeRemark(escapedTypeRemark)
                                tracks.setEscapedTfcj("2")  # 路段屏蔽

                                trailInfo = self.changeData(tracks, josnList)  # 获取设备的经纬度

                                # 判断门架抓拍是否经过了虚拟门架
                                if self.getIsVirtualFlag(trailInfo.getTrailList()):
                                    # 车牌颜色
                                    tracks.setPlateColor(
                                        self.getPlateColor(trailInfo.getTrailList()))
                                    trailInfo.setTrailUuid(carNo)

                                    key = self.getSuspiciousKey(formattedDate, carNo)
                                    self.redisCache.setCacheObject(key, trailInfo)

    # ==================================================================
    # Java L1644-L1893：同步可疑车辆（新版：拟合/未拟合轨迹 + 门架流水比对）
    # ==================================================================
    def syncSuspiciousCarQutazNew(self, startNum: int, endNum: int) -> None:
        """新版可疑车同步：同时拉"有拟合轨迹"和"无拟合轨迹"，再用门架流水校验屏蔽。

        【Java→Python 关键差异】
        1) 原 Java 里从 Redis 取 `redisTimeKey`/`supoer_mjnum` 的配置读取**整块被注释**，
           节假日起初也被硬编码为 "2025-01-01,2025-01-02,2025-01-03"（原样保留）。
        2) `SimpleDateFormat("yyyy-MM-dd HH:mm:ss").parse(queryStartTime)` → `strptime`；
           解析失败时 Java 只打印堆栈并保留 `twoDaysAgo`，Python 同样 `except` 后继续。
        3) 【忠实保留的缺陷】`queryStartDate` 在**每轮分页内**会被轨迹的 enterTime 逐步提前
           （`if (queryStartDate.getTime() > enterTime.getTime()) queryStartDate = enterTime;`），
           最终作为门架流水的 `inApplyTime1`；注意每轮 `i` 都会重置回 `twoDaysAgo`。
        4) `List#subList(from, to)` → Python 切片（新列表，非视图）；`Math.min` → 内置 `min`。
        5) `StringUtils.getUUID()` 是静态工具方法 → `StringUtils.getUUID()`。
        6) `JSON.parseArray(String, Class)` → 替身返回 JSONArray（list 子类，元素为 TrailBo）。
        7) `List` 变量名 `list`/`feeRecords01List` 在 Python 里用 `list_`/`feeRecords01List`
           （`list` 是内置类型名，遮蔽它会让同作用域的 `list(...)` 调用出错）。
        """
        pageSize = 10
        starTime = 2
        endTime = 4

        supoerMjnum = 5  # 跨省：同步可疑车辆门架抓拍数量5个以上

        # -------------- 从缓存取得对应的配置（原 Java 整块被注释，保留说明）
        # String redisTimeValue = redisCache.getCacheObject(redisTimeKey); // 默认2天
        # if (CommonUtil.isNotBlank(redisTimeValue)) { starTime = Integer.parseInt(...); }
        # String supoerMjnumValue = redisCache.getCacheObject(supoer_mjnum); // 比例默认为5
        # if (CommonUtil.isNotBlank(supoerMjnumValue)) { supoerMjnum = Integer.parseInt(...); }

        # 判断节假日（原文硬编码，未从 Redis 取）
        jholidayTimeValue = "2025-01-01,2025-01-02,2025-01-03"  # 节假日

        if CommonUtil.isNull(self.isLocalhost) == "local":
            log.info("本地配置------：" + CommonUtil.isNull(self.isLocalhost))
            # 本地  分页1000条 30 到 1 天
            pageSize = 6000
            endTime = starTime * 2
        else:
            log.info("生产配置------：" + CommonUtil.isNull(self.isLocalhost))
            # 生产------------- 分页1000条 14 到 7 天
            pageSize = 6000
            endTime = starTime * 2

        carParaVO = CarParaVO()
        # ----------7 到 14天
        carParaVO.setStarTime(starTime)
        carParaVO.setEndTime(endTime)

        # 门架
        gantryList = self.odsSzdnGantryService.getGantryRedis()
        gantryMao: dict[str, OdsSzdnGantry] = {}
        for rtnOdsSzdnGantry in gantryList:
            gantryMao[CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode())] = rtnOdsSzdnGantry

        # 位置信息
        locationMap: dict[str, ZdataLocationDict] = self.zdataLocationDictService.getRedisList()

        # 根据路段查询路线map（原文计算后未使用，保留）
        sectionMap: dict[str, OdsSzdnSection] = self.sectionService.getSectionMap()

        # -------可疑车辆存储时间
        now = datetime.now()
        formattedDate = now.strftime("%Y%m%d")

        # -------获取当前时间的前2天
        currentDate = datetime.now()
        twoDaysAgo = currentDate - timedelta(days=starTime)
        queryDate = twoDaysAgo.strftime("%Y-%m-%d")

        queryStartTime = queryDate + " 00:00:00"
        queryEndTime = queryDate + " 23:59:59"
        log.info("查询时间范围" + queryStartTime + "到" + queryEndTime)

        # 是否不是节假日
        isNotExitsjholidayFlag = True
        if jholidayTimeValue.find(queryDate) > -1:
            isNotExitsjholidayFlag = False

        for i in range(startNum, endNum + 1):
            # 【Java→Python】循环内重新创建 SimpleDateFormat 只影响性能，Python 无需等价物
            queryStartDate = twoDaysAgo
            try:
                queryStartDate = _parseDateTime(queryStartTime)
            except Exception as e:
                # Java: e.printStackTrace(); log.error("日期解析错误！" + queryStartTime);
                traceback.print_exc()
                log.error("日期解析错误！" + queryStartTime)

            # ----- 分页范围 ： 2000一次性查询
            carParaVO.setStartNum(pageSize)
            if i > 1:
                endRange = (i - 1) * pageSize  # 当前页 -1
                carParaVO.setEndNum(endRange)

            carParaVO.setApplyTime1(queryStartTime)
            carParaVO.setApplyTime2(queryEndTime)

            carlistAll: List[ZdataTrailTracks] = []

            if isNotExitsjholidayFlag:
                # --------- 有拟合轨迹的
                log.info("轨迹点开始------" + _javaDateToString(datetime.now())
                         + "分页配置：" + _javaStr(carParaVO.getStartNum())
                         + "到" + _javaStr(carParaVO.getEndNum()))
                carlistFittinglist = self.zdataTrailTracksService.getLatestTrail(carParaVO)
                log.info("轨迹点结束-----" + _javaDateToString(datetime.now())
                         + "--数据：" + _javaStr(len(carlistFittinglist)))
                for zdataTrailTracksVo in carlistFittinglist:
                    zdataTrailTracksVo.setFlag("1")  # 有的轨迹点
                    carlistAll.append(zdataTrailTracksVo)

                # -------------沒有拟合轨迹的  4000一次查询
                pageSizeNew = 4000
                carParaVO.setStartNum(pageSizeNew)
                if i > 1:
                    endRange = (i - 1) * pageSizeNew  # 当前页 -1
                    carParaVO.setEndNum(endRange)
                log.info("不存在轨迹点开始---" + _javaDateToString(datetime.now())
                         + "分页配置：" + _javaStr(carParaVO.getStartNum())
                         + "到" + _javaStr(carParaVO.getEndNum()))
                carUnFittingList = self.zdataTrailTracksService.getUnFitting(carParaVO)
                log.info("不存在轨迹点结束----" + _javaDateToString(datetime.now())
                         + "--数据：" + _javaStr(len(carUnFittingList)))
                for zdataTrailTracksVo in carUnFittingList:
                    zdataTrailTracksVo.setUuid(StringUtils.getUUID())
                    zdataTrailTracksVo.setFlag("0")  # 沒有的轨迹点
                    carlistAll.append(zdataTrailTracksVo)

            feeRecordsUuidList: List[str] = []  # 门架流水轨迹点

            # 符合业务的轨迹点
            carlistRtn: List[ZdataTrailTracks] = []
            feeRecords01Map: dict[str, OdsLwzxsfsjFeeRecords01] = {}

            for tracks in carlistAll:
                uuid = CommonUtil.isNull(tracks.getUuid())  # 轨迹点id（原文未使用，保留）
                keyValue = tracks.getTrailPoints()  # 行驶轨迹
                josnList: List[TrailBo] = []
                if CommonUtil.isNotBlank(keyValue):
                    enterTime = tracks.getEnterTime()
                    if enterTime is not None:
                        # 如果指定的时间 大于 轨迹开始时间的话
                        if _epochMillis(queryStartDate) > _epochMillis(enterTime):
                            queryStartDate = enterTime
                    josnList = self.getTrailBoList(keyValue)
                    tracks.setTrailPoints(JSON.toJSONString(josnList))
                    isNotXymjFlag = True  # 是否不包含虚拟门架
                    conutGantryCapture = 0
                    for trailBo in josnList:
                        locationCode = CommonUtil.isNull(trailBo.getLocationCode())  # 设备IP地址
                        stateType = CommonUtil.isNull(trailBo.getStateType())  # 流水来源类型标识
                        if stateType == self.GANTRY_CAPTURE:
                            # 门架抓拍
                            conutGantryCapture += 1
                            if CommonUtil.isNotBlank(locationCode):
                                if locationCode in locationMap:
                                    devLocatCode = CommonUtil.isNull(
                                        locationMap[locationCode].getStandardCode())  # 收费站/门架code
                                    # 判断是否是虚拟门架---------
                                    if CommonUtil.isNotBlank(devLocatCode):
                                        # 找到门架信息
                                        if devLocatCode in gantryMao:
                                            gantry = gantryMao[devLocatCode]
                                            if CommonUtil.isNull(gantry.getIsVirtual()) == "1":
                                                isNotXymjFlag = False

                    # 门架抓拍数量 > 5 并且没有经过虚拟门架
                    if conutGantryCapture > supoerMjnum and isNotXymjFlag:
                        for trailBo in josnList:
                            stateType = CommonUtil.isNull(trailBo.getStateType())
                            pointUuid = CommonUtil.isNull(trailBo.getPointUuid())
                            if stateType == self.FeeRecord:
                                if CommonUtil.isNotBlank(pointUuid):
                                    feeRecordsUuidList.append(pointUuid)
                        carlistRtn.append(tracks)

            feeRecords01 = OdsLwzxsfsjFeeRecords01()
            feeRecords01.setInApplyTime1(_formatDateTime(queryStartDate))
            feeRecords01.setInApplyTime2(queryEndTime)

            if len(feeRecordsUuidList) > 0:
                batchSize = 2000
                if len(feeRecordsUuidList) <= batchSize:
                    # 小于1000，
                    feeRecords01.setCidList(feeRecordsUuidList)
                    feeRecords01List = self.queryFeeRecords01List(feeRecords01)  # 查询数据
                    for rtnFeeRecords01 in feeRecords01List:
                        feeRecords01Map[CommonUtil.isNull(rtnFeeRecords01.getCid())] = rtnFeeRecords01
                else:
                    for yy in range(0, len(feeRecordsUuidList), batchSize):
                        subList = feeRecordsUuidList[yy:min(yy + batchSize, len(feeRecordsUuidList))]
                        # 处理subList，例如保存到数据库或进行其他操作
                        feeRecords01.setCidList(subList)
                        feeRecords01List = self.queryFeeRecords01List(feeRecords01)  # 查询数据
                        for rtnFeeRecords01 in feeRecords01List:
                            feeRecords01Map[CommonUtil.isNull(rtnFeeRecords01.getCid())] = (
                                rtnFeeRecords01)

            # 生成可疑车辆
            self.separateUnfiitingList(carlistRtn, feeRecords01Map)

            # 执行完了 还原
            carlistRtn = []
            feeRecords01Map = {}

    # ------------------------------------------------------------------
    def queryFeeRecords01List(
            self, feeRecords01: OdsLwzxsfsjFeeRecords01) -> List[OdsLwzxsfsjFeeRecords01]:
        """历史轨迹查询：按 cidList 批量查门架交易流水（Java 里是 private）。"""
        # log.info("门架流水开始------" + new Date() + "时间：" + feeRecords01.getInApplyTime1()
        #          + "到" + feeRecords01.getInApplyTime2() + " 轨迹点数量："
        #          + feeRecords01.getCidList().size());
        feeRecords01List = self.feeRecords01Service.selectOdsLwzxsfsjFeeRecords01ListNew(
            feeRecords01)
        log.info("门架流水结束----" + _javaDateToString(datetime.now())
                 + "--数据：" + _javaStr(len(feeRecords01List)))
        return feeRecords01List

    # ------------------------------------------------------------------
    def getIsVirtualFlag(self, trailList: Optional[List[TrailBo]]) -> bool:
        """判断是否有虚拟门架：任一"门架抓拍 + isVirtual == 1"即返回 False。"""
        isVirtualFlag = True
        if trailList is not None and len(trailList) > 0:
            for trailBo in trailList:
                stateType = CommonUtil.isNull(trailBo.getStateType())
                isVirtual = CommonUtil.isNull(trailBo.getIsVirtual())
                if stateType == self.GANTRY_CAPTURE and isVirtual == "1":
                    isVirtualFlag = False
        return isVirtualFlag

    # ------------------------------------------------------------------
    def getPlateColor(self, trailList: Optional[List[TrailBo]]) -> str:
        """获取车牌颜色：取**第一个**门架抓拍点的车牌颜色，取到就返回。

        【Java→Python】`countNum` 只在 stateType == GANTRY_CAPTURE 时自增，
        但由于取到就 return，实际等价于"第一个门架抓拍点"。
        """
        plateColor = ""
        if trailList is not None and len(trailList) > 0:
            countNum = 0
            for trailBo in trailList:
                stateType = CommonUtil.isNull(trailBo.getStateType())
                if stateType == self.GANTRY_CAPTURE:
                    # 查询第一个门架抓拍的车牌号
                    if countNum == 0:
                        changeTrailBo = self.getByTrailBo(trailBo)
                        if changeTrailBo is not None:
                            plateColor = CommonUtil.isNull(changeTrailBo.getPlatecolor())
                            return plateColor
                    countNum += 1
        return plateColor

    # ==================================================================
    # Java L1961-L1987：查询车辆历史记录
    # ==================================================================
    def carTrackQuery(self, carParaVO: CarParaVO) -> List[TrailInfo]:
        """历史轨迹查询：把轨迹点 JSON 转成 TrailInfo（含设备经纬度补全）。

        【Java→Python】`carlistPara.stream().map(CarVO::getCarNo).collect(toList())`
        → 列表推导式（语义等价，顺序一致）。
        """
        carlistPara: List[CarVO] = carParaVO.getCarlist()
        if carlistPara is not None and len(carlistPara) > 0:
            carNoList = [carVO.getCarNo() for carVO in carlistPara]
            carParaVO.setCarNoList(carNoList)
        carlist = self.zdataTrailTracksService.getHistoryTrail(carParaVO)
        rtnList: List[TrailInfo] = []
        if carlist is not None and len(carlist) > 0:
            for tracks in carlist:
                carNo = CommonUtil.isNull(tracks.getPlateKey())
                keyValue = tracks.getTrailPoints()  # 行驶轨迹
                josnList: List[TrailBo] = []
                if CommonUtil.isNotBlank(keyValue):
                    josnList = self.getTrailBoList(keyValue)
                    # tracks.setTrailPoints("");  // 行驶轨迹（原文注释）

                    trailInfo = self.changeData(tracks, josnList)  # 获取设备的经纬度
                    trailInfo.setTrailUuid(carNo)
                    rtnList.append(trailInfo)
        return rtnList

    # ==================================================================
    # Java L1995-L2004：轨迹查询（界面）
    # ==================================================================
    def carTrackQueryNew(self, carParaVO: CarParaVO) -> List[ZdataTrailTracks]:
        """界面轨迹查询：直接返回轨迹点列表（不做 JSON 展开）。"""
        carlistPara: List[CarVO] = carParaVO.getCarlist()
        if carlistPara is not None and len(carlistPara) > 0:
            carNoList = [carVO.getCarNo() for carVO in carlistPara]
            carParaVO.setCarNoList(carNoList)
        list_ = self.zdataTrailTracksService.getHistoryTrail(carParaVO)

        return list_

    # ==================================================================
    # Java L2011-L2022：dws json 字符串转换
    # ==================================================================
    def getTrailBoListString(self, paraTrailPoints: Optional[str]) -> str:
        """把 dws 落库的"被二次转义"的 JSON 串还原成标准 JSON 数组文本。

        【Java→Python】`String#replace(CharSequence, CharSequence)` 是**字面量**替换
        （不是正则），与 Python `str.replace` 语义一致，可逐句直译。
        """
        trailPoints = CommonUtil.isNull(paraTrailPoints)
        if CommonUtil.isNotBlank(trailPoints):
            trailPoints = trailPoints.replace("\\", "")
            trailPoints = trailPoints.replace('{"{', "[{")
            trailPoints = trailPoints.replace('}"}', "}]")
            trailPoints = trailPoints.replace('","{', ",{")

            trailPoints = trailPoints.replace("ZdTrails:", "")
        return trailPoints

    # ==================================================================
    # Java L2030-L2084：转 json（手工逐字段赋值）
    # ==================================================================
    def getTrailBoList(self, paraTrailPoints: Optional[str]) -> List[TrailBo]:
        """轨迹点 JSON 文本 → `List<TrailBo>`，并做 4 分钟去重合并。

        【Java→Python 关键差异】
        1) `JSON.parseArray(text)` 返回 JSONArray；`for (Object o : array)` 里强转 JSONObject
           → 替身 JSONArray 的 `__iter__` 已把 dict 包装为 JSONObject，可直接 `getString`。
        2) 【忠实保留的缺陷】只有 `captureTime` 含 "T" 时才用
           `SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss")` 解析并**回写** captureTime；
           普通 `"yyyy-MM-dd HH:mm:ss"` 格式的时间会被**直接丢弃**（trailBo.captureTime 为 null）。
        3) `new BigDecimal(lon)` → `_bdFloat(lon)`（实体字段已映射为 float）。
        4) 末尾统一走 `mapTrailBoList` 做 4 分钟合并。
        """
        trailBoList: List[TrailBo] = []
        trailPoints = self.getTrailBoListString(paraTrailPoints)
        if CommonUtil.isNotBlank(trailPoints) and trailPoints != "{}":
            try:
                # 先转josn数组 然后循环 一个一个手动赋值
                array: JSONArray = JSON.parseArray(trailPoints)
                # SimpleDateFormat format1 = "yyyy-MM-dd'T'HH:mm:ss"
                # SimpleDateFormat format2 = "yyyy-MM-dd HH:mm:ss"
                for o in array:
                    jsonObj: JSONObject = o
                    captureTime = jsonObj.getString("captureTime")
                    stateType = jsonObj.getString("stateType")
                    platenumber = jsonObj.getString("platenumber")
                    locationId = jsonObj.getString("locationId")
                    locationCode = jsonObj.getString("locationCode")
                    pointUuid = jsonObj.getString("pointUuid")
                    sectionCode = jsonObj.getString("sectionCode")
                    orgCode = jsonObj.getString("orgCode")
                    pileNo = jsonObj.getString("pileNo")
                    lon = jsonObj.getString("lon")
                    lat = jsonObj.getString("lat")
                    trailBo = TrailBo()
                    captureTime = CommonUtil.isNull(captureTime)
                    if captureTime.find("T") > -1:
                        dateTime = datetime.strptime(captureTime, "%Y-%m-%dT%H:%M:%S")
                        # 步骤2：使用DateTimeFormatter转字符串
                        formattedDateStr = dateTime.strftime("%Y-%m-%d %H:%M:%S")
                        trailBo.setCaptureTime(formattedDateStr)
                    trailBo.setStateType(stateType)
                    trailBo.setPlatenumber(platenumber)
                    trailBo.setLocationId(locationId)
                    trailBo.setLocationCode(locationCode)
                    trailBo.setPointUuid(pointUuid)
                    trailBo.setSectionCode(sectionCode)
                    trailBo.setOrgCode(orgCode)
                    trailBo.setPileno(pileNo)
                    if CommonUtil.isNotBlank(lon):
                        trailBo.setLon(_bdFloat(lon))
                    if CommonUtil.isNotBlank(lat):
                        trailBo.setLat(_bdFloat(lat))
                    trailBoList.append(trailBo)
            except Exception as e:
                # Java: catch (Exception e) { e.printStackTrace(); log.error("解析错误！" + trailPoints); }
                traceback.print_exc()
                log.error("解析错误！" + trailPoints)
        rtnList = self.mapTrailBoList(trailBoList)

        return rtnList

    # ==================================================================
    # Java L2092-L2152：合并门架抓拍和收费站抓拍流水（4 分钟去重）
    # ==================================================================
    def mapTrailBoList(self, trailBoList: Optional[List[TrailBo]]) -> List[TrailBo]:
        """按 `stateType + locationCode` 分组，4 分钟内的重合点合并图片。

        【Java→Python 关键差异】
        1) `Map<String, TrailBo> map` → `dict`；**存的是引用**，所以对 map 里对象的
           `setImagesArry` 修改会直接作用到已放入 mapList 的对象（与 Java 一致）。
        2) `Math.abs(d2.getTime() - d1.getTime())` → `abs(_epochMillis(d2) - _epochMillis(d1))`。
        3) `SimpleDateFormat#parse` 的 ParseException → `ValueError`，同样 catch 后
           把当前点加入结果并打日志。
        4) 只有门架抓拍/收费站抓拍会写入 map（供后续比较），其余类型只进 mapList。
        """
        mapList: List[TrailBo] = []

        # 按照时间排序----------（原文整块被注释，保留说明）
        # if (null != trailBoList && trailBoList.size() > 0) { trailBoList = ...sorted(...); }

        # 去掉重合的
        threeMinutesInMillis = 4 * 60 * 1000  # 三分钟转换为毫秒（原文变量名如此，实际为 4 分钟）

        map_: dict[str, TrailBo] = {}
        if trailBoList is not None and len(trailBoList) > 0:
            for trailBo in trailBoList:
                stateType = CommonUtil.isNull(trailBo.getStateType())  # 类型
                locationCode = CommonUtil.isNull(trailBo.getLocationCode())  # 设备IP地址
                captureTime = CommonUtil.isNull(trailBo.getCaptureTime())  # 抓拍时间
                imagesArry = CommonUtil.deleteEnd(trailBo.getImagesArry())  # 抓拍图片
                mapKey = stateType + locationCode
                if mapKey in map_:
                    trailBoTemp = map_[mapKey]
                    captureTimeTemp = CommonUtil.isNull(trailBoTemp.getCaptureTime())
                    if CommonUtil.isNotBlank(captureTime) and CommonUtil.isNotBlank(
                            captureTimeTemp):
                        try:
                            captureTimeDate1 = _parseDateTime(captureTime)
                            captureTimeDate2 = _parseDateTime(captureTimeTemp)
                            diff = abs(_epochMillis(captureTimeDate2)
                                       - _epochMillis(captureTimeDate1))
                            if diff > threeMinutesInMillis:
                                mapList.append(trailBo)
                            else:
                                # 抓拍图片累加--------------
                                imagesArryTemp = CommonUtil.deleteEnd(
                                    trailBoTemp.getImagesArry())
                                if imagesArry != "":
                                    if imagesArryTemp == "":
                                        trailBoTemp.setImagesArry(imagesArry)
                                    else:
                                        trailBoTemp.setImagesArry(imagesArryTemp + ","
                                                                  + imagesArry)
                        except Exception as e:
                            mapList.append(trailBo)
                            log.info("日期解析失败------------" + str(e))
                    else:
                        mapList.append(trailBo)
                else:
                    mapList.append(trailBo)

                if stateType == self.GANTRY_CAPTURE or stateType == self.STATION_CAPTURE:
                    map_[mapKey] = trailBo
        return mapList

    # ==================================================================
    # Java L2161-L2183：把门架抓拍流水按"路段@@车牌"分组写入 Redis
    # ==================================================================
    def syncSnapshotFlow(self, snapshotFlow: OdsRtSzdnSnapshotFlowAddcode) -> None:
        """查询门架抓拍流水并写 Redis（key = snapshotFlowList + yyyyMMdd + ":" + 路段@@车牌）。

        【Java→Python】`List` 局部变量名是 `list`，Python 里改名为 `list_`，
        避免遮蔽内置 `list` 类型（同作用域后面若调用 `list(...)` 会报 TypeError）。
        """
        log.info("门架抓拍流水SQL开始查询----------" + _javaDateToString(datetime.now()))
        now = datetime.now()
        redisDate = now.strftime("%Y%m%d")
        # ----- 分页范围
        list_ = self.snapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeListNew(
            snapshotFlow)
        log.info("门架抓拍流水SQL结束查询----------" + _javaDateToString(datetime.now())
                 + "--数据：" + _javaStr(len(list_)))
        for snapshotFlowAddcode in list_:
            if (CommonUtil.isNotBlank(snapshotFlowAddcode.getPlatenumber())
                    and snapshotFlowAddcode.getSnapshottime() is not None):
                keyList: List[OdsRtSzdnSnapshotFlowAddcode] = []
                # 按照路段和车牌
                key = (CommonUtil.isNull(snapshotFlowAddcode.getSectioncode()) + "@@"
                       + CommonUtil.isNull(snapshotFlowAddcode.getPlatenumber()))
                redisKey = self.snapshotFlowListKey(redisDate, key)
                oldList = self.redisCache.getCacheObject(redisKey)
                if oldList is not None and len(oldList) > 0:
                    keyList = oldList
                keyList.append(snapshotFlowAddcode)
                self.redisCache.setCacheObject(redisKey, keyList)

    # ==================================================================
    # Java L2192-L2220：把门架交易流水按"路段@@车牌"分组写入 Redis
    # ==================================================================
    def syncFeeRecords(self, feeRecords: OdsLwzxsfsjFeeRecords01) -> None:
        """查询门架交易流水并写 Redis。

        【Java→Python】`vehicleplate.split("_")` 是**正则** split 且丢弃尾部空串，
        故用 `StringUtils._java_split("_", text)`；若 `vehicleplate` 只有 "_"，
        Java 得到长度 0 的数组、`[0]` 抛 ArrayIndexOutOfBoundsException，
        Python 侧 `_java_split` 返回 []、`[0]` 抛 IndexError（等价）。
        """
        log.info("门架交易流水SQL开始查询----------" + _javaDateToString(datetime.now()))
        now = datetime.now()
        redisDate = now.strftime("%Y%m%d")
        # ----- 分页范围
        feeRecords.setOrderByFlag("order")
        list_ = self.feeRecords01Service.selectOdsLwzxsfsjFeeRecords01ListNew(feeRecords)
        log.info("门架交易流水SQL开始查询----------" + _javaDateToString(datetime.now())
                 + "数据--" + _javaStr(len(list_)))
        for feeRecords01 in list_:
            vehicleplate = CommonUtil.isNull(feeRecords01.getVehicleplate())  # 车牌号_颜色
            if vehicleplate.find("_") > -1:
                vehicleplateStr = _java_split("_", vehicleplate)
                vehicleplateChange = CommonUtil.isNull(vehicleplateStr[0])
                if CommonUtil.isNotBlank(vehicleplateChange):
                    # 按照路段和车牌
                    keyList: List[OdsLwzxsfsjFeeRecords01] = []
                    key = (CommonUtil.isNull(feeRecords01.getSectioncode()) + "@@"
                           + CommonUtil.isNull(vehicleplateChange))
                    redisKey = self.feeRecordsListKey(redisDate, key)
                    oldList = self.redisCache.getCacheObject(redisKey)
                    if oldList is not None and len(oldList) > 0:
                        keyList = oldList
                    keyList.append(feeRecords01)
                    self.redisCache.setCacheObject(redisKey, keyList)

    # ==================================================================
    # Java L2226-L2299：门架抓拍流水与门架交易流水比对（按 1 小时分组）
    # ==================================================================
    def separateSnapshotFlowTimeList(self) -> None:
        """把当天所有门架抓拍流水按"1 小时内为同一组"切分，再逐组查是否有交易流水。

        【Java→Python 关键差异】
        1) `Collection<String> keys = redisCache.keys(pattern)` → 替身返回 `set`
           （与 Java `Set<String>` 一样无序）；判空用 `is not None and len(...) > 0`。
        2) `stream().sorted(comparing(X::getSnapshottime))` → `list.sort(key=...)`（原地排序）。
           【注意】Java 的 Comparator 遇到 null 会抛 NPE，这里同样不兜底（让 TypeError 冒泡）。
        3) `long thirtyMinutesInMillis = 60 * 60 * 1000;` —— 变量名写"30 分钟"，
           实际是 **1 小时**（原样保留）。
        4) 方法末尾会**删除**当天的 3 类 Redis key（snapshotFlowList / feeRecordsList /
           trailFittingList），删除后数据不可恢复（原逻辑如此）。
        """
        now = datetime.now()
        redisDate = now.strftime("%Y%m%d")

        roadSupoerMjnum = 3  # 路段：门架抓拍数量和门架流水数量对比
        roadSupoeMjnumValue = self.redisCache.getCacheObject(self.road_supoer_mjnum)  # 比例默认为3
        if CommonUtil.isNotBlank(roadSupoeMjnumValue):
            roadSupoerMjnum = int(roadSupoeMjnumValue)
            log.info("从缓存路段：取得门架抓拍数量------：" + _javaStr(roadSupoeMjnumValue))

        thirtyMinutesInMillis = 60 * 60 * 1000  # 30分钟转换为毫秒（实为 1 小时）

        keys = self.redisCache.keys(Constants.snapshotFlowList + redisDate + "*")
        if keys is not None and len(keys) > 0:
            for key in keys:
                keyList = self.redisCache.getCacheObject(key)
                if keyList is not None and len(keyList) >= roadSupoerMjnum:
                    # 按照车辆时间排序
                    # 【Java→Python】Comparator.comparing(getSnapshottime) → sort(key=)
                    keyList.sort(key=lambda item: item.getSnapshottime())

                    # 判断有几次通行
                    snapshotList: List[OdsRtSzdnSnapshotFlowAddcode] = []
                    for i in range(len(keyList)):
                        rtndata = keyList[i]
                        if i == 0:
                            snapshotList.append(rtndata)
                        else:
                            # 时间相差1个小时之内为同一组
                            preSnapshottime = keyList[i - 1].getSnapshottime()
                            snapshottime = rtndata.getSnapshottime()

                            diff = abs(_epochMillis(snapshottime)
                                       - _epochMillis(preSnapshottime))
                            if diff > thirtyMinutesInMillis:
                                # 超过了60分钟
                                self.isFeeRecordsExist(key, snapshotList, roadSupoerMjnum,
                                                       redisDate)

                                # 重新计算---------------
                                snapshotList = []
                                snapshotList.append(rtndata)
                            else:
                                snapshotList.append(rtndata)
                    self.isFeeRecordsExist(key, snapshotList, roadSupoerMjnum, redisDate)

        # 删除redis
        if keys is not None and len(keys) > 0:
            self.redisCache.deleteObject(keys)

        freeKeys = self.redisCache.keys(Constants.feeRecordsList + redisDate + "*")
        if freeKeys is not None and len(freeKeys) > 0:
            # 删除redis
            self.redisCache.deleteObject(freeKeys)

        trailFittingKeys = self.redisCache.keys(Constants.trailFittingList + redisDate + "*")
        if trailFittingKeys is not None and len(trailFittingKeys) > 0:
            # 删除redis
            self.redisCache.deleteObject(trailFittingKeys)

    # ==================================================================
    # Java L2307-L2531：对比找到可疑车辆（路段全程屏蔽，逃费场景 3）
    # ==================================================================
    def isFeeRecordsExist(self, key: str, snapshotList: List[OdsRtSzdnSnapshotFlowAddcode],
                          roadSupoerMjnum: int, redisDate: str) -> None:
        """判断一组门架抓拍流水是否存在对应交易流水；无流水则生成可疑车辆写入 Redis。

        【Java→Python 关键差异】
        1) `key.split(":")` 是正则 split（丢弃尾部空串）→ `_java_split(":", key)`。
           Redis key 形如 `js_car_snapshot20260601:200R500450649000@@赣A12345`，
           取 `[1]` 得到"路段@@车牌"，与 `feeRecordsListKey` 的存储格式对应。
        2) `snapshotList.get(snapshotList.size() - 1)` → `snapshotList[len(snapshotList) - 1]`。
        3) `getTime()` 比较 → `_epochMillis(...)` 得到 int 毫秒再比大小，避免
           Python datetime 与 int 混比。
        4) `new BigDecimal(x)` 校验 + `fee.compareTo(BigDecimal.ZERO) > 0`
           → `_bd(fee).compareTo(BigDecimal.ZERO) > 0`（fee 在实体里是 float）。
        5) `redisCache.getCacheObject(kykey) == null` 判"是否已存在"
           → `isExistObj is None`（替身在 key 不存在时返回 None）。
        6) 方法体内 `stateType` 恒为 `GANTRY_CAPTURE`（原文如此）。
        """
        if (CommonUtil.isNotBlank(key) and snapshotList is not None
                and len(snapshotList) >= roadSupoerMjnum and len(snapshotList) >= 2):
            roadCarKeyStr = _java_split(":", key)

            # 门架----------
            gantryList = self.odsSzdnGantryService.getGantryRedis()
            gantryMao: dict[str, OdsSzdnGantry] = {}
            for rtnOdsSzdnGantry in gantryList:
                gantryMao[CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode())] = rtnOdsSzdnGantry

            # 根据路段查询路线map
            sectionMap: dict[str, OdsSzdnSection] = self.sectionService.getSectionMap()

            stateType = self.GANTRY_CAPTURE  # 门架抓拍

            if len(roadCarKeyStr) > 1:
                firstBo = snapshotList[0]  # 第一个
                endBo = snapshotList[len(snapshotList) - 1]  # 最后一个

                startTime = firstBo.getSnapshottime()
                endTime = endBo.getSnapshottime()

                startTimeLong = _epochMillis(startTime)
                endTimeLong = _epochMillis(endTime)

                roadCarKey = roadCarKeyStr[1]
                sectionCode = CommonUtil.isNull(firstBo.getSectioncode())

                sectionName = ""
                roadCode = ""
                if sectionCode in sectionMap:
                    odsSzdnSection = sectionMap[sectionCode]
                    sectionName = odsSzdnSection.getSectionName()
                    roadCode = odsSzdnSection.getRoadCode()

                redisKey = self.feeRecordsListKey(redisDate, roadCarKey)
                isAddFlag = False
                oldList = self.redisCache.getCacheObject(redisKey)
                if oldList is not None and len(oldList) > 0:
                    freeCountNum = 0  # 计费模块响应计费结果 0 成功 1失败
                    for feeRecords01 in oldList:
                        transtime = feeRecords01.getTranstime()
                        if transtime is not None:
                            transtimelong = _epochMillis(transtime)
                            if startTimeLong <= transtimelong <= endTimeLong:
                                # 时间在范围里
                                fee = feeRecords01.getFee()
                                if (fee is not None
                                        and _bd(fee).compareTo(BigDecimal.ZERO) > 0):
                                    freeCountNum = freeCountNum + 1
                    if freeCountNum > 0:
                        # 有数据 后续做部分
                        pass
                    else:
                        isAddFlag = True
                else:
                    # 无数据------------
                    isAddFlag = True

                if isAddFlag:
                    carNo = firstBo.getPlatenumber()

                    trailFitting = 0  # 是否有轨迹点

                    # ------------ 判断是否有出入口轨迹
                    trailFittingRedisKey = self.trailFittingKey(redisDate, carNo)
                    oldFittingList = self.redisCache.getCacheObject(trailFittingRedisKey)
                    if oldFittingList is not None and len(oldFittingList) > 0:
                        for trailTracksVo in oldFittingList:
                            trailTtartTime = trailTracksVo.getEnterTime()  # 进入时间
                            trailEndTime = trailTracksVo.getExitTime()  # 离开时间
                            if trailTtartTime is not None and trailEndTime is not None:
                                if (_epochMillis(trailTtartTime) <= endTimeLong
                                        <= _epochMillis(trailEndTime)):
                                    trailFitting = trailFitting + 1

                    if trailFitting == 0:
                        platecolor = firstBo.getPlatecolor()

                        tracks = ZdataTrailTracks()
                        tracks.setUuid(StringUtils.getUUID())
                        tracks.setPlateKey(carNo)
                        # tracks.setEnvehicleid(carNo);
                        # tracks.setEnaxlecount(0);
                        tracks.setEnterTime(startTime)

                        startGantryid = CommonUtil.isNull(firstBo.getGantrycode())
                        tracks.setEntollstationid(startGantryid)
                        if startGantryid in gantryMao:
                            odsSzdnGantry = gantryMao[startGantryid]
                            tracks.setEntollstationname(odsSzdnGantry.getGantryName())  # 门架名称

                            if CommonUtil.isNotBlank(odsSzdnGantry.getLon()):
                                tracks.setStartLon(odsSzdnGantry.getLon())  # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.getLat()):
                                tracks.setStratLat(odsSzdnGantry.getLat())  # 纬度

                        tracks.setEnvehicletype(CommonUtil.isNull(firstBo.getCartypecode()))  # 车型
                        tracks.setEnvehicleid(carNo)  # 车牌号

                        tracks.setExitTime(endTime)

                        endGantryid = CommonUtil.isNull(endBo.getGantrycode())
                        tracks.setExtollstationid(endGantryid)
                        if endGantryid in gantryMao:
                            odsSzdnGantry = gantryMao[endGantryid]
                            tracks.setExtollstationname(odsSzdnGantry.getGantryName())  # 门架名称

                            if CommonUtil.isNotBlank(odsSzdnGantry.getLon()):
                                tracks.setEndLon(odsSzdnGantry.getLon())  # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.getLat()):
                                tracks.setEndLat(odsSzdnGantry.getLat())  # 纬度

                        tracks.setExvehicleid(carNo)  # 车牌号

                        # 【Java→Python】BigDecimal → float 字段，先 _bd 校验再落 float
                        if CommonUtil.isNotBlank(tracks.getStartLon()):
                            tracks.setStartLonDec(_bdFloat(tracks.getStartLon()))
                        if CommonUtil.isNotBlank(tracks.getStratLat()):
                            tracks.setStratLatDec(_bdFloat(tracks.getStratLat()))
                        if CommonUtil.isNotBlank(tracks.getEndLon()):
                            tracks.setEndLonDec(_bdFloat(tracks.getEndLon()))
                        if CommonUtil.isNotBlank(tracks.getEndLat()):
                            tracks.setEndLatDec(_bdFloat(tracks.getEndLat()))

                        # -------------- 车辆轨迹点
                        josnList: List[TrailBo] = []
                        for snapshotBo in snapshotList:
                            trailBo = TrailBo()

                            gantryCode = CommonUtil.isNull(snapshotBo.getGantrycode())

                            trailBo.setStateType(stateType)
                            trailBo.setPlatenumber(snapshotBo.getPlatenumber())
                            trailBo.setLocationId(gantryCode)
                            trailBo.setLocationCode(gantryCode)
                            trailBo.setPointUuid(snapshotBo.getDatauuid())
                            trailBo.setSectionCode(snapshotBo.getSectioncode())

                            captureTime = snapshotBo.getSnapshottime()
                            if captureTime is not None:
                                trailBo.setCaptureTime(_formatDateTime(captureTime))

                            trailBo.setDevCode(gantryCode)  # 设备编号
                            if gantryCode in gantryMao:
                                odsSzdnGantry = gantryMao[gantryCode]
                                lon = odsSzdnGantry.getLon()
                                lat = odsSzdnGantry.getLat()

                                trailBo.setPileno(odsSzdnGantry.getPileNo())  # 桩号
                                if CommonUtil.isNotBlank(lon):
                                    trailBo.setLon(_bdFloat(lon))
                                if CommonUtil.isNotBlank(lat):
                                    trailBo.setLat(_bdFloat(lat))

                                trailBo.setDevName(odsSzdnGantry.getGantryName())  # 设备名称

                            # 设备名称没有默认位置信息--------------
                            if CommonUtil.isBlank(trailBo.getDevName()):
                                trailBo.setDevName(gantryCode)

                            trailBo.setRoadCode(roadCode)
                            josnList.append(trailBo)

                        escapedTypeRemark = (sectionName + "路段全程屏蔽：其中门架牌识流水数量:"
                                             + _javaStr(len(snapshotList))
                                             + "，门架交易成功流水数量:0。")
                        escapedType = Constants.escapedType_20
                        tracks.setEscapedType(escapedType)  # 屏蔽
                        tracks.setEscapedTypeRemark(escapedTypeRemark)
                        tracks.setEscapedTfcj("3")  # 路段屏蔽

                        # 车牌颜色
                        tracks.setPlateColor(platecolor)

                        trailInfo = TrailInfo()
                        trailInfo.setTracks(tracks)
                        trailInfo.setTrailList(josnList)
                        trailInfo.setTrailUuid(carNo)

                        # 判断门架抓拍是否经过了虚拟门架
                        if self.getIsVirtualFlag(trailInfo.getTrailList()):
                            kykey = self.getSuspiciousKey(redisDate, carNo)
                            isExistObj = self.redisCache.getCacheObject(kykey)
                            if isExistObj is None:
                                self.redisCache.setCacheObject(kykey, trailInfo)

    # ==================================================================
    # Java L2537-L2638：根据流水节点与门架交易流水对比，生成可疑车辆
    # ==================================================================
    def separateUnfiitingList(self, carlistRtn: List[ZdataTrailTracks],
                              feeRecords01Map: dict[str, OdsLwzxsfsjFeeRecords01]) -> None:
        """对候选轨迹点统计"门架牌识流水/门架交易流水/交易成功数"，判定逃费场景 1/2/3。

        【Java→Python 关键差异】
        1) `JSON.parseArray(keyValue, TrailBo.class)` → 替身返回 JSONArray（元素为 TrailBo）。
        2) `new BigDecimal(int)` → `_bd(int)`；`divide(..., 4, ROUND_HALF_UP)` 精确到 4 位小数。
        3) `bite.compareTo(costBite) >= 0` → 同为 `compareTo`（忽略 scale 只比数值）。
        4) 【忠实保留】场景描述里用的是 `conutGantryCapture`（门架牌识数），
           `costBite` 的分子却是 `conutFeeRecord`、分母是 `sussFeeRecord`（原文如此）。
        5) `flag == "0"` 表示"没有拟合轨迹"的候选点，会被打上 "currentTrack" 标记。
        """
        now = datetime.now()
        redisDate = now.strftime("%Y%m%d")
        bite = _bd("0.5")  # 门架抓拍和流水抓拍占比

        log.info("生成可疑的数据开始：" + _javaDateToString(datetime.now()))
        log.info("参数:轨迹点数量" + _javaStr(len(carlistRtn)))

        if carlistRtn is not None and len(carlistRtn) > 0 and feeRecords01Map is not None:
            for tracks in carlistRtn:
                if tracks is not None:
                    carNo = CommonUtil.isNull(tracks.getPlateKey())
                    keyValue = tracks.getTrailPoints()  # 行驶轨迹
                    typeFlag = CommonUtil.isNull(tracks.getFlag())
                    josnList: List[TrailBo] = []
                    if CommonUtil.isNotBlank(keyValue):
                        josnList = JSON.parseArray(keyValue, TrailBo)
                        if josnList is not None and len(josnList) > 0:
                            # 没有轨迹点的s
                            if typeFlag == "0":
                                tracks.setFlag("currentTrack")  # 设置起点和终点

                            # ---------------------------分析场景: 路段抓拍和流水抓拍 占比
                            conutGantryCapture = 0  # 门架抓拍流水
                            conutFeeRecord = 0  # 门架抓拍流水
                            sussFeeRecord = 0  # 成功门架抓拍流水

                            for rtnTrailBo in josnList:
                                stateType = CommonUtil.isNull(rtnTrailBo.getStateType())
                                pointUuid = CommonUtil.isNull(rtnTrailBo.getPointUuid())
                                if stateType == self.GANTRY_CAPTURE:
                                    # 门架抓拍
                                    conutGantryCapture += 1
                                elif stateType == self.FeeRecord:
                                    # 卡口流水
                                    conutFeeRecord += 1
                                    if CommonUtil.isNotBlank(pointUuid):
                                        feeRecordObj = feeRecords01Map.get(pointUuid)
                                        if feeRecordObj is not None:
                                            rtnFeeRecords01 = feeRecordObj
                                            fee = rtnFeeRecords01.getFee()
                                            if (fee is not None
                                                    and _bd(fee).compareTo(
                                                        BigDecimal.ZERO) > 0):
                                                sussFeeRecord += 1

                            addFlag = False
                            escapedTfcj = ""  # 逃费场景
                            escapedTypeRemark = ""  # 场景描述
                            escapedType = ""
                            if conutFeeRecord == 0:
                                # 全屏蔽
                                escapedTypeRemark = ("全程屏蔽：其中门架牌识流水数量:"
                                                     + _javaStr(conutGantryCapture)
                                                     + "，门架交易流水数量:"
                                                     + _javaStr(conutFeeRecord) + "。")
                                escapedTfcj = "1"
                                escapedType = Constants.escapedType_20
                                addFlag = True
                            else:
                                if sussFeeRecord == 0:
                                    escapedTypeRemark = ("全程屏蔽(交易成功)：其中门架牌识流水数量:"
                                                         + _javaStr(conutGantryCapture)
                                                         + "，门架交易流水数量:"
                                                         + _javaStr(conutFeeRecord) + "，"
                                                         + "，门架交易流水成功数量:"
                                                         + _javaStr(sussFeeRecord) + "。")
                                    escapedTfcj = "3"
                                    escapedType = Constants.escapedType_20
                                    addFlag = True
                                else:
                                    # 【Java→Python】divide(divisor, 4, ROUND_HALF_UP)
                                    costBite = _bd(conutFeeRecord).divide(
                                        _bd(sussFeeRecord), 4, BigDecimal.ROUND_HALF_UP)
                                    if bite.compareTo(costBite) >= 0:
                                        escapedTypeRemark = (
                                            "部分屏蔽(交易成功)：其中门架牌识流水数量:"
                                            + _javaStr(conutGantryCapture)
                                            + "，门架交易流水数量:"
                                            + _javaStr(conutFeeRecord) + "，"
                                            + "，门架交易流水成功数量:"
                                            + _javaStr(sussFeeRecord) + "。")
                                        escapedTfcj = "2"
                                        escapedType = Constants.escapedType_20
                                        addFlag = True

                            if addFlag:
                                tracks.setEscapedTfcj(escapedTfcj)  # 逃费场景
                                tracks.setEscapedType(escapedType)
                                tracks.setEscapedTypeRemark(escapedTypeRemark)

                                trailInfo = self.changeData(tracks, josnList)  # 获取设备的经纬度

                                # 车牌颜色
                                tracks.setPlateColor(self.getPlateColor(trailInfo.getTrailList()))
                                trailInfo.setTrailUuid(carNo)

                                suspiciousKey = self.getSuspiciousKey(redisDate, carNo)
                                self.redisCache.setCacheObject(suspiciousKey, trailInfo)
        log.info("生成可疑车辆的数据结束：" + _javaDateToString(datetime.now()))

    # ==================================================================
    # Java L2644-L2692：数据推送（调用远端接口同步可疑车辆）
    # ==================================================================
    def syncSuspiciousCarDB(self) -> None:
        """把当天 Redis 中的可疑车辆打包，签名后调用 `syncSuspiciousCarTask` 上传。

        【Java→Python 关键差异】
        1) `Long timeStamp = System.currentTimeMillis();` → int（Python 无 Long）。
           拼签名时 Java 走 `String + Long` → 自动 toString，故用 `_javaStr(timeStamp)`。
        2) `SecuritySHA1Utils.shaEncode(...)` 的受检异常 → Python 直接 `raise RuntimeError(e)`
           （对应 `throw new RuntimeException(e)`）。
        3) `jsonObject.getInteger(CODE_TAG)` 可能为 None；Java 与 int 比较会自动拆箱抛 NPE，
           Python 的 `None == 200` 只是 False —— **差异点**，此处保持 Python 自然语义
           （失败分支不执行删除，不额外抛错）。
        4) `@Resource HttpSysUtilApiService` 的 Forest 动态代理 → 构造器注入的
           `ForestHttpSysUtilApiService`（离线默认实现，返回 code=200）。
        """
        # 从redis拿
        trailInfoList: List[TrailInfo] = []
        now = datetime.now()
        formattedDate = now.strftime("%Y%m%d")

        keys = self.redisCache.keys(Constants.car_uspicious + formattedDate + "*")
        if keys is not None and len(keys) > 0:
            for key in keys:
                trailInfo = self.redisCache.getCacheObject(key)
                trailInfoList.append(trailInfo)

        # 签名key
        signatureKey = "car_monit_pt"

        # 时间戳(毫秒)
        timeStamp = System.currentTimeMillis()

        # 签名
        try:
            signature = SecuritySHA1Utils.shaEncode(signatureKey + _javaStr(timeStamp))
        except Exception as e:
            raise RuntimeError(e)

        suspiciousCarVO = SuspiciousCarVO()
        suspiciousCarVO.setSignatureKey(signatureKey)
        suspiciousCarVO.setTimeStamp(timeStamp)
        suspiciousCarVO.setSignature(signature)
        suspiciousCarVO.setTrailInfoList(trailInfoList)
        log.info("调用接口开始--------：" + _javaDateToString(datetime.now()))
        jsonObject = self.httpSysUtilApiService.syncSuspiciousCarTask(suspiciousCarVO)
        responseCode = jsonObject.getInteger(AjaxResult.CODE_TAG)
        log.info("调用接口结束--------：" + _javaDateToString(datetime.now()))
        log.info(jsonObject.toJSONString())
        if responseCode == HttpStatus.SUCCESS:
            log.info("调用接口成功返回--------：" + _javaDateToString(datetime.now()))
            if keys is not None and len(keys) > 0:
                # 删除redis
                self.redisCache.deleteObject(keys)


# ======================================================================
# 【Java→Python】接口抽象方法覆盖自检
# ======================================================================
# Java 的 `implements ISysUtilService` 由编译器保证"方法都实现了"；
# Python 的 ABC 只在**实例化时**检查 `__abstractmethods__` 是否为空，
# 一旦某个方法漏写，会抛 TypeError: Can't instantiate abstract class。
# 这里在模块加载完成后显式比对一次，把"缺方法"变成立即失败的 ImportError，
# 便于 CI/重构校验尽早发现（不影响运行期性能）。
def _assert_interface_implemented() -> None:
    missing = sorted(getattr(SysUtilServiceImpl, "__abstractmethods__", frozenset()))
    if missing:
        raise ImportError(
            "SysUtilServiceImpl 未实现 ISysUtilService 的抽象方法: " + ", ".join(missing))


_assert_interface_implemented()
