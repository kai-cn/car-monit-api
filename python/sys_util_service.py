# -*- coding: utf-8 -*-
"""
SysUtilServiceImpl（Java）→ Python 3.12 一比一重构版
===============================================================================
源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java
本文件：python/sys_util_service.py（新增文件，不修改、不影响原 Java 工程）

移植原则
--------
1. 方法名、方法体语句顺序、分支顺序、魔法数字、日志文案、Redis key 规则全部与 Java 对齐；
2. Java 侧的历史遗留问题（例如 lat 误取 lon、注释写“30分钟/3分钟”而实际是 1 小时/4 分钟等）
   一律【原样保留】，不做“顺手修复”，保证可逐行对照；
3. Java 与 Python 语义差异较大之处统一用 `# 【Java→Python】` 前缀标注。

主要语义差异总览
----------------
- Lombok @Data 实体            → @dataclass（getter/setter 退化为属性访问）
- BigDecimal                   → decimal.Decimal（divide 必须显式 quantize + ROUND_HALF_UP）
- Date / SimpleDateFormat / Calendar
                               → datetime + strftime/strptime（解析严格性不同）
- Spring RedisTemplate         → RedisCache（内存实现，读写 deepcopy 模拟“序列化隔离”）
- JedisCluster                 → JedisCluster 桩（仅实现 get）
- MyBatis Mapper / 远程 HTTP    → 构造注入的接口桩，方法名保持 Java 原名
- "a" + null（Java 得 "null"）  → _java_str()，避免 Python 拼接 None 抛 TypeError
- switch-case                  → if/elif（Java 的 break 语义天然满足）
- stream().map / sorted        → 列表推导 / sorted(key=...)
- Integer == int（自动拆箱）     → Python ==（None 比较不抛 NPE，见具体注释）
- Collection 重载 deleteObject  → 单方法内部按类型分发
- List.subList（视图）           → 列表切片（生成新列表）
- String.split（丢弃尾部空串）   → str.split（保留尾部空串）
- UUID / SHA1 / JSON           → uuid4().hex / hashlib.sha1 / json
"""

from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

# @Slf4j：Python 侧用模块级 logger，调用点 log.info/log.error 与 Java 一一对应
log = logging.getLogger(__name__)


# =============================================================================
# 一、常量（与 SysUtilServiceImpl / Constants 完全一致）
# =============================================================================

# ---- 流水来源类型标识
BORDER_WEIGHING_CAPTURE = "BorderWeighingCapture"  # 省界称重
GANTRY_CAPTURE = "GantryCapture"                   # 门架抓拍
PROV_CAPTURE = "ProvCapture"                       # 省界抓拍
SERVICE_AREA_CAPTURE = "ServiceAreaCapture"        # 服务区抓拍
STATION_CAPTURE = "StationCapture"                 # 收费站抓拍

# ---- 流水类型
FeeRecord = "FeeRecord"                # 卡口流水
FeeStationEnter = "FeeStationEnter"    # 收费站入口流水
FeeStationExit = "FeeStationExit"      # 收费站出口流水

# ---- Redis 配置类 key（“比例默认为0.5/默认2天”等注释原样保留）
redisBiteKey = "sys_config:syncSuspiciousCar_bite"          # 比例默认为0.5
redisTimeKey = "sys_config:syncSuspiciousCar_time"          # 默认2天
supoer_mjnum = "sys_config:supoer_mjnum"                    # 跨省：门架数量 5个
road_supoer_mjnum = "sys_config:road_supoer_mjnum"          # 路段： 门架数量 3个
jholiday_time = "sys_config:jholiday_time"                  # 节假日时间

# ---- com.ruoyi.common.constant.Constants 中被本类引用的常量
CONST_TRAIL = "trail:"                                  # Constants.trail
CONST_CAR_LIST_JC = "car_list_jc"                       # Constants.car_list_jc
CONST_CAR_USPICIOUS = "car_uspicious"                   # Constants.car_uspicious
CONST_CAR_CURENT_TRAIL = "car_curent_trail:"            # Constants.car_curent_trail
CONST_ESCAPED_TYPE_20 = "20"                            # Constants.escapedType_20
CONST_SNAPSHOT_FLOW_LIST = "js_car_snapshot"            # Constants.snapshotFlowList
CONST_FEE_RECORDS_LIST = "js_car_reerecords"            # Constants.feeRecordsList
CONST_TRAIL_FITTING_LIST = "js_car_trail_fitting"       # Constants.trailFittingList
CONST_TRAIL_UN_FITTING_LIST = "js_car_trail_unfitting"  # Constants.trailUnFittingList


# =============================================================================
# 二、CommonUtil / 日期 / JSON / 编码 工具（行为逐条对齐 Java）
# =============================================================================

def is_null(names: Any) -> str:
    """CommonUtil.isNull：null → ""，否则 toString().trim()。

    【Java→Python】Java 的 String.trim() 只裁剪 <= U+0020 的字符，
    Python 的 str.strip() 裁剪所有 Unicode 空白，业务数据（车牌/编码）无差异。
    """
    if names is None:
        return ""
    return str(names).strip()


def is_not_blank(text: Optional[str]) -> bool:
    """CommonUtil.isNotBlank → StringUtils.isNotBlank：非 None 且去空白后非空。"""
    return text is not None and text.strip() != ""


def is_blank(text: Optional[str]) -> bool:
    """CommonUtil.isBlank。"""
    return not is_not_blank(text)


def delete_end(obj: Any) -> str:
    """CommonUtil.deleteEnd：去掉结尾的一个英文逗号。"""
    value = is_null(obj)
    if value.endswith(","):
        value = value[: len(value) - 1]
    return value


def repalace_pic_url(images_arry: Any) -> str:
    """CommonUtil.repalacePicUrl：图片域名替换。

    【Java→Python】Java 用的是 String.replaceAll（正则），这里的 URL 里含 '.'，
    正则会把它当通配符，但由于替换目标是字面量、源串固定，结果与 str.replace 一致。
    """
    value = is_null(images_arry)
    if is_not_blank(value):
        if "http://jxjt.isilon.com/ifs" in value:
            value = value.replace("http://jxjt.isilon.com/ifs", "http://36.200.30.144:9080")
        else:
            value = value.replace("http://jxjt.isilon.com", "http://36.200.30.144:9080")
    return value


def repalace_szdn_toll_name(toll_name: Any) -> str:
    """CommonUtil.repalaceSzdnTollName：去掉“收费站/江西/站”。"""
    value = is_null(toll_name)
    if is_not_blank(value):
        value = value.replace("收费站", "")
        value = value.replace("江西", "")
        value = value.replace("站", "")
    return value


def get_uuid() -> str:
    """StringUtils.getUUID：UUID.randomUUID().toString().replaceAll("-", "")。"""
    return uuid.uuid4().hex


def sha_encode(in_str: str) -> str:
    """SecuritySHA1Utils.shaEncode：SHA1(UTF-8) 小写十六进制。"""
    return hashlib.sha1(in_str.encode("utf-8")).hexdigest()


def _java_str(value: Any) -> str:
    """模拟 Java 字符串拼接 / String.valueOf 的语义：null → "null"。

    【Java→Python】Java 里 "x" + obj（obj 为 null）得到 "xnull"；
    Python 直接拼 None 会抛 TypeError。凡是 Java 源码对可能为 null 的字段做
    `+=` 拼接的位置，这里都显式走 _java_str()。
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# ---- SimpleDateFormat 模式常量（与 Java 中的 pattern 字符串一一对应）
_FMT_DATE_COMPACT = "%Y%m%d"           # new SimpleDateFormat("yyyyMMdd")
_FMT_DATE = "%Y-%m-%d"                 # new SimpleDateFormat("yyyy-MM-dd")
_FMT_DATETIME = "%Y-%m-%d %H:%M:%S"    # new SimpleDateFormat("yyyy-MM-dd HH:mm:ss")
_FMT_DATETIME_T = "%Y-%m-%dT%H:%M:%S"  # new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss")


def _format_date(fmt: str, value: datetime) -> str:
    """SimpleDateFormat.format 的等价实现。"""
    return value.strftime(fmt)


# Java 的 SimpleDateFormat.parse 只要求从字符串开头按 pattern 解析，允许尾随内容
# （例如用 "yyyy-MM-dd" 解析 "2025-10-14 13:46:42" 是成功的），
# 而 Python 的 strptime 要求整串完全匹配。这里为每个 pattern 定义“前缀正则”，
# 先截取可解析的前缀再交给 strptime，从而与 Java 行为对齐。
_PATTERN_PREFIX_REGEX: dict[str, re.Pattern[str]] = {
    _FMT_DATE_COMPACT: re.compile(r"\d{8}"),
    _FMT_DATE: re.compile(r"\d{4}-\d{1,2}-\d{1,2}"),
    _FMT_DATETIME: re.compile(r"\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{1,2}:\d{1,2}"),
    _FMT_DATETIME_T: re.compile(r"\d{4}-\d{1,2}-\d{1,2}T\d{1,2}:\d{1,2}:\d{1,2}"),
}


def _parse_date(fmt: str, text: str) -> datetime:
    """SimpleDateFormat.parse 的等价实现。

    【Java→Python】
    1) Java 的 parse 允许尾随内容，Python 的 strptime 不允许 —— 这里先用前缀正则截取；
    2) Java 默认 lenient=true（会把 2025-13-45 “纠正”成合法日期），Python 严格校验并抛
       ValueError；本方法保留严格行为，调用方仍然包在 try/except 中，异常分支与 Java 一致
       （日志文案也保留）。
    """
    pattern = _PATTERN_PREFIX_REGEX.get(fmt)
    if pattern is not None:
        matched = pattern.match(text)
        if matched is None:
            raise ValueError(f"time data {text!r} does not match format {fmt!r}")
        return datetime.strptime(matched.group(0), fmt)
    return datetime.strptime(text, fmt)


def _millis(value: Optional[datetime]) -> int:
    """Date.getTime() 的等价实现：毫秒时间戳。

    【Java→Python】Java Date 内部是 UTC 毫秒；Python 朴素 datetime 的 timestamp() 按本机时区
    解释。本文件里毫秒只用于“同一时区下两个时间点的差值/区间判断”，结果一致；
    若要跨时区持久化，应改用 aware datetime。
    """
    if value is None:
        # Java 侧对 null 调 getTime() 会 NPE；此处抛 TypeError，调用点不会走到
        raise TypeError("Date.getTime(): date is None（对应 Java NullPointerException）")
    return int(value.timestamp() * 1000)


def _to_decimal(value: Any) -> Decimal:
    """new BigDecimal(String) 的等价实现。

    【Java→Python】Java 传 null 抛 NullPointerException；Decimal(None) 抛 TypeError。
    非法数字：Java 抛 NumberFormatException，Python 抛 decimal.InvalidOperation，
    调用方统一按 Exception 捕获 —— 与 Java 的 try/catch(Exception) 行为一致。
    """
    return Decimal(str(value))


def _json_loads(text: str) -> Any:
    """JSON.parse / JSON.parseArray 的等价实现（失败抛 json.JSONDecodeError）。"""
    return json.loads(text)


def _json_get_string(json_obj: dict, key: str) -> Optional[str]:
    """fastjson2 JSONObject.getString 的等价实现。

    【Java→Python】getString 对数字/布尔会做字符串化（1 → "1"，true → "true"），
    对象/数组则返回其 JSON 串；key 不存在或值为 null 时返回 None。这里逐条还原。
    """
    if not isinstance(json_obj, dict) or key not in json_obj:
        return None
    value = json_obj[key]
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _json_get_integer(json_obj: dict, key: str) -> Optional[int]:
    """fastjson2 JSONObject.getInteger 的等价实现。"""
    if not isinstance(json_obj, dict) or key not in json_obj:
        return None
    value = json_obj[key]
    if value is None:
        return None
    return int(value)


def _json_ready(value: Any) -> Any:
    """把 Python 值转换成 json.dumps 可序列化的形式。

    【Java→Python】fastjson2 会把 BigDecimal 输出为精确数值；Python 标准库无法输出
    Decimal 字面量，这里退化为 float（本文件只用于轨迹点 lon/lat，误差在 1e-15 量级）。
    若需要绝对精确，可在此处接入 simplejson(use_decimal=True)。
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        # fastjson2 默认把 Date 序列化为毫秒时间戳
        return _millis(value)
    if isinstance(value, TrailBo):
        return _trail_bo_to_dict(value)
    return value


# ---- TrailBo 的 Java 属性名映射（JSON.toJSONString / JSON.parseArray(TrailBo.class) 需要）
_TRAIL_BO_FIELDS: tuple[tuple[str, str], ...] = (
    ("point_uuid", "pointUuid"),
    ("state_type", "stateType"),
    ("point_flag", "pointFlag"),
    ("point_josn", "pointJosn"),
    ("capture_time", "captureTime"),
    ("direction_in", "directionIn"),
    ("location_code", "locationCode"),
    ("location_name", "locationName"),
    ("standard_code", "standardCode"),
    ("longitude", "longitude"),
    ("latitude", "latitude"),
    ("location_flag", "locationFlag"),
    ("ip_type", "ipType"),
    ("location_josn", "locationJosn"),
    ("dev_code", "devCode"),
    ("dev_name", "devName"),
    ("images_arry", "imagesArry"),
    ("lon", "lon"),
    ("lat", "lat"),
    ("road_code", "roadCode"),
    ("section_code", "sectionCode"),
    ("org_code", "orgCode"),
    ("direction", "direction"),
    ("pileno", "pileno"),
    ("pre_capture_time", "preCaptureTime"),
    ("count_num", "countNum"),
    ("platenumber", "platenumber"),
    ("location_id", "locationId"),
    ("is_query", "isQuery"),
    ("platecolor", "platecolor"),
    ("is_virtual", "isVirtual"),
)


def _trail_bo_to_dict(trail_bo: "TrailBo") -> dict:
    """TrailBo → fastjson2 风格 dict（跳过 null 字段，字段名保持 Java 驼峰）。"""
    data: dict[str, Any] = {}
    for py_name, java_name in _TRAIL_BO_FIELDS:
        value = getattr(trail_bo, py_name, None)
        if value is None:
            continue
        # 嵌套的业务 BO 在轨迹点里不会出现，这里直接透传可序列化值
        data[java_name] = _json_ready(value)
    return data


def _trail_bo_list_to_json(trail_bo_list: list["TrailBo"]) -> str:
    """JSON.toJSONString(List<TrailBo>) 的等价实现。"""
    return json.dumps([_trail_bo_to_dict(item) for item in trail_bo_list], ensure_ascii=False)


def _parse_array_to_trail_bo_list(text: str) -> list["TrailBo"]:
    """JSON.parseArray(text, TrailBo.class) 的等价实现。

    【Java→Python】fastjson2 依据属性名反射赋值，未出现的字段保持 null；这里同样只赋值
    JSON 中存在的键，lon/lat 转 Decimal，directionIn 转 bool。
    """
    result: list["TrailBo"] = []
    for item in _json_loads(text):
        if not isinstance(item, dict):
            continue
        trail_bo = TrailBo()
        for py_name, java_name in _TRAIL_BO_FIELDS:
            if java_name not in item:
                continue
            value = item[java_name]
            if value is None:
                continue
            if py_name in ("lon", "lat"):
                value = _to_decimal(value)
            elif py_name == "direction_in":
                value = bool(value)
            setattr(trail_bo, py_name, value)
        result.append(trail_bo)
    return result


# =============================================================================
# 三、Redis / 配置 基础设施（Spring 组件的 Python 替身）
# =============================================================================

class RedisCache:
    """com.ruoyi.common.core.redis.RedisCache 的内存版替身。

    【Java→Python】Java 侧数据经过 FastJson2 序列化后写入 Redis，读回来是“重新反序列化的
    副本”，因此“取出来改一改再放回去”不会影响缓存里的原对象。这里用 deepcopy 精确模拟
    这种“序列化隔离”，避免 Python 的引用语义改变业务行为。
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def set_cache_object(self, key: str, value: Any) -> None:
        # redisTemplate.opsForValue().set(key, value)
        self._store[key] = copy.deepcopy(value)

    def get_cache_object(self, key: str) -> Any:
        # 与序列化往返一致：每次读取都返回独立副本，未命中返回 None
        if key not in self._store:
            return None
        return copy.deepcopy(self._store[key])

    def has_key(self, key: str) -> bool:
        return key in self._store

    def delete_object(self, key_or_keys) -> bool:
        """deleteObject(String) 与 deleteObject(Collection) 两个重载的合并实现。"""
        if isinstance(key_or_keys, str):
            return self._store.pop(key_or_keys, None) is not None
        deleted = 0
        for key in list(key_or_keys or []):
            if self._store.pop(key, None) is not None:
                deleted += 1
        return deleted > 0

    def keys(self, pattern: str) -> list[str]:
        """Redis KEYS pattern。

        【Java→Python】RedisTemplate.keys 无匹配时返回空 Set（不是 null），Java 里的
        `null != keys` 只是防御式写法；fnmatch 的 * ? [] 语义与 Redis glob 基本一致。
        """
        return [key for key in list(self._store.keys()) if fnmatch.fnmatchcase(key, pattern)]


class RedisConfig:
    """com.ruoyi.common.core.redis.RedisConfig 的最小替身，仅暴露 getClusterNodes()。"""

    def __init__(self, cluster_nodes: str = "") -> None:
        self._cluster_nodes = cluster_nodes

    def get_cluster_nodes(self) -> str:
        return self._cluster_nodes


class JedisCluster:
    """redis.clients.jedis.JedisCluster 的最小替身：只实现本类用到的 get()。

    【Java→Python】生产环境走 JedisCluster 直连 Redis（字符串值）；这里用注入的 dict 存储，
    get 未命中返回 None，与 Jedis 返回 null 一致。
    """

    def __init__(self, store: dict[str, str]) -> None:
        self._store = store

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)


class RedisSourceFactory:
    """RedisSourceFactory 替身：createSource(redisConfig) → JedisCluster。"""

    def __init__(self) -> None:
        self._cluster_store: dict[str, str] = {}

    def create_source(self, redis_config: RedisConfig) -> JedisCluster:
        return JedisCluster(self._cluster_store)


class HttpStatus:
    """com.ruoyi.common.constant.HttpStatus 中本类用到的状态码。"""

    SUCCESS = 200


class AjaxResult(dict):
    """com.ruoyi.common.core.domain.AjaxResult 的最小替身（本质是 HashMap）。"""

    CODE_TAG = "code"
    MSG_TAG = "msg"
    DATA_TAG = "data"

    @staticmethod
    def success(msg: str = "操作成功") -> "AjaxResult":
        return AjaxResult({AjaxResult.CODE_TAG: HttpStatus.SUCCESS, AjaxResult.MSG_TAG: msg})


# =============================================================================
# 四、领域实体（Lombok @Data → @dataclass；字段名沿用 Java 语义，Python 用蛇形命名）
# =============================================================================

@dataclass
class TrailBo:
    """com.ruoyi.base.domain.TrailBo：单个轨迹点（抓拍/流水的最小单元）。"""

    point_uuid: Optional[str] = None                 # pointUuid 流水唯一标识符
    state_type: Optional[str] = None                 # stateType 流水来源类型标识
    point_flag: Optional[str] = None                 # pointFlag 是否有值 0否 1是
    point_josn: Optional[str] = None                 # pointJosn pointUuid 的 json 对象
    border_weighing_capture_bo: Any = None           # 省界称重
    gantry_capture_bo: Any = None                    # 门架抓拍
    prov_capture_bo: Any = None                      # 省界抓拍
    station_capture: Any = None                      # 收费站抓拍
    fee_record: Any = None                           # 卡口流水
    fee_station_enter: Any = None                    # 收费站入口流水
    fee_station_exit: Any = None                     # 收费站出口流水
    capture_time: Optional[str] = None               # captureTime 抓拍流水发生时间
    direction_in: Optional[bool] = None              # directionIn true进入 false驶出 null非进出类
    location_code: Optional[str] = None              # locationCode 设备IP地址
    location_name: Optional[str] = None              # 设备名称
    standard_code: Optional[str] = None              # 标准代码
    longitude: Optional[str] = None                  # 进度
    latitude: Optional[str] = None                   # 维度
    location_flag: Optional[str] = None              # 位置是否有值
    ip_type: Optional[str] = None                    # ip 类型 gantryip/stationip
    location_josn: Optional[str] = None              # 位置 json 对象
    gantry_ip_bo: Any = None                         # 门架IP
    station_ip_bo: Any = None                        # 收费站ip
    dev_code: Optional[str] = None                   # 设备编码
    dev_name: Optional[str] = None                   # 设备名称
    images_arry: Optional[str] = None                # 抓拍图片（逗号分隔）
    lon: Optional[Decimal] = None                    # 经度
    lat: Optional[Decimal] = None                    # 维度
    road_code: Optional[str] = None                  # 路线编号
    section_code: Optional[str] = None               # 路段编号
    org_code: Optional[str] = None                   # 机构编码
    direction: Optional[str] = None                  # 方向（0上行 1下行）
    pileno: Optional[str] = None                     # 桩号
    pre_capture_time: Optional[str] = None           # 上一个抓拍时间
    count_num: Optional[int] = None                  # 数量
    platenumber: Optional[str] = None                # 车牌号
    location_id: Optional[str] = None                # 位置ID
    is_query: Optional[str] = None                   # 是否查询：1查询
    platecolor: Optional[str] = None                 # 车牌颜色
    is_virtual: Optional[str] = None                 # 是否虚门架 0否 1是


@dataclass
class ZdataTrailTracks:
    """com.ruoyi.base.domain.ZdataTrailTracks：一趟车的完整轨迹。

    【Java→Python】Java 侧 @EqualsAndHashCode 让实体可作为 HashMap 的 key；@dataclass 默认
    eq=True 时不可哈希（__hash__ 为 None）。本文件中该实体只在 List 里流转，未做 dict key。
    """

    uuid: Optional[str] = None                       # 唯一标识符
    type: Optional[int] = None                       # 轨迹类型 0不完整 1完整
    point_count: Optional[int] = None                # 轨迹点数量
    plate_key: Optional[str] = None                  # 车牌唯一标识
    enter_time: Optional[datetime] = None            # 进入时间
    exit_time: Optional[datetime] = None             # 离开时间
    trail_points: Optional[str] = None               # 轨迹点集合（JSON 串）
    enter_locationcode: Optional[str] = None         # 进入位置code
    exit_locationcode: Optional[str] = None          # 离开位置code
    track_jsn: Optional[str] = None                  # 集合详情
    enaxlecount: Optional[int] = None                # 入口车轴数
    entolllaneid: Optional[str] = None               # 入口车道编号
    entollstationid: Optional[str] = None            # 入口收费站编号
    entollstationname: Optional[str] = None          # 入口收费站名称
    envehicleclass: Optional[str] = None             # 入口车型分类
    envehicleid: Optional[str] = None                # 入口车辆编号
    envehicletype: Optional[str] = None              # 入口车辆类型代码
    enweight: Optional[Decimal] = None               # 入口称重(kg)
    extolllaneid: Optional[str] = None               # 出口车道编号
    extollstationid: Optional[str] = None            # 出口收费站编号
    extollstationname: Optional[str] = None          # 出口收费站名称
    exvehicleclass: Optional[str] = None             # 出口车型分类
    exvehicleid: Optional[str] = None                # 出口车辆编号
    exvehicletype: Optional[str] = None              # 出口车辆类型代码
    exweight: Optional[Decimal] = None               # 出口称重(kg)
    start_lon: Optional[str] = None                  # 入口收费站经度
    strat_lat: Optional[str] = None                  # 入口收费站维度（原字段名拼写如此）
    end_lon: Optional[str] = None                    # 出口收费站经度
    end_lat: Optional[str] = None                    # 出口收费站维度
    firt_station_code: Optional[str] = None          # 入栈口
    firt_station_name: Optional[str] = None          # 入栈口名称
    firt_station_time: Optional[str] = None          # 入栈口时间
    plate_color: Optional[str] = None                # 车牌颜色（字典：1白色2黑色）
    car_type: Optional[str] = None                   # 车型
    car_no: Optional[str] = None                     # 车牌号
    car_vehicle: Optional[str] = None                # 车种
    car_num: Optional[int] = None                    # 轴数
    pass_type: Optional[str] = None                  # 通行标识
    escaped_type: Optional[str] = None               # 逃费类型
    escaped_type_remark: Optional[str] = None        # 逃费类型：原因
    apply_time1: Optional[str] = None                # 申请时间1
    apply_time2: Optional[str] = None                # 申请时间2
    flag: Optional[str] = None                       # 标识
    start_lon_dec: Optional[Decimal] = None          # 入口收费站经度（BigDecimal）
    strat_lat_dec: Optional[Decimal] = None          # 入口收费站维度（BigDecimal）
    end_lon_dec: Optional[Decimal] = None            # 出口收费站经度（BigDecimal）
    end_lat_dec: Optional[Decimal] = None            # 出口收费站维度（BigDecimal）
    escaped_tfcj: Optional[str] = None               # 逃费场景
    trailtype: Optional[str] = None                  # 业务类型 0省外收费 1省内收费


@dataclass
class TrailInfo:
    """com.ruoyi.base.domain.TrailInfo：轨迹聚合对象（写入 Redis 的可疑车辆结构）。"""

    trail_uuid: Optional[str] = None                 # 轨迹ID
    enter_time: Optional[datetime] = None            # 进入时间（分区键）
    tracks: Optional[ZdataTrailTracks] = None        # 轨迹对象
    trail_list: Optional[list[TrailBo]] = None       # 轨迹详情


@dataclass
class CarVO:
    """com.ruoyi.base.domain.CarVO。"""

    car_no: Optional[str] = None                     # 车牌号


@dataclass
class CarParaVO:
    """com.ruoyi.base.domain.CarParaVO：轨迹查询条件。"""

    carlist: Optional[list[CarVO]] = None            # 车辆列表
    car_no: Optional[str] = None                     # 车牌号
    apply_time1: Optional[str] = None                # 时间查询
    apply_time2: Optional[str] = None
    car_no_list: Optional[list[str]] = None          # 车辆编号数组
    page_num: Optional[int] = None                   # 当前页面
    page_size: Optional[int] = None                  # 分页大小
    start_num: Optional[int] = None                  # 起始界面
    end_num: Optional[int] = None                    # 最后的界面
    star_time: Optional[int] = None                  # 起始天数
    end_time: Optional[int] = None                   # 最后的天数
    flag: Optional[str] = None                       # 标识位
    section_list: Optional[list[str]] = None         # 对象集合
    last_exit_time: Optional[datetime] = None        # 游标分页的最后出站时间


@dataclass
class TrailTracksVo:
    """com.ruoyi.base.domain.TrailTracksVo：缓存里的“出入口时间段”。"""

    plate_key: Optional[str] = None                  # 车牌唯一标识
    enter_time: Optional[datetime] = None            # 进入时间
    exit_time: Optional[datetime] = None             # 离开时间
    trailpoints: Optional[str] = None                # 轨迹点
    envehicletype: Optional[str] = None              # 车牌型号


@dataclass
class SuspiciousCarVO:
    """com.ruoyi.base.domain.SuspiciousCarVO：推送给外部接口的报文。"""

    signature_key: Optional[str] = None              # 签名key
    time_stamp: Optional[int] = None                 # 时间戳
    signature: Optional[str] = None                  # 签名
    trail_info_list: list[TrailInfo] = field(default_factory=list)


@dataclass
class OdsSzdnGantry:
    """com.ruoyi.base.domain.OdsSzdnGantry：门架基础信息。"""

    id: Optional[str] = None
    gantry_code: Optional[str] = None
    gantry_name: Optional[str] = None
    road_code: Optional[str] = None
    section_code: Optional[str] = None
    toll_code: Optional[str] = None
    org_code: Optional[str] = None
    direction: Optional[str] = None
    pile_no: Optional[str] = None
    lon: Optional[str] = None
    lat: Optional[str] = None
    is_virtual: Optional[str] = None


@dataclass
class OdsSzdnGantryIp:
    """com.ruoyi.base.domain.OdsSzdnGantryIp：门架 IP 与门架的关联。"""

    id: Optional[int] = None
    gantry_code: Optional[str] = None
    gantry_name: Optional[str] = None
    org_code: Optional[str] = None
    ip: Optional[str] = None
    ods_szdn_gantry: Optional[OdsSzdnGantry] = None


@dataclass
class OdsSzdnToll:
    """com.ruoyi.base.domain.OdsSzdnToll：收费站基础信息。"""

    id: Optional[str] = None
    road_code: Optional[str] = None
    section_code: Optional[str] = None
    toll_code: Optional[str] = None
    toll_name: Optional[str] = None
    pile_no: Optional[str] = None
    longitude: Optional[str] = None
    latitude: Optional[str] = None


@dataclass
class OdsSzdnTollStationIp:
    """com.ruoyi.base.domain.OdsSzdnTollStationIp：收费站 IP 与收费站的关联。"""

    toll_code: Optional[str] = None
    toll_name: Optional[str] = None
    ods_szdn_toll: Optional[OdsSzdnToll] = None


@dataclass
class ZdataLocationDict:
    """com.ruoyi.base.domain.ZdataLocationDict：设备 IP → 设施的标准映射。"""

    id: Optional[int] = None
    type: Optional[str] = None
    name: Optional[str] = None
    raw_code: Optional[str] = None
    standard_code: Optional[str] = None
    roadcode: Optional[str] = None
    roadname: Optional[str] = None
    sectioncode: Optional[str] = None
    sectionname: Optional[str] = None
    tollcode: Optional[str] = None
    tollname: Optional[str] = None
    orgcode: Optional[str] = None
    orgname: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    pile_no_k: Optional[str] = None
    pile_no: Optional[str] = None
    direction: Optional[str] = None


@dataclass
class OdsSzdnSection:
    """com.ruoyi.base.domain.OdsSzdnSection：路段基础信息。"""

    id: Optional[str] = None
    road_code: Optional[str] = None
    road_name: Optional[str] = None
    section_code: Optional[str] = None
    section_name: Optional[str] = None


@dataclass
class OdsRtSzdnSnapshotFlowAddcode:
    """com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode：门架抓拍流水。"""

    roadcode: Optional[str] = None
    sectioncode: Optional[str] = None
    direction: Optional[int] = None
    platenumber: Optional[str] = None
    platecolor: Optional[str] = None
    cartypecode: Optional[int] = None
    snappicturepath: Optional[str] = None
    datauuid: Optional[str] = None
    snapshottime: Optional[datetime] = None
    gantrycode: Optional[str] = None
    apply_time1: Optional[str] = None
    apply_time2: Optional[str] = None
    start_num: Optional[int] = None
    end_num: Optional[int] = None
    section_list: Optional[list[str]] = None


@dataclass
class OdsLwzxsfsjFeeRecords01:
    """com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01：门架交易流水。"""

    fee: Optional[Decimal] = None
    gantryid: Optional[str] = None
    vehicleplate: Optional[str] = None
    cid: Optional[str] = None
    transtime: Optional[datetime] = None
    sectioncode: Optional[str] = None
    plate_color: Optional[str] = None
    gantry_name: Optional[str] = None
    in_apply_time1: Optional[str] = None
    in_apply_time2: Optional[str] = None
    start_num: Optional[int] = None
    end_num: Optional[int] = None
    order_by_flag: Optional[str] = None
    section_list: Optional[list[str]] = None
    cid_list: Optional[list[str]] = None


@dataclass
class OdsRtSzdnSnapshotFlowProvcaptureAddcode:
    """com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode：省界抓拍流水。"""

    platecolor: Optional[str] = None
    plateimage: Optional[str] = None
    sideimage: Optional[str] = None
    headimage: Optional[str] = None


@dataclass
class OdsRtSzdnSnapshotFlowStationcaptureAddcode:
    """com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode：收费站抓拍流水。"""

    snappicturepath: Optional[str] = None


@dataclass
class OdsSzdnProvinceBorderVehicleWeightNewstructure:
    """com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure：省界称重流水。"""

    weighing_images_arry: Optional[str] = None


@dataclass
class OdsCxztFwqclls:
    """com.ruoyi.base.domain.OdsCxztFwqclls：服务区车辆流水。"""

    targetpicurl: Optional[str] = None
    platepicurl: Optional[str] = None


@dataclass
class OdsLwzxsfsjFeeStationEnter01:
    """com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01：收费站入口流水。

    本类只做“判存 + 置空图片”，Java 侧也未读取任何字段，故保持空实体。
    """


@dataclass
class OdsLwzxsfsjFeeStationExit01:
    """com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01：收费站出口流水。"""


# =============================================================================
# 五、依赖服务（Spring 注入的 Bean / MyBatis Mapper → 构造注入的接口桩）
# =============================================================================

class _ServiceStub:
    """Bean/Mapper 占位基类。

    Java 侧这些依赖由 @Autowired/@Resource 注入；Python 侧改为构造参数注入，
    缺省用本占位类。任一未接入的方法被调用时立刻抛 NotImplementedError，
    避免“静默返回空数据”掩盖接线错误。
    """

    def __getattr__(self, method_name: str):
        if method_name.startswith("_"):
            raise AttributeError(method_name)

        def _stub(*args, **kwargs):
            raise NotImplementedError(
                f"{self.__class__.__name__}.{method_name} 未接入实现"
                f"（对应 Java 侧 Spring Bean / MyBatis Mapper）"
            )

        return _stub


class IZdataTrailTracksService(_ServiceStub):
    """getLatestTrail / getUnFitting / getHistoryTrail / selectZdataTrailTracksList。"""


class IOdsSzdnProvinceBorderVehicleWeightNewstructureService(_ServiceStub):
    """selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids。"""


class IOdsRtSzdnSnapshotFlowAddcodeService(_ServiceStub):
    """selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids / selectOdsRtSzdnSnapshotFlowAddcodeListNew。"""


class IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService(_ServiceStub):
    """selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids。"""


class IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService(_ServiceStub):
    """selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids。"""


class IOdsSzdnTollStationIpService(_ServiceStub):
    """selectStationIpMap / getRedisList。"""


class IOdsSzdnGantryIpService(_ServiceStub):
    """selectOdsSzdnGantryIpMap / getRedisList。"""


class IOdsLwzxsfsjFeeRecords01Service(_ServiceStub):
    """selectOdsLwzxsfsjFeeRecords01ByQueryUuids / selectOdsLwzxsfsjFeeRecords01ListNew。"""


class IOdsLwzxsfsjFeeStationEnter01Service(_ServiceStub):
    """selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids。"""


class IOdsLwzxsfsjFeeStationExit01Service(_ServiceStub):
    """selectOdsLwzxsfsjFeeStationExit01ByQueryUuids。"""


class IZdataLocationDictService(_ServiceStub):
    """getRedisList。"""


class IOdsCxztFwqcllsService(_ServiceStub):
    """selectOdsCxztFwqcllsByQueryUuids。"""


class IDwdLcztFwqjcxxService(_ServiceStub):
    """getServiceNameMap（当前实现中已注释，未被调用）。"""


class IOdsSzdnSectionService(_ServiceStub):
    """getSectionMap / getSectionList。"""


class IOdsSzdnGantryService(_ServiceStub):
    """getGantryRedis。"""


class IOdsSzdnTollService(_ServiceStub):
    """getRedisMap。"""


class HttpSysUtilApiService(_ServiceStub):
    """Forest 声明式 HTTP 客户端替身：syncSuspiciousCarTask(SuspiciousCarVO) → JSONObject。"""


# =============================================================================
# 六、SysUtilServiceImpl：业务逻辑（方法顺序与 Java 源码逐一对齐）
# =============================================================================

class SysUtilServiceImpl:
    """com.ruoyi.base.service.impl.SysUtilServiceImpl 的 Python 版本。

    【Java→Python】Spring 的 @Autowired/@Resource 字段注入 → 构造参数（关键字）注入；
    @Value("${isLocalhost}") → 构造参数 is_localhost（构造期一次性注入，
    与 Java 字段注入完成后再使用该字段的时序保持一致）。
    """

    def __init__(
        self,
        *,
        is_localhost: str = "",
        redis_config: Optional[RedisConfig] = None,
        redis_cache: Optional[RedisCache] = None,
        redis_source_factory: Optional[RedisSourceFactory] = None,
        zdata_trail_tracks_service=None,
        province_border_vehicle_weight_newstructure_service=None,
        snapshot_flow_addcode_service=None,
        provcapture_addcode_service=None,
        stationcapture_addcode_service=None,
        ods_szdn_toll_station_ip_service=None,
        ods_szdn_gantry_ip_service=None,
        fee_records01_service=None,
        fee_station_enter01_service=None,
        fee_station_exit01_service=None,
        zdata_location_dict_service=None,
        fwqclls_service=None,
        fwqjcxx_service=None,
        section_service=None,
        ods_szdn_gantry_service=None,
        ods_szdn_toll_service=None,
        http_sys_util_api_service=None,
    ) -> None:
        self.redis_cache = redis_cache if redis_cache is not None else RedisCache()
        self.redis_source_factory = (
            redis_source_factory if redis_source_factory is not None else RedisSourceFactory()
        )
        self.redis_config = redis_config if redis_config is not None else RedisConfig()
        self.is_localhost = is_localhost

        self.zdata_trail_tracks_service = (
            zdata_trail_tracks_service or IZdataTrailTracksService()
        )
        self.province_border_vehicle_weight_newstructure_service = (
            province_border_vehicle_weight_newstructure_service
            or IOdsSzdnProvinceBorderVehicleWeightNewstructureService()
        )
        self.snapshot_flow_addcode_service = (
            snapshot_flow_addcode_service or IOdsRtSzdnSnapshotFlowAddcodeService()
        )
        self.provcapture_addcode_service = (
            provcapture_addcode_service or IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService()
        )
        self.stationcapture_addcode_service = (
            stationcapture_addcode_service or IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService()
        )
        self.ods_szdn_toll_station_ip_service = (
            ods_szdn_toll_station_ip_service or IOdsSzdnTollStationIpService()
        )
        self.ods_szdn_gantry_ip_service = (
            ods_szdn_gantry_ip_service or IOdsSzdnGantryIpService()
        )
        self.fee_records01_service = fee_records01_service or IOdsLwzxsfsjFeeRecords01Service()
        self.fee_station_enter01_service = (
            fee_station_enter01_service or IOdsLwzxsfsjFeeStationEnter01Service()
        )
        self.fee_station_exit01_service = (
            fee_station_exit01_service or IOdsLwzxsfsjFeeStationExit01Service()
        )
        self.zdata_location_dict_service = (
            zdata_location_dict_service or IZdataLocationDictService()
        )
        self.fwqclls_service = fwqclls_service or IOdsCxztFwqcllsService()
        self.fwqjcxx_service = fwqjcxx_service or IDwdLcztFwqjcxxService()
        self.section_service = section_service or IOdsSzdnSectionService()
        self.ods_szdn_gantry_service = ods_szdn_gantry_service or IOdsSzdnGantryService()
        self.ods_szdn_toll_service = ods_szdn_toll_service or IOdsSzdnTollService()
        self.http_sys_util_api_service = (
            http_sys_util_api_service or HttpSysUtilApiService()
        )

    # -------------------------------------------------------------------------
    # key 生成（Java 中均为 private 方法，命名保持一致便于对照）
    # -------------------------------------------------------------------------

    def get_cache_key(self, config_key: str) -> str:
        """设置cache key。"""
        return CONST_TRAIL + config_key

    def get_suspicious_key(self, cur_data: str, config_key: str) -> str:
        """可疑车辆。"""
        return CONST_CAR_USPICIOUS + cur_data + ":" + config_key

    def snapshot_flow_list_key(self, cur_data: str, config_key: str) -> str:
        """门架抓拍流水。"""
        return CONST_SNAPSHOT_FLOW_LIST + cur_data + ":" + config_key

    def fee_records_list_key(self, cur_data: str, config_key: str) -> str:
        """门架流水key。"""
        return CONST_FEE_RECORDS_LIST + cur_data + ":" + config_key

    def trail_fitting_key(self, cur_data: str, config_key: str) -> str:
        """轨迹点key：有轨迹。"""
        return CONST_TRAIL_FITTING_LIST + cur_data + ":" + config_key

    def trail_un_fitting_key(self, cur_data: str, config_key: str) -> str:
        """轨迹点key：无轨迹。"""
        return CONST_TRAIL_UN_FITTING_LIST + cur_data + ":" + config_key

    # -------------------------------------------------------------------------
    # saveRedis
    # -------------------------------------------------------------------------

    def save_redis(self, sys_util: Any) -> AjaxResult:
        """新增或者修改车辆信息（Java 参数 SysUtil，方法体未使用该参数）。"""
        log.info(
            "获取的配置信息："
            + _java_str(self.redis_config.get_cluster_nodes())
            + "--本地配置："
            + _java_str(self.is_localhost)
        )
        return AjaxResult.success()

    # -------------------------------------------------------------------------
    # syncTrack
    # -------------------------------------------------------------------------

    def sync_track(self, car_para_vo: CarParaVO) -> None:
        """同步轨迹。"""
        carlist: list[CarVO] = []
        obj = self.redis_cache.get_cache_object(CONST_CAR_LIST_JC)
        if obj is not None:
            # 【Java→Python】Java 为 `carlist = (List) obj`；Python 没有泛型擦除，
            # 直接引用即可（缓存层已 deepcopy，修改不会污染缓存中的对象）
            carlist = obj

        # 原代码声明后未使用，保留以保持结构一致；Java 中 Map 以实体作 key，Python 侧不参与键运算
        map_car: dict[ZdataTrailTracks, list[TrailBo]] = {}

        if carlist is not None and len(carlist) > 0:
            log.info(
                "获取的配置信息："
                + _java_str(self.redis_config.get_cluster_nodes())
                + "--本地配置："
                + _java_str(self.is_localhost)
                + "--同步车辆数量："
                + _java_str(len(carlist))
            )
            jedis_cluster = self.redis_source_factory.create_source(self.redis_config)

            # 去掉重合的
            format2 = _FMT_DATETIME
            three_minutes_in_millis = 24 * 60 * 60 * 1000  # 24小时转换为毫秒（变量名沿用原代码）

            for car_vo in carlist:
                car_no = is_null(car_vo.car_no)
                key_value = ""

                if is_null(self.is_localhost) == "local":
                    # 本地
                    key_value = self.redis_cache.get_cache_object(self.get_cache_key(car_no))
                else:
                    # 生产-------------
                    key_value = jedis_cluster.get(self.get_cache_key(car_no))

                josn_list: list[TrailBo] = []
                if is_not_blank(key_value):
                    # 先转 josn 数组 然后循环 一个一个手动赋值
                    array = _json_loads(key_value)
                    for o in array:
                        json_obj = o  # Java: JSONObject jsonObj = (JSONObject) o
                        trail_bo = TrailBo()
                        trail_bo.point_uuid = _json_get_string(json_obj, "pointUuid")
                        trail_bo.state_type = _json_get_string(json_obj, "stateType")
                        trail_bo.capture_time = _json_get_string(json_obj, "captureTime")
                        trail_bo.location_code = _json_get_string(json_obj, "locationCode")
                        trail_bo.location_name = _json_get_string(json_obj, "locationName")
                        trail_bo.standard_code = _json_get_string(json_obj, "standardCode")
                        trail_bo.location_id = _json_get_string(json_obj, "locationId")
                        trail_bo.platenumber = _json_get_string(json_obj, "platenumber")

                        lon = _json_get_string(json_obj, "longitude")
                        lat = _json_get_string(json_obj, "latitude")

                        if is_not_blank(lon):
                            trail_bo.lon = _to_decimal(lon)
                        if is_not_blank(lat):
                            trail_bo.lat = _to_decimal(lat)

                        trail_bo.dev_code = trail_bo.standard_code
                        trail_bo.dev_name = trail_bo.location_name

                        # 判断和当前时间相差24小时就不加
                        if is_null(self.is_localhost) == "local":
                            josn_list.append(trail_bo)
                        else:
                            if is_not_blank(trail_bo.capture_time):
                                try:
                                    capture_time_date1 = _parse_date(format2, trail_bo.capture_time)
                                    capture_time_date2 = datetime.now()
                                    diff = abs(
                                        _millis(capture_time_date2) - _millis(capture_time_date1)
                                    )
                                    if diff <= three_minutes_in_millis:
                                        josn_list.append(trail_bo)
                                except Exception as e:
                                    # Java 的 e.toString() ≙ Python 的 str(e)
                                    log.info("实时轨迹日期解析失败------------" + str(e))

                    rtn_list = self.map_trail_bo_list(josn_list)
                    # 最后一个轨迹点需要查询
                    if rtn_list is not None and len(rtn_list) > 0:
                        formatted_date = datetime.now().strftime(_FMT_DATE_COMPACT)

                        tracks = ZdataTrailTracks()
                        tracks.plate_key = car_no
                        tracks.uuid = car_no + "@@" + formatted_date
                        tracks.flag = "currentTrack"  # 实时轨迹

                        trail_info = self.change_data(tracks, rtn_list)  # 获取设备的经纬度
                        trail_info.trail_uuid = car_no

                        key = CONST_CAR_CURENT_TRAIL + car_no
                        self.redis_cache.set_cache_object(key, trail_info)

    # -------------------------------------------------------------------------
    # changeData
    # -------------------------------------------------------------------------

    def change_data(self, tracks: ZdataTrailTracks, josn_list: list[TrailBo]) -> TrailInfo:
        """数据转换。"""
        trail_info = TrailInfo()

        if josn_list is not None and len(josn_list) > 0:
            pass  # Java 中此处为空 if 块
        else:
            trail_info.tracks = tracks
            trail_info.trail_list = []
            return trail_info

        service_area_capture_uuids = ""  # 服务区抓拍

        for trail_bo in josn_list:
            point_uuid = trail_bo.point_uuid
            state_type = is_null(trail_bo.state_type)
            if state_type == SERVICE_AREA_CAPTURE:
                # 【Java→Python】Java 中 null 参与字符串拼接得到 "null"，这里用 _java_str 等价
                service_area_capture_uuids += _java_str(point_uuid) + ","

        # 服务区抓拍（Java 源码中该段已被注释，这里保留注释以便对照）
        # Map<String, OdsCxztFwqclls> fwqcllsMap = new HashMap<>();
        # serviceAreaCaptureUUids = CommonUtil.deleteEnd(serviceAreaCaptureUUids);
        # if (CommonUtil.isNotBlank(serviceAreaCaptureUUids)) {
        #     fwqcllsMap = fwqcllsService.selectOdsCxztFwqcllsByQueryUuids(serviceAreaCaptureUUids);
        # }

        # 收费站ip
        szdn_toll_map = self.ods_szdn_toll_station_ip_service.selectStationIpMap()

        # 收费站code
        ods_szdn_toll_map = self.ods_szdn_toll_service.getRedisMap()

        # 门架IP
        szdn_gantry_map = self.ods_szdn_gantry_ip_service.selectOdsSzdnGantryIpMap()

        # 位置信息
        location_map = self.zdata_location_dict_service.getRedisList()

        # 服务区信息（原代码注释）
        # Map<String, DwdLcztFwqjcxx> serviceNameMap = fwqjcxxService.getServiceNameMap();

        # 根据路段查询路线map
        section_map = self.section_service.getSectionMap()

        firt_station_code = ""
        # 入栈口名称
        firt_station_name = ""
        # 入栈口时间
        firt_station_time = ""

        # 车牌颜色（字典：1白色2黑色）
        plate_color = ""

        # 车型
        car_type = ""

        # 车种
        car_vehicle = ""

        # 轴数（Long carNum = null）
        car_num: Optional[int] = None

        # 1-OBU 2-CPC卡 3-纸券 9-无通行介质,4- M1卡
        pass_type = ""

        # 查询类型
        index_type = ""

        for trail_bo in josn_list:
            # --------------抓拍信息
            point_uuid = trail_bo.point_uuid
            location_code = is_null(trail_bo.location_code)  # 设备IP地址
            state_type = is_null(trail_bo.state_type)  # 流水来源类型标识

            section_code = is_null(trail_bo.section_code)
            pileno = is_null(trail_bo.pileno)
            lon = trail_bo.lon
            # 【原样保留】Java 源码此处为 `BigDecimal lat = trailBo.getLon();`
            # 即 lat 取的是经度，属于原有缺陷；为保证“一比一”移植，这里同样取 lon。
            lat = trail_bo.lon
            road_code = ""

            # 这个要查询数据库拿---
            if is_not_blank(section_code):
                if section_code in section_map:
                    section = section_map[section_code]
                    road_code = is_null(section.road_code)
                    trail_bo.road_code = road_code

            # Java switch(stateType) 无 default 分支 → if/elif 且不加 else，语义一致
            if state_type == BORDER_WEIGHING_CAPTURE:
                # 省界称重
                index_type = "gantryType"  # 门架
            elif state_type == GANTRY_CAPTURE:
                # 门架抓拍
                index_type = "gantryType"  # 门架
            elif state_type == PROV_CAPTURE:
                # 省界抓拍
                index_type = "gantryType"  # 门架
            elif state_type == SERVICE_AREA_CAPTURE:
                # 服务区抓拍
                index_type = "service_area"  # 服务区
            elif state_type == STATION_CAPTURE:
                # 收费站抓拍
                index_type = "stationType"  # 收费站
            elif state_type == FeeRecord:
                # 卡口流水
                index_type = "gantryType"  # 门架
            elif state_type == FeeStationEnter:
                # 收费站入口流水
                index_type = "stationType"  # 收费站
            elif state_type == FeeStationExit:
                # 收费站出口流水
                index_type = "stationType"  # 收费站

            # ---------------通过位置信息查询设备
            dev_locat_code = ""
            if location_code in location_map:
                dev_locat_code = is_null(location_map[location_code].standard_code)  # 收费站/门架code

            dev_code_id = is_null(trail_bo.dev_code)  # 通过设备编码先查询

            if index_type == "stationType":
                # 收费站ip 或者CODE查询
                station_ip_bo: Optional[OdsSzdnTollStationIp] = None

                # 从位置信息
                if is_not_blank(dev_locat_code):
                    station_ip_bo = szdn_toll_map.get(dev_locat_code)

                # 从设备id拿
                if station_ip_bo is None:
                    if is_not_blank(dev_code_id):
                        station_ip_bo = szdn_toll_map.get(dev_code_id)

                # 从当前位置拿
                if station_ip_bo is None:
                    if is_not_blank(location_code):
                        station_ip_bo = szdn_toll_map.get(location_code)

                if station_ip_bo is not None:
                    trail_bo.dev_code = station_ip_bo.toll_code  # 设备编号
                    trail_bo.dev_name = station_ip_bo.toll_name  # 设备名称

                    ods_szdn_toll = station_ip_bo.ods_szdn_toll
                    if ods_szdn_toll is not None:
                        # 注意：lon/lat 是循环开始时的快照值（Java 语义），赋值后不会回写局部变量
                        if lon is None:
                            # 经度
                            if is_not_blank(ods_szdn_toll.longitude):
                                trail_bo.lon = _to_decimal(ods_szdn_toll.longitude)

                        if lat is None:
                            # 经度（原注释如此）
                            if is_not_blank(ods_szdn_toll.latitude):
                                trail_bo.lat = _to_decimal(ods_szdn_toll.latitude)

                        if is_blank(road_code):
                            # 路线编号
                            trail_bo.road_code = is_null(ods_szdn_toll.road_code)

                        if is_blank(section_code):
                            # 路段
                            trail_bo.section_code = is_null(ods_szdn_toll.section_code)

                        if is_blank(pileno):
                            # 桩号
                            trail_bo.pileno = is_null(ods_szdn_toll.pile_no)

                        # trailBo.setDirection(odsSzdnToll.getDirection()); // 方向（原代码注释）

            elif index_type == "gantryType":
                # 门架ip
                gantry_ip_bo: Optional[OdsSzdnGantryIp] = None

                # 从位置信息
                if is_not_blank(dev_locat_code):
                    gantry_ip_bo = szdn_gantry_map.get(dev_locat_code)

                # 从设备id拿
                if gantry_ip_bo is None:
                    if is_not_blank(dev_code_id):
                        gantry_ip_bo = szdn_gantry_map.get(dev_code_id)

                # 从当前位置拿
                if gantry_ip_bo is None:
                    if is_not_blank(location_code):
                        gantry_ip_bo = szdn_gantry_map.get(location_code)

                if gantry_ip_bo is not None:
                    trail_bo.dev_code = gantry_ip_bo.gantry_code  # 设备编号
                    trail_bo.dev_name = gantry_ip_bo.gantry_name  # 设备名称

                    ods_szdn_gantry = gantry_ip_bo.ods_szdn_gantry
                    if ods_szdn_gantry is not None:
                        if lon is None:
                            # 经度
                            if is_not_blank(ods_szdn_gantry.lon):
                                trail_bo.lon = _to_decimal(ods_szdn_gantry.lon)

                        if lat is None:
                            # 经度（原注释如此）
                            if is_not_blank(ods_szdn_gantry.lat):
                                trail_bo.lat = _to_decimal(ods_szdn_gantry.lat)

                        if is_blank(road_code):
                            # 路线编号
                            trail_bo.road_code = is_null(ods_szdn_gantry.road_code)

                        if is_blank(section_code):
                            # 路段编号
                            trail_bo.section_code = is_null(ods_szdn_gantry.section_code)

                        if is_blank(pileno):
                            # 桩号
                            trail_bo.pileno = is_null(ods_szdn_gantry.pile_no)

                        trail_bo.direction = ods_szdn_gantry.direction  # 方向
                        trail_bo.is_virtual = ods_szdn_gantry.is_virtual  # 虚拟门架

            elif index_type == "service_area":
                # 服务区
                location_code = location_code.replace("devip:", "serviceip:")
                if location_code in location_map:
                    location_dict = location_map[location_code]

                    trail_bo.dev_code = location_dict.standard_code  # 设备编号
                    trail_bo.dev_name = location_dict.name  # 设备名称

                    # 经度
                    if location_dict.longitude is not None:
                        trail_bo.lon = location_dict.longitude

                    # 经度（原注释如此，实际赋的是纬度）
                    if location_dict.latitude is not None:
                        trail_bo.lat = location_dict.latitude

                    # 路线编号
                    trail_bo.road_code = is_null(location_dict.roadcode)
                    # 路段
                    trail_bo.section_code = is_null(location_dict.sectioncode)
                    # 桩号
                    trail_bo.pileno = is_null(location_dict.pile_no)
                    trail_bo.direction = location_dict.direction  # 方向

            # 设备名称没有默认位置信息--------------
            if is_blank(trail_bo.dev_name):
                trail_bo.dev_name = is_null(location_code).replace("serviceip:", "")

        tracks.firt_station_code = firt_station_code
        tracks.firt_station_name = firt_station_name
        tracks.firt_station_time = firt_station_time
        tracks.plate_color = plate_color
        tracks.car_type = car_type
        tracks.car_vehicle = car_vehicle
        tracks.car_num = car_num
        tracks.pass_type = pass_type

        # -------------------------获取起点 终点 的经纬度
        jwd_list: list[TrailBo] = []
        if josn_list is not None and len(josn_list) > 0:
            for trail_bo in josn_list:
                if trail_bo.lon is not None and trail_bo.lat is not None:
                    jwd_list.append(trail_bo)

        if is_null(tracks.flag) == "currentTrack":
            # 实时轨迹
            if jwd_list is not None and len(jwd_list) > 0:
                first_trail_bo = jwd_list[0]

                tracks.entollstationid = is_null(first_trail_bo.dev_code)
                tracks.entollstationname = is_null(first_trail_bo.dev_name)
                tracks.start_lon = is_null(first_trail_bo.lon)  # 经度
                tracks.strat_lat = is_null(first_trail_bo.lat)  # 经度（原注释如此）

                if len(jwd_list) > 1:
                    end_trail_bo = jwd_list[len(jwd_list) - 1]
                    tracks.extollstationid = is_null(end_trail_bo.dev_code)
                    tracks.extollstationname = is_null(end_trail_bo.dev_name)
                    tracks.end_lon = is_null(end_trail_bo.lon)  # 经度
                    tracks.end_lat = is_null(end_trail_bo.lat)  # 经度
        else:
            # 历史轨迹：
            first_code = is_null(tracks.entollstationid)  # 入口收费站编号
            first_name = repalace_szdn_toll_name(tracks.entollstationname)  # 入口收费站名称
            end_code = is_null(tracks.extollstationid)  # 出口收费站编号
            end_name = repalace_szdn_toll_name(tracks.extollstationname)  # 出口收费站名称

            if is_not_blank(first_code):
                # 收费站ip
                if first_code in ods_szdn_toll_map:
                    ods_szdn_toll = ods_szdn_toll_map.get(first_code)
                    if ods_szdn_toll is not None:
                        if is_not_blank(ods_szdn_toll.longitude):
                            tracks.start_lon = ods_szdn_toll.longitude  # 经度
                        if is_not_blank(ods_szdn_toll.latitude):
                            tracks.strat_lat = ods_szdn_toll.latitude  # 经度
                        tracks.entollstationid = is_null(ods_szdn_toll.toll_code)
                else:
                    # 门架
                    if first_code in szdn_gantry_map:
                        gantry_ip_bo = szdn_gantry_map.get(first_code)
                        ods_szdn_gantry = gantry_ip_bo.ods_szdn_gantry
                        if ods_szdn_gantry is not None:
                            if is_not_blank(ods_szdn_gantry.lon):
                                tracks.start_lon = ods_szdn_gantry.lon  # 经度
                            if is_not_blank(ods_szdn_gantry.lat):
                                tracks.strat_lat = ods_szdn_gantry.lat  # 经度

            # --------- 如果拿不到就根据名称来拿
            if is_blank(tracks.start_lon):
                if is_not_blank(first_name):
                    # 收费站ip
                    if first_name in szdn_toll_map:
                        station_ip_bo = szdn_toll_map.get(first_name)
                        ods_szdn_toll = station_ip_bo.ods_szdn_toll
                        if ods_szdn_toll is not None:
                            if is_not_blank(ods_szdn_toll.longitude):
                                tracks.start_lon = ods_szdn_toll.longitude  # 经度
                            if is_not_blank(ods_szdn_toll.latitude):
                                tracks.strat_lat = ods_szdn_toll.latitude  # 经度
                        tracks.entollstationid = is_null(station_ip_bo.toll_code)
                    else:
                        # 门架
                        if first_name in szdn_gantry_map:
                            gantry_ip_bo = szdn_gantry_map.get(first_name)
                            ods_szdn_gantry = gantry_ip_bo.ods_szdn_gantry
                            if ods_szdn_gantry is not None:
                                if is_not_blank(ods_szdn_gantry.lon):
                                    tracks.start_lon = ods_szdn_gantry.lon  # 经度
                                if is_not_blank(ods_szdn_gantry.lat):
                                    tracks.strat_lat = ods_szdn_gantry.lat  # 经度
                            tracks.entollstationid = is_null(gantry_ip_bo.gantry_code)

            if is_not_blank(end_code):
                # 收费站ip
                if end_code in ods_szdn_toll_map:
                    ods_szdn_toll = ods_szdn_toll_map.get(end_code)
                    if ods_szdn_toll is not None:
                        if is_not_blank(ods_szdn_toll.longitude):
                            tracks.end_lon = ods_szdn_toll.longitude  # 经度
                        if is_not_blank(ods_szdn_toll.latitude):
                            tracks.end_lat = ods_szdn_toll.latitude  # 经度
                        tracks.extollstationid = is_null(ods_szdn_toll.toll_code)
                else:
                    # 门架
                    if end_code in szdn_gantry_map:
                        gantry_ip_bo = szdn_gantry_map.get(end_code)
                        ods_szdn_gantry = gantry_ip_bo.ods_szdn_gantry
                        if ods_szdn_gantry is not None:
                            if is_not_blank(ods_szdn_gantry.lon):
                                tracks.end_lon = ods_szdn_gantry.lon  # 经度
                            if is_not_blank(ods_szdn_gantry.lat):
                                tracks.end_lat = ods_szdn_gantry.lat  # 经度

            # --------- 如果拿不到就根据名称来拿
            if is_blank(tracks.end_lon):
                if is_not_blank(end_name):
                    # 收费站ip
                    if end_name in szdn_toll_map:
                        station_ip_bo = szdn_toll_map.get(end_name)
                        ods_szdn_toll = station_ip_bo.ods_szdn_toll
                        if ods_szdn_toll is not None:
                            if is_not_blank(ods_szdn_toll.longitude):
                                tracks.end_lon = ods_szdn_toll.longitude  # 经度
                            if is_not_blank(ods_szdn_toll.latitude):
                                tracks.end_lat = ods_szdn_toll.latitude  # 经度
                        tracks.extollstationid = is_null(station_ip_bo.toll_code)
                    else:
                        # 门架
                        if end_name in szdn_gantry_map:
                            gantry_ip_bo = szdn_gantry_map.get(end_name)
                            ods_szdn_gantry = gantry_ip_bo.ods_szdn_gantry
                            if ods_szdn_gantry is not None:
                                if is_not_blank(ods_szdn_gantry.lon):
                                    tracks.end_lon = ods_szdn_gantry.lon  # 经度
                                if is_not_blank(ods_szdn_gantry.lat):
                                    tracks.end_lat = ods_szdn_gantry.lat  # 经度
                            tracks.extollstationid = is_null(gantry_ip_bo.gantry_code)

            # 如果获取的经纬度为空的话（Java 源码中该段已被注释）

        if is_not_blank(tracks.start_lon):
            tracks.start_lon_dec = _to_decimal(tracks.start_lon)
        if is_not_blank(tracks.strat_lat):
            tracks.strat_lat_dec = _to_decimal(tracks.strat_lat)
        if is_not_blank(tracks.end_lon):
            tracks.end_lon_dec = _to_decimal(tracks.end_lon)
        if is_not_blank(tracks.end_lat):
            tracks.end_lat_dec = _to_decimal(tracks.end_lat)

        trail_info.tracks = tracks
        trail_info.trail_list = josn_list

        return trail_info

    # -------------------------------------------------------------------------
    # getByTrailBo
    # -------------------------------------------------------------------------

    def get_by_trail_bo(self, trail_bo: TrailBo) -> TrailBo:
        """获取抓拍对象。"""
        if trail_bo is None:
            return TrailBo()

        border_weighing_capture_uuids = ""  # 省界称重
        gantry_capture_uuids = ""  # 门架抓拍
        prov_capture_uuids = ""  # 省界抓拍
        service_area_capture_uuids = ""  # 服务区抓拍
        station_capture_uuids = ""  # 收费站抓拍
        fee_record_uuids = ""  # 卡口流水
        fee_station_enter_uuids = ""  # 收费站入口流水
        fee_station_exit_uuids = ""  # 收费站出口流水

        capture_time = is_null(trail_bo.capture_time)
        apply_time1 = ""
        apply_time2 = ""
        if is_not_blank(capture_time):
            # 获取开始时间
            format2 = _FMT_DATE
            try:
                capture_time_date1 = _parse_date(format2, capture_time)
                base_query_time = _format_date(format2, capture_time_date1)
                apply_time1 = base_query_time + " 00:00:00"
                apply_time2 = base_query_time + " 23:59:59"
            except Exception as e:
                log.info("日期解析失败------------" + str(e))

        state_type = is_null(trail_bo.state_type)
        point_uuid = trail_bo.point_uuid

        if state_type == BORDER_WEIGHING_CAPTURE:
            # 省界称重
            border_weighing_capture_uuids += _java_str(point_uuid) + ","
        elif state_type == GANTRY_CAPTURE:
            # 门架抓拍
            gantry_capture_uuids += _java_str(point_uuid) + ","
        elif state_type == PROV_CAPTURE:
            # 省界抓拍
            prov_capture_uuids += _java_str(point_uuid) + ","
        elif state_type == SERVICE_AREA_CAPTURE:
            # 服务区抓拍
            service_area_capture_uuids += _java_str(point_uuid) + ","
        elif state_type == STATION_CAPTURE:
            # 收费站抓拍
            station_capture_uuids += _java_str(point_uuid) + ","
        elif state_type == FeeRecord:
            # 卡口流水（Java 中拼接语句已注释）
            # feeRecordUUids += pointUuid + ",";
            pass
        elif state_type == FeeStationEnter:
            # 收费站入口流水（Java 中拼接语句已注释）
            # feeStationEnterUUids += pointUuid + ",";
            pass
        elif state_type == FeeStationExit:
            # 收费站出口流水（Java 中拼接语句已注释）
            # feeStationExitUUids += pointUuid + ",";
            pass

        # 省界称重
        weight_newstructure_map: dict[str, OdsSzdnProvinceBorderVehicleWeightNewstructure] = {}
        border_weighing_capture_uuids = delete_end(border_weighing_capture_uuids)
        if is_not_blank(border_weighing_capture_uuids):
            weight_newstructure_map = self.province_border_vehicle_weight_newstructure_service \
                .selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(
                    border_weighing_capture_uuids
                )

        # 门架抓拍
        snapshot_flow_addcode_map: dict[str, OdsRtSzdnSnapshotFlowAddcode] = {}
        gantry_capture_uuids = delete_end(gantry_capture_uuids)
        if is_not_blank(gantry_capture_uuids):
            snapshot_flow_addcode_map = self.snapshot_flow_addcode_service \
                .selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(
                    gantry_capture_uuids, apply_time1, apply_time2
                )

        # 省界抓拍
        provcapture_addcode_map: dict[str, OdsRtSzdnSnapshotFlowProvcaptureAddcode] = {}
        prov_capture_uuids = delete_end(prov_capture_uuids)
        if is_not_blank(prov_capture_uuids):
            provcapture_addcode_map = self.provcapture_addcode_service \
                .selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(prov_capture_uuids)

        # 服务区抓拍
        fwqclls_map: dict[str, OdsCxztFwqclls] = {}
        service_area_capture_uuids = delete_end(service_area_capture_uuids)
        if is_not_blank(service_area_capture_uuids):
            fwqclls_map = self.fwqclls_service.selectOdsCxztFwqcllsByQueryUuids(
                service_area_capture_uuids
            )

        # 收费站抓拍
        stationcapture_addcode_map: dict[str, OdsRtSzdnSnapshotFlowStationcaptureAddcode] = {}
        station_capture_uuids = delete_end(station_capture_uuids)
        if is_not_blank(station_capture_uuids):
            stationcapture_addcode_map = self.stationcapture_addcode_service \
                .selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(
                    station_capture_uuids, apply_time1, apply_time2
                )

        # 卡口流水
        fee_record_map: dict[str, OdsLwzxsfsjFeeRecords01] = {}
        fee_record_uuids = delete_end(fee_record_uuids)
        if is_not_blank(fee_record_uuids):
            fee_record_map = self.fee_records01_service.selectOdsLwzxsfsjFeeRecords01ByQueryUuids(
                fee_record_uuids, apply_time1, apply_time2
            )

        # 收费站入口流水
        fee_station_enter_map: dict[str, OdsLwzxsfsjFeeStationEnter01] = {}
        fee_station_enter_uuids = delete_end(fee_station_enter_uuids)
        if is_not_blank(fee_station_enter_uuids):
            fee_station_enter_map = self.fee_station_enter01_service \
                .selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids(fee_station_enter_uuids)

        # 收费站入口流水（原注释如此，实为出口）
        fee_station_exit_map: dict[str, OdsLwzxsfsjFeeStationExit01] = {}
        fee_station_exit_uuids = delete_end(fee_station_exit_uuids)
        if is_not_blank(fee_station_exit_uuids):
            fee_station_exit_map = self.fee_station_exit01_service \
                .selectOdsLwzxsfsjFeeStationExit01ByQueryUuids(fee_station_exit_uuids)

        if state_type == BORDER_WEIGHING_CAPTURE:
            # 省界称重
            if point_uuid in weight_newstructure_map:
                border_weighing_capture_bo = weight_newstructure_map.get(point_uuid)

                # 抓拍照片
                images_str = is_null(border_weighing_capture_bo.weighing_images_arry)
                if is_not_blank(images_str):
                    images_src = ""
                    imges_json_array = _json_loads(images_str)
                    # Java 用下标 for 循环（zz < imgesJsonArray.size()），此处保持一致
                    for zz in range(len(imges_json_array)):
                        image_temp_josn = imges_json_array[zz]
                        # 【Java→Python】getJSONObject(zz) 对非对象元素返回 null，这里等价处理
                        if isinstance(image_temp_josn, dict):
                            temp_image_src = is_null(
                                _json_get_string(image_temp_josn, "snapPicturePath")
                            )
                            if is_not_blank(temp_image_src):
                                images_src += temp_image_src + ","
                    trail_bo.images_arry = delete_end(images_src)  # 抓拍照片
        elif state_type == GANTRY_CAPTURE:
            if point_uuid in snapshot_flow_addcode_map:
                gantry_capture_bo = snapshot_flow_addcode_map.get(point_uuid)
                trail_bo.images_arry = gantry_capture_bo.snappicturepath  # 抓拍照片
                # 车牌颜色
                trail_bo.platecolor = is_null(gantry_capture_bo.platecolor)
        elif state_type == PROV_CAPTURE:
            # 省界抓拍
            if point_uuid in provcapture_addcode_map:
                images_src = ""
                prov_capture_bo = provcapture_addcode_map.get(point_uuid)
                # 车牌图路径
                if is_not_blank(prov_capture_bo.plateimage):
                    images_src += prov_capture_bo.plateimage + ","
                # 车身图路径
                if is_not_blank(prov_capture_bo.sideimage):
                    images_src += prov_capture_bo.sideimage + ","
                # 车头图路径
                if is_not_blank(prov_capture_bo.headimage):
                    images_src += prov_capture_bo.headimage + ","
                trail_bo.images_arry = delete_end(images_src)  # 抓拍照片
        elif state_type == SERVICE_AREA_CAPTURE:
            # 服务区抓拍
            if point_uuid in fwqclls_map:
                fwqclls = fwqclls_map.get(point_uuid)
                images_src = ""
                # 抓拍照片url
                if is_not_blank(fwqclls.targetpicurl):
                    images_src += fwqclls.targetpicurl + ","
                # 车牌照片
                if is_not_blank(fwqclls.platepicurl):
                    images_src += fwqclls.platepicurl + ","
                # 抓拍照片
                trail_bo.images_arry = delete_end(images_src)
        elif state_type == STATION_CAPTURE:
            # 收费站抓拍
            if point_uuid in stationcapture_addcode_map:
                station_capture = stationcapture_addcode_map.get(point_uuid)
                trail_bo.images_arry = station_capture.snappicturepath  # 抓拍照片
        elif state_type == FeeRecord:
            # 卡口流水
            if point_uuid in fee_record_map:
                fee_records = fee_record_map.get(point_uuid)
                trail_bo.dev_code = fee_records.gantryid  # 设备编号
                trail_bo.images_arry = ""  # 抓拍照片
        elif state_type == FeeStationEnter:
            # 收费站入口流水
            if point_uuid in fee_station_enter_map:
                # Java 中取出的对象未使用，这里保留变量以保持结构一致
                fee_station_enter = fee_station_enter_map.get(point_uuid)
                trail_bo.images_arry = ""  # 抓拍照片
        elif state_type == FeeStationExit:
            # 收费站出口流水
            if point_uuid in fee_station_exit_map:
                fee_station_exit = fee_station_exit_map.get(point_uuid)
                trail_bo.images_arry = ""  # 抓拍照片

        # 图片替换----
        images_arry = delete_end(trail_bo.images_arry)
        trail_bo.images_arry = repalace_pic_url(images_arry)

        return trail_bo

    # -------------------------------------------------------------------------
    # syncSuspiciousCar
    # -------------------------------------------------------------------------

    def sync_suspicious_car(self, car_para_vo: CarParaVO) -> dict[ZdataTrailTracks, list[TrailBo]]:
        """同步可疑车俩（Java 原样：直接返回空 Map）。"""
        return {}

    # -------------------------------------------------------------------------
    # syncSuspiciousCarQutaz
    # -------------------------------------------------------------------------

    def sync_suspicious_car_qutaz(self, start_num: int, end_num: int) -> None:
        """同步可疑车俩：定时（startNum 起始页面 1，最后页面 10）。"""
        page_size = 10
        star_time = 2
        end_time = 4
        bite = Decimal("0.3")  # 门架抓拍和流水抓拍占比

        supoer_mjnum_value_int = 5  # 跨省：同步可疑车辆门架抓拍数量5个以上
        road_supoer_mjnum_int = 3  # 路段：门架抓拍数量和门架流水数量对比

        # -------------- 从缓存取得对应的配置
        redis_time_value = self.redis_cache.get_cache_object(redisTimeKey)  # 默认2天
        if is_not_blank(redis_time_value):
            # 【Java→Python】Java 为 Integer.parseInt(String)；Python int() 同时接受 int/str
            star_time = int(redis_time_value)
            log.info("从缓存取得时间配置--------：" + _java_str(redis_time_value))

        redis_bite_value = self.redis_cache.get_cache_object(redisBiteKey)  # 比例默认为0.3
        if is_not_blank(redis_bite_value):
            bite = _to_decimal(redis_bite_value)
            log.info("从缓存取得占比配置------：" + _java_str(bite))

        supoer_mjnum_value = self.redis_cache.get_cache_object(supoer_mjnum)  # 比例默认为5
        if is_not_blank(supoer_mjnum_value):
            supoer_mjnum_value_int = int(supoer_mjnum_value)
            log.info("从缓存取得跨省：门架抓拍数量------：" + _java_str(supoer_mjnum_value_int))

        road_supoe_mjnum_value = self.redis_cache.get_cache_object(road_supoer_mjnum)  # 比例默认为3
        if is_not_blank(road_supoe_mjnum_value):
            road_supoer_mjnum_int = int(road_supoe_mjnum_value)
            log.info("从缓存路段：取得门架抓拍数量------：" + _java_str(road_supoe_mjnum_value))

        # 判断节假日
        jholiday_time_value = is_null(self.redis_cache.get_cache_object(jholiday_time))  # 节假日
        log.info("从缓存路段：取得节假日------：" + jholiday_time_value)

        if is_null(self.is_localhost) == "local":
            log.info("本地配置------：" + is_null(self.is_localhost))
            # 本地  分页1000条 30 到 1 天
            page_size = 2000
            end_time = star_time * 2
        else:
            log.info("生产配置------：" + is_null(self.is_localhost))
            # 生产------------- 分页1000条 14 到 7 天
            page_size = 2000
            end_time = star_time * 2

        log.info(
            "分页配置："
            + _java_str(page_size)
            + "--时间范围"
            + _java_str(star_time)
            + "到"
            + _java_str(end_time)
        )

        car_para_vo = CarParaVO()
        # ----------7 到 14天
        car_para_vo.star_time = star_time
        car_para_vo.end_time = end_time

        gantry_list = self.ods_szdn_gantry_service.getGantryRedis()
        gantry_mao: dict[str, OdsSzdnGantry] = {}
        for rtn_ods_szdn_gantry in gantry_list:
            gantry_mao[is_null(rtn_ods_szdn_gantry.gantry_code)] = rtn_ods_szdn_gantry

        # 位置信息
        location_map = self.zdata_location_dict_service.getRedisList()

        # 根据路段查询路线map
        section_map = self.section_service.getSectionMap()

        # 查询路段list
        sectionlist = self.section_service.getSectionList()

        # 筛选的路段信息-------------
        index_section_code = "200R500450649000"  # 泰赣路段编码
        index_section_name = "泰赣路段"  # 泰赣路段
        index_road_code_map: dict[str, str] = {}
        sections_query_list: list[str] = []
        for ods_szdn_section in sectionlist:
            road_code = is_null(ods_szdn_section.road_code)  # 路线
            section_code = is_null(ods_szdn_section.section_code)  # 路段编码
            if is_not_blank(road_code) and is_not_blank(section_code):
                # 大广高速
                if section_code == index_section_code:
                    sections_query_list.append(section_code)
                    index_road_code_map[section_code] = road_code

        section_code_list: list[str] = []
        section_code_list.append(index_section_code)

        # -------可疑车辆存储时间
        now = datetime.now()
        formatted_date = now.strftime(_FMT_DATE_COMPACT)

        # -------获取当前时间的前2天
        current_date = datetime.now()
        # 【Java→Python】Calendar.add(DAY_OF_MONTH, -N) ≙ 直接减去 timedelta(days=N)
        two_days_ago = current_date + timedelta(days=-star_time)
        query_date = two_days_ago.strftime(_FMT_DATE)

        query_start_time = query_date + " 00:00:00"
        query_end_time = query_date + " 23:59:59"
        log.info("查询时间范围" + query_start_time + "到" + query_end_time)

        # 门架抓拍流水
        snapshot_flow = OdsRtSzdnSnapshotFlowAddcode()
        snapshot_flow.platecolor = "黄色"
        snapshot_flow.section_list = section_code_list
        snapshot_flow.apply_time1 = query_start_time
        snapshot_flow.apply_time2 = query_end_time

        # 门架交易流水
        fee_records01 = OdsLwzxsfsjFeeRecords01()
        fee_records01.plate_color = "_1"
        fee_records01.section_list = section_code_list
        fee_records01.in_apply_time1 = query_start_time
        fee_records01.in_apply_time2 = query_end_time

        # 是否不是节假日
        is_not_exitsjholiday_flag = True
        if query_date in jholiday_time_value:
            is_not_exitsjholiday_flag = False

        for i in range(start_num, end_num + 1):
            # ----- 分页范围 ： 2000一次性查询
            car_para_vo.start_num = page_size
            if i > 1:
                end_range = (i - 1) * page_size  # 当前页 -1
                car_para_vo.end_num = end_range

            # 查询门架抓拍流水
            snapshot_flow.start_num = car_para_vo.start_num
            snapshot_flow.end_num = car_para_vo.end_num
            self.sync_snapshot_flow(snapshot_flow)

            # 门架交易流水
            fee_records01.start_num = car_para_vo.start_num
            fee_records01.end_num = car_para_vo.end_num
            self.sync_fee_records(fee_records01)

            # -------------轨迹点6000一次查询
            page_size_new = 6000
            car_para_vo.start_num = page_size_new
            if i > 1:
                end_range = (i - 1) * page_size_new  # 当前页 -1
                car_para_vo.end_num = end_range

            car_para_vo.apply_time1 = query_start_time
            car_para_vo.apply_time2 = query_end_time
            # 【Java→Python】new Date() 的 toString 与 str(datetime) 文本不同，仅影响日志内容
            log.info("轨迹点SQL开始查询----------" + _java_str(datetime.now()))
            carlist_all = self.zdata_trail_tracks_service.getLatestTrail(car_para_vo)
            log.info(
                "轨迹点SQL结束查询----------"
                + _java_str(datetime.now())
                + "--数据："
                + _java_str(len(carlist_all))
            )

            # ---------------------------------- 跨省全程屏蔽
            carlist_qspb: list[ZdataTrailTracks] = []
            # ---------------------------------- 关注路段屏蔽
            carlist_ldpb: list[ZdataTrailTracks] = []

            for zdata_trail_tracks_vo in carlist_all:
                trailtype = is_null(zdata_trail_tracks_vo.trailtype)

                first_code = is_null(zdata_trail_tracks_vo.entollstationid)  # 入口收费站编号
                first_name = repalace_szdn_toll_name(
                    zdata_trail_tracks_vo.entollstationname
                )  # 入口收费站名称
                end_code = is_null(zdata_trail_tracks_vo.extollstationid)  # 出口收费站编号
                end_name = repalace_szdn_toll_name(
                    zdata_trail_tracks_vo.extollstationname
                )  # 出口收费站名称

                car_no = is_null(zdata_trail_tracks_vo.plate_key)

                # 外省进 外省出的车
                # 【Java→Python】String.indexOf(x) > -1 ≙ x in string
                if trailtype == "0" and "门架" in first_name and "门架" in end_name:
                    if is_not_exitsjholiday_flag:
                        carlist_qspb.append(zdata_trail_tracks_vo)
                else:
                    # 判断是否包含大广路段
                    key_value = zdata_trail_tracks_vo.trail_points  # 行驶轨迹
                    if is_not_blank(key_value):
                        exflag = False
                        for section_code_value in sections_query_list:
                            if section_code_value in key_value:
                                exflag = True
                        if exflag:
                            if is_not_exitsjholiday_flag:
                                carlist_ldpb.append(zdata_trail_tracks_vo)
                            trail_tracks_vo = TrailTracksVo()
                            trail_tracks_vo.plate_key = car_no
                            trail_tracks_vo.enter_time = zdata_trail_tracks_vo.enter_time
                            trail_tracks_vo.exit_time = zdata_trail_tracks_vo.exit_time

                            # 按照车牌存放当天轨迹
                            key_list: list[TrailTracksVo] = []

                            trail_fitting_redis_key = self.trail_fitting_key(formatted_date, car_no)
                            old_fitting_list = self.redis_cache.get_cache_object(
                                trail_fitting_redis_key
                            )
                            if old_fitting_list is not None and len(old_fitting_list) > 0:
                                key_list = old_fitting_list
                            key_list.append(trail_tracks_vo)

                            self.redis_cache.set_cache_object(trail_fitting_redis_key, key_list)

            # ---------------------------------- 跨省全程屏蔽
            if carlist_qspb is not None and len(carlist_qspb) > 0:
                for tracks in carlist_qspb:
                    car_no = is_null(tracks.plate_key)
                    key_value = tracks.trail_points  # 行驶轨迹
                    escaped_type = ""
                    josn_list: list[TrailBo] = []
                    if is_not_blank(key_value):
                        josn_list = self.get_trail_bo_list(key_value)
                        tracks.trail_points = ""  # 行驶轨迹
                        # ---------------------------分析场景: 门架抓拍和流水抓拍 占比
                        conut_gantry_capture = 0
                        conut_fee_record = 0
                        for rtn_trail_bo in josn_list:
                            state_type = is_null(rtn_trail_bo.state_type)
                            if state_type == GANTRY_CAPTURE:
                                # 门架抓拍
                                conut_gantry_capture += 1
                            elif state_type == FeeRecord:
                                # 卡口流水
                                conut_fee_record += 1

                        # ---------------屏蔽:
                        if conut_gantry_capture > supoer_mjnum_value_int:
                            escaped_type_remark = ""
                            add_flag = False
                            if conut_fee_record == 0:
                                escaped_type_remark = (
                                    "跨省全程屏蔽：其中门架牌识流水数量:"
                                    + _java_str(conut_gantry_capture)
                                    + "，门架交易流水数量:"
                                    + _java_str(conut_fee_record)
                                    + "。"
                                )
                                add_flag = True
                            if add_flag:
                                escaped_type = CONST_ESCAPED_TYPE_20
                                tracks.escaped_type = escaped_type  # 屏蔽
                                tracks.escaped_type_remark = escaped_type_remark
                                tracks.escaped_tfcj = "1"  # 逃费场景

                                trail_info = self.change_data(tracks, josn_list)  # 获取设备的经纬度

                                # 判断门架抓拍是否经过了虚拟门架
                                if self.get_is_virtual_flag(trail_info.trail_list):
                                    # 车牌颜色
                                    tracks.plate_color = self.get_plate_color(trail_info.trail_list)
                                    trail_info.trail_uuid = car_no

                                    key = self.get_suspicious_key(formatted_date, car_no)
                                    self.redis_cache.set_cache_object(key, trail_info)

            # ---------------------------------- 关注路段屏蔽
            if carlist_ldpb is not None and len(carlist_ldpb) > 0:
                for tracks in carlist_ldpb:
                    car_no = is_null(tracks.plate_key)
                    key_value = tracks.trail_points  # 行驶轨迹
                    escaped_type = ""
                    josn_list: list[TrailBo] = []
                    if is_not_blank(key_value):
                        josn_list = self.get_trail_bo_list(key_value)
                        tracks.trail_points = ""  # 行驶轨迹

                        # ---------------------------分析场景: 路段抓拍和流水抓拍 占比
                        conut_gantry_capture = 0
                        conut_fee_record = 0

                        for rtn_trail_bo in josn_list:
                            section_code = is_null(rtn_trail_bo.section_code)  # 路段信息
                            state_type = is_null(rtn_trail_bo.state_type)

                            if is_not_blank(section_code):
                                if section_code in index_road_code_map:
                                    if state_type == GANTRY_CAPTURE:
                                        # 门架抓拍
                                        conut_gantry_capture += 1
                                    elif state_type == FeeRecord:
                                        # 卡口流水
                                        conut_fee_record += 1
                        # 该路段门架比例一定的数值---------
                        if conut_gantry_capture > road_supoer_mjnum_int:
                            escaped_type_remark = ""
                            add_flag = False
                            if conut_fee_record == 0:
                                escaped_type_remark = (
                                    index_section_name
                                    + "全程屏蔽：其中门架牌识流水数量:"
                                    + _java_str(conut_gantry_capture)
                                    + "，门架交易流水数量:"
                                    + _java_str(conut_fee_record)
                                    + "。"
                                )
                                add_flag = True

                            if add_flag:
                                escaped_type = CONST_ESCAPED_TYPE_20
                                tracks.escaped_type = escaped_type  # 屏蔽
                                tracks.escaped_type_remark = escaped_type_remark
                                tracks.escaped_tfcj = "2"  # 路段屏蔽

                                trail_info = self.change_data(tracks, josn_list)  # 获取设备的经纬度

                                # 判断门架抓拍是否经过了虚拟门架
                                if self.get_is_virtual_flag(trail_info.trail_list):
                                    # 车牌颜色
                                    tracks.plate_color = self.get_plate_color(trail_info.trail_list)
                                    trail_info.trail_uuid = car_no

                                    key = self.get_suspicious_key(formatted_date, car_no)
                                    self.redis_cache.set_cache_object(key, trail_info)

    # -------------------------------------------------------------------------
    # syncSuspiciousCarQutazNew
    # -------------------------------------------------------------------------

    def sync_suspicious_car_qutaz_new(self, start_num: int, end_num: int) -> None:
        """同步可疑车俩：定时（startNum 起始页面 1，最后页面 10）。"""
        page_size = 10
        star_time = 2
        end_time = 4

        # 【Java→Python】Java 中该局部变量与静态常量 supoer_mjnum（Redis key）同名，
        # 方法内以局部变量为准；Python 同样以局部变量遮蔽模块常量。
        supoer_mjnum = 5  # 跨省：同步可疑车辆门架抓拍数量5个以上

        # -------------- 从缓存取得对应的配置（Java 源码中整段已被注释）
        # String redisTimeValue = redisCache.getCacheObject(redisTimeKey);
        # ...
        # String supoerMjnumValue = redisCache.getCacheObject(supoer_mjnum);
        # ...

        # 判断节假日
        jholiday_time_value = "2025-01-01,2025-01-02,2025-01-03"  # 节假日

        if is_null(self.is_localhost) == "local":
            log.info("本地配置------：" + is_null(self.is_localhost))
            # 本地  分页1000条 30 到 1 天
            page_size = 6000
            end_time = star_time * 2
        else:
            log.info("生产配置------：" + is_null(self.is_localhost))
            # 生产------------- 分页1000条 14 到 7 天
            page_size = 6000
            end_time = star_time * 2

        car_para_vo = CarParaVO()
        # ----------7 到 14天
        car_para_vo.star_time = star_time
        car_para_vo.end_time = end_time

        # 门架
        gantry_list = self.ods_szdn_gantry_service.getGantryRedis()
        gantry_mao: dict[str, OdsSzdnGantry] = {}
        for rtn_ods_szdn_gantry in gantry_list:
            gantry_mao[is_null(rtn_ods_szdn_gantry.gantry_code)] = rtn_ods_szdn_gantry

        # 位置信息
        location_map = self.zdata_location_dict_service.getRedisList()

        # 根据路段查询路线map（Java 中声明后未使用，保留以保持结构一致）
        section_map = self.section_service.getSectionMap()

        # -------可疑车辆存储时间
        now = datetime.now()
        formatted_date = now.strftime(_FMT_DATE_COMPACT)

        # -------获取当前时间的前2天
        current_date = datetime.now()
        two_days_ago = current_date + timedelta(days=-star_time)
        query_date = two_days_ago.strftime(_FMT_DATE)

        query_start_time = query_date + " 00:00:00"
        query_end_time = query_date + " 23:59:59"
        log.info("查询时间范围" + query_start_time + "到" + query_end_time)

        # 是否不是节假日
        is_not_exitsjholiday_flag = True
        if query_date in jholiday_time_value:
            is_not_exitsjholiday_flag = False

        for i in range(start_num, end_num + 1):
            format2 = _FMT_DATETIME
            query_start_date = two_days_ago
            try:
                query_start_date = _parse_date(format2, query_start_time)
            except Exception as e:
                # 【Java→Python】Java 同时调用 e.printStackTrace() 与 log.error，
                # Python 用 exc_info=True 在日志中输出同等堆栈
                log.error("日期解析错误！" + query_start_time, exc_info=True)

            # ----- 分页范围 ： 2000一次性查询
            car_para_vo.start_num = page_size
            if i > 1:
                end_range = (i - 1) * page_size  # 当前页 -1
                car_para_vo.end_num = end_range

            car_para_vo.apply_time1 = query_start_time
            car_para_vo.apply_time2 = query_end_time

            carlist_all: list[ZdataTrailTracks] = []

            if is_not_exitsjholiday_flag:
                # --------- 有拟合轨迹的
                log.info(
                    "轨迹点开始------"
                    + _java_str(datetime.now())
                    + "分页配置："
                    + _java_str(car_para_vo.start_num)
                    + "到"
                    + _java_str(car_para_vo.end_num)
                )
                carlist_fittinglist = self.zdata_trail_tracks_service.getLatestTrail(car_para_vo)
                log.info(
                    "轨迹点结束-----"
                    + _java_str(datetime.now())
                    + "--数据："
                    + _java_str(len(carlist_fittinglist))
                )
                for zdata_trail_tracks_vo in carlist_fittinglist:
                    zdata_trail_tracks_vo.flag = "1"  # 有的轨迹点
                    carlist_all.append(zdata_trail_tracks_vo)

                # -------------沒有拟合轨迹的  4000一次查询
                page_size_new = 4000
                car_para_vo.start_num = page_size_new
                if i > 1:
                    end_range = (i - 1) * page_size_new  # 当前页 -1
                    car_para_vo.end_num = end_range
                log.info(
                    "不存在轨迹点开始---"
                    + _java_str(datetime.now())
                    + "分页配置："
                    + _java_str(car_para_vo.start_num)
                    + "到"
                    + _java_str(car_para_vo.end_num)
                )
                car_un_fitting_list = self.zdata_trail_tracks_service.getUnFitting(car_para_vo)
                log.info(
                    "不存在轨迹点结束----"
                    + _java_str(datetime.now())
                    + "--数据："
                    + _java_str(len(car_un_fitting_list))
                )
                for zdata_trail_tracks_vo in car_un_fitting_list:
                    zdata_trail_tracks_vo.uuid = get_uuid()
                    zdata_trail_tracks_vo.flag = "0"  # 沒有的轨迹点
                    carlist_all.append(zdata_trail_tracks_vo)

            fee_records_uuid_list: list[str] = []  # 门架流水轨迹点

            # 符合业务的轨迹点
            carlist_rtn: list[ZdataTrailTracks] = []
            fee_records01_map: dict[str, OdsLwzxsfsjFeeRecords01] = {}

            for tracks in carlist_all:
                uuid = is_null(tracks.uuid)  # 轨迹点id（Java 中取出后未使用）
                key_value = tracks.trail_points  # 行驶轨迹
                josn_list: list[TrailBo] = []
                if is_not_blank(key_value):
                    enter_time = tracks.enter_time
                    if enter_time is not None:
                        # 如果指定的时间 大于 轨迹开始时间的话
                        if _millis(query_start_date) > _millis(enter_time):
                            query_start_date = enter_time
                    josn_list = self.get_trail_bo_list(key_value)
                    # JSON.toJSONString(josnList)：字段名保持 Java 驼峰，null 字段不输出
                    tracks.trail_points = _trail_bo_list_to_json(josn_list)
                    is_not_xymj_flag = True  # 是否不包含虚拟门架
                    conut_gantry_capture = 0
                    for trail_bo in josn_list:
                        location_code = is_null(trail_bo.location_code)  # 设备IP地址
                        state_type = is_null(trail_bo.state_type)  # 流水来源类型标识
                        if state_type == GANTRY_CAPTURE:
                            # 门架抓拍
                            conut_gantry_capture += 1
                            if is_not_blank(location_code):
                                if location_code in location_map:
                                    dev_locat_code = is_null(
                                        location_map[location_code].standard_code
                                    )  # 收费站/门架code
                                    # 判断是否是虚拟门架---------
                                    if is_not_blank(dev_locat_code):
                                        # 找到门架信息
                                        if dev_locat_code in gantry_mao:
                                            gantry = gantry_mao.get(dev_locat_code)
                                            if is_null(gantry.is_virtual) == "1":
                                                is_not_xymj_flag = False

                    # 门架抓拍数量 > 5 并且没有经过虚拟门架
                    if conut_gantry_capture > supoer_mjnum and is_not_xymj_flag:
                        for trail_bo in josn_list:
                            state_type = is_null(trail_bo.state_type)
                            point_uuid = is_null(trail_bo.point_uuid)
                            if state_type == FeeRecord:
                                if is_not_blank(point_uuid):
                                    fee_records_uuid_list.append(point_uuid)
                        carlist_rtn.append(tracks)

            fee_records01 = OdsLwzxsfsjFeeRecords01()
            fee_records01.in_apply_time1 = _format_date(format2, query_start_date)
            fee_records01.in_apply_time2 = query_end_time

            if len(fee_records_uuid_list) > 0:
                batch_size = 2000
                if len(fee_records_uuid_list) <= batch_size:
                    # 小于1000，
                    fee_records01.cid_list = fee_records_uuid_list
                    fee_records01_list = self.query_fee_records01_list(fee_records01)  # 查询数据
                    for rtn_fee_records01 in fee_records01_list:
                        fee_records01_map[is_null(rtn_fee_records01.cid)] = rtn_fee_records01
                else:
                    # 【Java→Python】Java 用 subList(yy, min(yy+batchSize, size))（视图），
                    # Python 切片生成新列表，但同样只读使用，行为一致
                    for yy in range(0, len(fee_records_uuid_list), batch_size):
                        sub_list = fee_records_uuid_list[
                            yy: min(yy + batch_size, len(fee_records_uuid_list))
                        ]
                        # 处理subList，例如保存到数据库或进行其他操作
                        fee_records01.cid_list = sub_list
                        fee_records01_list = self.query_fee_records01_list(fee_records01)  # 查询数据
                        for rtn_fee_records01 in fee_records01_list:
                            fee_records01_map[is_null(rtn_fee_records01.cid)] = rtn_fee_records01

            # 生成可疑车辆
            self.separate_unfiiting_list(carlist_rtn, fee_records01_map)

            # 执行完了 还原
            carlist_rtn = []
            fee_records01_map = {}

    # -------------------------------------------------------------------------
    # 历史轨迹查询（门架流水）
    # -------------------------------------------------------------------------

    def query_fee_records01_list(
        self, fee_records01: OdsLwzxsfsjFeeRecords01
    ) -> list[OdsLwzxsfsjFeeRecords01]:
        fee_records01_list = self.fee_records01_service.selectOdsLwzxsfsjFeeRecords01ListNew(
            fee_records01
        )
        log.info(
            "门架流水结束----"
            + _java_str(datetime.now())
            + "--数据："
            + _java_str(len(fee_records01_list))
        )
        return fee_records01_list

    # -------------------------------------------------------------------------
    # 判断是否有虚拟门架
    # -------------------------------------------------------------------------

    def get_is_virtual_flag(self, trail_list: list[TrailBo]) -> bool:
        is_virtual_flag = True
        if trail_list is not None and len(trail_list) > 0:
            for trail_bo in trail_list:
                state_type = is_null(trail_bo.state_type)
                is_virtual = is_null(trail_bo.is_virtual)
                if state_type == GANTRY_CAPTURE and is_virtual == "1":
                    is_virtual_flag = False
        return is_virtual_flag

    # -------------------------------------------------------------------------
    # 获取车牌颜色
    # -------------------------------------------------------------------------

    def get_plate_color(self, trail_list: list[TrailBo]) -> str:
        plate_color = ""
        if trail_list is not None and len(trail_list) > 0:
            count_num = 0
            for trail_bo in trail_list:
                state_type = is_null(trail_bo.state_type)
                if state_type == GANTRY_CAPTURE:
                    # 查询第一个门架抓拍的车牌号
                    if count_num == 0:
                        change_trail_bo = self.get_by_trail_bo(trail_bo)
                        if change_trail_bo is not None:
                            plate_color = is_null(change_trail_bo.platecolor)
                            return plate_color
                    count_num += 1
        return plate_color

    # -------------------------------------------------------------------------
    # carTrackQuery
    # -------------------------------------------------------------------------

    def car_track_query(self, car_para_vo: CarParaVO) -> list[TrailInfo]:
        """查询车俩历史记录。"""
        carlist_para = car_para_vo.carlist
        if carlist_para is not None and len(carlist_para) > 0:
            # 【Java→Python】stream().map(CarVO::getCarNo).collect(toList()) ≙ 列表推导
            car_no_list = [car_vo.car_no for car_vo in carlist_para]
            car_para_vo.car_no_list = car_no_list
        carlist = self.zdata_trail_tracks_service.getHistoryTrail(car_para_vo)
        rtn_list: list[TrailInfo] = []
        if carlist is not None and len(carlist) > 0:
            for tracks in carlist:
                car_no = is_null(tracks.plate_key)
                key_value = tracks.trail_points  # 行驶轨迹
                josn_list: list[TrailBo] = []
                if is_not_blank(key_value):
                    josn_list = self.get_trail_bo_list(key_value)
                    # tracks.setTrailPoints("");  // 行驶轨迹（原代码已注释）

                    trail_info = self.change_data(tracks, josn_list)  # 获取设备的经纬度
                    trail_info.trail_uuid = car_no
                    rtn_list.append(trail_info)
        return rtn_list

    # -------------------------------------------------------------------------
    # carTrackQueryNew
    # -------------------------------------------------------------------------

    def car_track_query_new(self, car_para_vo: CarParaVO) -> list[ZdataTrailTracks]:
        """轨迹查询：界面上查询-------------"""
        carlist_para = car_para_vo.carlist
        if carlist_para is not None and len(carlist_para) > 0:
            car_no_list = [car_vo.car_no for car_vo in carlist_para]
            car_para_vo.car_no_list = car_no_list
        list_ = self.zdata_trail_tracks_service.getHistoryTrail(car_para_vo)

        return list_

    # -------------------------------------------------------------------------
    # dws json 字符串转换
    # -------------------------------------------------------------------------

    def get_trail_bo_list_string(self, para_trail_points: str) -> str:
        """dws josn2字符串转换。"""
        trail_points = is_null(para_trail_points)
        if is_not_blank(trail_points):
            # Java 源码中的转义写法与字面量逐字对应：
            # replace("\\", "")          → 去掉反斜杠
            # replace("{\"{", "[{")      → {"{  → [{
            # replace("}\"}", "}]")      → }"}  → }]
            # replace("\",\"{", ",{")    → ","{  → ,{
            trail_points = trail_points.replace("\\", "")
            trail_points = trail_points.replace('{"{', "[{")
            trail_points = trail_points.replace('}"}', "}]")
            trail_points = trail_points.replace('","{', ",{")
            trail_points = trail_points.replace("ZdTrails:", "")
        return trail_points

    # -------------------------------------------------------------------------
    # getTrailBoList
    # -------------------------------------------------------------------------

    def get_trail_bo_list(self, para_trail_points: str) -> list[TrailBo]:
        """转josn。"""
        trail_bo_list: list[TrailBo] = []
        trail_points = self.get_trail_bo_list_string(para_trail_points)
        if is_not_blank(trail_points) and trail_points != "{}":
            try:
                # 先转josn数组 然后循环 一个一个手动赋值
                array = _json_loads(trail_points)
                format1 = _FMT_DATETIME_T
                format2 = _FMT_DATETIME
                for o in array:
                    json_obj = o  # Java: JSONObject jsonObj = (JSONObject) o
                    capture_time = _json_get_string(json_obj, "captureTime")
                    state_type = _json_get_string(json_obj, "stateType")
                    platenumber = _json_get_string(json_obj, "platenumber")
                    location_id = _json_get_string(json_obj, "locationId")
                    location_code = _json_get_string(json_obj, "locationCode")
                    point_uuid = _json_get_string(json_obj, "pointUuid")
                    section_code = _json_get_string(json_obj, "sectionCode")
                    org_code = _json_get_string(json_obj, "orgCode")
                    pile_no = _json_get_string(json_obj, "pileNo")
                    lon = _json_get_string(json_obj, "lon")
                    lat = _json_get_string(json_obj, "lat")
                    trail_bo = TrailBo()
                    capture_time = is_null(capture_time)
                    # 【Java→Python】String.indexOf("T") > -1 ≙ "T" in capture_time
                    if "T" in capture_time:
                        date_time = _parse_date(format1, capture_time)
                        # 步骤2：使用DateTimeFormatter转字符串
                        formatted_date_str = _format_date(format2, date_time)
                        trail_bo.capture_time = formatted_date_str
                    trail_bo.state_type = state_type
                    trail_bo.platenumber = platenumber
                    trail_bo.location_id = location_id
                    trail_bo.location_code = location_code
                    trail_bo.point_uuid = point_uuid
                    trail_bo.section_code = section_code
                    trail_bo.org_code = org_code
                    trail_bo.pileno = pile_no
                    if is_not_blank(lon):
                        trail_bo.lon = _to_decimal(lon)
                    if is_not_blank(lat):
                        trail_bo.lat = _to_decimal(lat)
                    trail_bo_list.append(trail_bo)
            except Exception as e:
                # 【Java→Python】Java 的 e.printStackTrace() 在 Python 中通过 exc_info 输出堆栈；
                # 注意：Java 的 try 包住整个 for 循环，异常时已解析出的部分列表仍会被使用
                log.error("解析错误！" + trail_points, exc_info=True)
        rtn_list = self.map_trail_bo_list(trail_bo_list)

        return rtn_list

    # -------------------------------------------------------------------------
    # mapTrailBoList
    # -------------------------------------------------------------------------

    def map_trail_bo_list(self, trail_bo_list: list[TrailBo]) -> list[TrailBo]:
        """处理：合并门架抓拍和收费站抓拍流水------"""
        map_list: list[TrailBo] = []

        # 去掉重合的
        format2 = _FMT_DATETIME
        # 【原样保留】注释写“三分钟”，取值实际是 4 分钟，按 Java 源码保持不变
        three_minutes_in_millis = 4 * 60 * 1000

        map_: dict[str, TrailBo] = {}
        if trail_bo_list is not None and len(trail_bo_list) > 0:
            for trail_bo in trail_bo_list:
                state_type = is_null(trail_bo.state_type)  # 类型
                location_code = is_null(trail_bo.location_code)  # 设备IP地址
                capture_time = is_null(trail_bo.capture_time)  # 抓拍时间
                images_arry = delete_end(trail_bo.images_arry)  # 抓拍图片
                map_key = state_type + location_code
                if map_key in map_:
                    trail_bo_temp = map_.get(map_key)
                    capture_time_temp = is_null(trail_bo_temp.capture_time)
                    if is_not_blank(capture_time) and is_not_blank(capture_time_temp):
                        try:
                            capture_time_date1 = _parse_date(format2, capture_time)
                            capture_time_date2 = _parse_date(format2, capture_time_temp)
                            diff = abs(
                                _millis(capture_time_date2) - _millis(capture_time_date1)
                            )
                            if diff > three_minutes_in_millis:
                                map_list.append(trail_bo)
                            else:
                                # 抓拍图片累加--------------
                                images_arry_temp = delete_end(trail_bo_temp.images_arry)
                                if images_arry != "":
                                    if images_arry_temp == "":
                                        trail_bo_temp.images_arry = images_arry
                                    else:
                                        trail_bo_temp.images_arry = (
                                            images_arry_temp + "," + images_arry
                                        )
                        except Exception as e:
                            map_list.append(trail_bo)
                            log.info("日期解析失败------------" + str(e))
                    else:
                        map_list.append(trail_bo)
                else:
                    map_list.append(trail_bo)

                if state_type == GANTRY_CAPTURE or state_type == STATION_CAPTURE:
                    map_[map_key] = trail_bo

        return map_list

    # -------------------------------------------------------------------------
    # 获取门架抓拍流水
    # -------------------------------------------------------------------------

    def sync_snapshot_flow(self, snapshot_flow: OdsRtSzdnSnapshotFlowAddcode) -> None:
        log.info("门架抓拍流水SQL开始查询----------" + _java_str(datetime.now()))
        now = datetime.now()
        redis_date = now.strftime(_FMT_DATE_COMPACT)
        # ----- 分页范围
        list_ = self.snapshot_flow_addcode_service.selectOdsRtSzdnSnapshotFlowAddcodeListNew(
            snapshot_flow
        )
        log.info(
            "门架抓拍流水SQL结束查询----------"
            + _java_str(datetime.now())
            + "--数据："
            + _java_str(len(list_))
        )
        for snapshot_flow_addcode in list_:
            if is_not_blank(snapshot_flow_addcode.platenumber) and \
                    snapshot_flow_addcode.snapshottime is not None:
                key_list: list[OdsRtSzdnSnapshotFlowAddcode] = []
                # 按照路段和车牌
                key = (
                    is_null(snapshot_flow_addcode.sectioncode)
                    + "@@"
                    + is_null(snapshot_flow_addcode.platenumber)
                )
                redis_key = self.snapshot_flow_list_key(redis_date, key)
                old_list = self.redis_cache.get_cache_object(redis_key)
                if old_list is not None and len(old_list) > 0:
                    key_list = old_list
                key_list.append(snapshot_flow_addcode)
                self.redis_cache.set_cache_object(redis_key, key_list)

    # -------------------------------------------------------------------------
    # 获取门架交易流水
    # -------------------------------------------------------------------------

    def sync_fee_records(self, fee_records: OdsLwzxsfsjFeeRecords01) -> None:
        log.info("门架交易流水SQL开始查询----------" + _java_str(datetime.now()))
        now = datetime.now()
        redis_date = now.strftime(_FMT_DATE_COMPACT)
        # ----- 分页范围
        fee_records.order_by_flag = "order"
        list_ = self.fee_records01_service.selectOdsLwzxsfsjFeeRecords01ListNew(fee_records)
        log.info(
            "门架交易流水SQL开始查询----------"
            + _java_str(datetime.now())
            + "数据--"
            + _java_str(len(list_))
        )
        for fee_records01 in list_:
            vehicleplate = is_null(fee_records01.vehicleplate)  # 车牌号_颜色
            # 【Java→Python】String.split("_") 会丢弃尾部空串，Python 保留；
            # 这里只取下标 0，两种行为结果相同
            if "_" in vehicleplate:
                vehicleplate_str = vehicleplate.split("_")
                vehicleplate_change = is_null(vehicleplate_str[0])
                if is_not_blank(vehicleplate_change):
                    # 按照路段和车牌
                    key_list: list[OdsLwzxsfsjFeeRecords01] = []
                    key = (
                        is_null(fee_records01.sectioncode)
                        + "@@"
                        + is_null(vehicleplate_change)
                    )
                    redis_key = self.fee_records_list_key(redis_date, key)
                    old_list = self.redis_cache.get_cache_object(redis_key)
                    if old_list is not None and len(old_list) > 0:
                        key_list = old_list
                    key_list.append(fee_records01)
                    self.redis_cache.set_cache_object(redis_key, key_list)

    # -------------------------------------------------------------------------
    # separateSnapshotFlowTimeList
    # -------------------------------------------------------------------------

    def separate_snapshot_flow_time_list(self) -> None:
        """门架抓拍流水 和 获取门架交易流水 对比。"""
        now = datetime.now()
        redis_date = now.strftime(_FMT_DATE_COMPACT)

        road_supoer_mjnum_int = 3  # 路段：门架抓拍数量和门架流水数量对比
        road_supoe_mjnum_value = self.redis_cache.get_cache_object(road_supoer_mjnum)  # 比例默认为3
        if is_not_blank(road_supoe_mjnum_value):
            road_supoer_mjnum_int = int(road_supoe_mjnum_value)
            log.info("从缓存路段：取得门架抓拍数量------：" + _java_str(road_supoe_mjnum_value))

        # 【原样保留】注释写“30分钟”，取值实际是 1 小时，按 Java 源码保持不变
        thirty_minutes_in_millis = 60 * 60 * 1000

        keys = self.redis_cache.keys(CONST_SNAPSHOT_FLOW_LIST + redis_date + "*")
        if keys is not None and len(keys) > 0:
            for key in keys:
                key_list = self.redis_cache.get_cache_object(key)
                if key_list is not None and len(key_list) >= road_supoer_mjnum_int:
                    # 按照车辆时间排序
                    # 【Java→Python】Comparator.comparing(...) 遇到 null 抛 NPE，
                    # Python sorted 遇到 None 抛 TypeError，同为“快速失败”
                    key_list = sorted(key_list, key=lambda item: item.snapshottime)

                    # 判断有几次通行
                    snapshot_list: list[OdsRtSzdnSnapshotFlowAddcode] = []
                    for i in range(len(key_list)):
                        rtndata = key_list[i]
                        if i == 0:
                            snapshot_list.append(rtndata)
                        else:
                            # 时间相差1个小时之内为同一组
                            pre_snapshottime = key_list[i - 1].snapshottime
                            snapshottime = rtndata.snapshottime

                            diff = abs(_millis(snapshottime) - _millis(pre_snapshottime))
                            if diff > thirty_minutes_in_millis:
                                # 超过了60分钟
                                self.is_fee_records_exist(
                                    key, snapshot_list, road_supoer_mjnum_int, redis_date
                                )

                                # 重新计算---------------
                                snapshot_list = []
                                snapshot_list.append(rtndata)
                            else:
                                snapshot_list.append(rtndata)
                    self.is_fee_records_exist(
                        key, snapshot_list, road_supoer_mjnum_int, redis_date
                    )

        # 删除redis
        if keys is not None and len(keys) > 0:
            self.redis_cache.delete_object(keys)

        free_keys = self.redis_cache.keys(CONST_FEE_RECORDS_LIST + redis_date + "*")
        if free_keys is not None and len(free_keys) > 0:
            self.redis_cache.delete_object(free_keys)

        trail_fitting_keys = self.redis_cache.keys(CONST_TRAIL_FITTING_LIST + redis_date + "*")
        if trail_fitting_keys is not None and len(trail_fitting_keys) > 0:
            self.redis_cache.delete_object(trail_fitting_keys)

    # -------------------------------------------------------------------------
    # isFeeRecordsExist
    # -------------------------------------------------------------------------

    def is_fee_records_exist(
        self,
        key: str,
        snapshot_list: list[OdsRtSzdnSnapshotFlowAddcode],
        road_supoer_mjnum: int,
        redis_date: str,
    ) -> None:
        """对比找到可疑车辆。"""
        if is_not_blank(key) and snapshot_list is not None \
                and len(snapshot_list) >= road_supoer_mjnum and len(snapshot_list) >= 2:
            # 【Java→Python】key 形如 "js_car_snapshot20251021:路段@@车牌"，不含尾部空串，
            # String.split 与 str.split 结果一致
            road_car_key_str = key.split(":")

            # 门架----------
            gantry_list = self.ods_szdn_gantry_service.getGantryRedis()
            gantry_mao: dict[str, OdsSzdnGantry] = {}
            for rtn_ods_szdn_gantry in gantry_list:
                gantry_mao[is_null(rtn_ods_szdn_gantry.gantry_code)] = rtn_ods_szdn_gantry

            # 根据路段查询路线map
            section_map = self.section_service.getSectionMap()

            state_type = GANTRY_CAPTURE  # 门架抓拍
            format2 = _FMT_DATETIME

            if len(road_car_key_str) > 1:
                first_bo = snapshot_list[0]  # 第一个
                end_bo = snapshot_list[len(snapshot_list) - 1]  # 最后一个

                start_time = first_bo.snapshottime
                end_time = end_bo.snapshottime

                start_time_long = _millis(start_time)
                end_time_long = _millis(end_time)

                road_car_key = road_car_key_str[1]
                section_code = is_null(first_bo.sectioncode)

                section_name = ""
                road_code = ""
                if section_code in section_map:
                    ods_szdn_section = section_map.get(section_code)
                    section_name = ods_szdn_section.section_name
                    road_code = ods_szdn_section.road_code

                redis_key = self.fee_records_list_key(redis_date, road_car_key)
                is_add_flag = False
                old_list = self.redis_cache.get_cache_object(redis_key)
                if old_list is not None and len(old_list) > 0:
                    free_count_num = 0  # 计费模块响应计费结果 0 成功 1失败
                    for fee_records01 in old_list:
                        transtime = fee_records01.transtime
                        if transtime is not None:
                            transtime_long = _millis(transtime)
                            if start_time_long <= transtime_long <= end_time_long:
                                # 时间在范围里
                                fee = fee_records01.fee
                                # 【Java→Python】BigDecimal.compareTo(ZERO) > 0 ≙ Decimal 直接比较
                                if fee is not None and fee > Decimal(0):
                                    free_count_num = free_count_num + 1
                    if free_count_num > 0:
                        pass  # 有数据 后续做部分
                    else:
                        is_add_flag = True
                else:
                    # 无数据------------
                    is_add_flag = True

                if is_add_flag:
                    car_no = first_bo.platenumber

                    trail_fitting = 0  # 是否有轨迹点

                    # ------------ 判断是否有出入口轨迹
                    # 【Java→Python】carNo 可能为 null，Java 拼 key 得到 "...null"，此处用 _java_str 等价
                    trail_fitting_redis_key = self.trail_fitting_key(
                        redis_date, _java_str(car_no)
                    )
                    old_fitting_list = self.redis_cache.get_cache_object(trail_fitting_redis_key)
                    if old_fitting_list is not None and len(old_fitting_list) > 0:
                        for trail_tracks_vo in old_fitting_list:
                            trail_ttart_time = trail_tracks_vo.enter_time  # 进入时间
                            trail_end_time = trail_tracks_vo.exit_time  # 离开时间
                            if trail_ttart_time is not None and trail_end_time is not None:
                                if _millis(trail_ttart_time) <= end_time_long \
                                        <= _millis(trail_end_time):
                                    trail_fitting = trail_fitting + 1

                    if trail_fitting == 0:
                        platecolor = first_bo.platecolor

                        tracks = ZdataTrailTracks()
                        tracks.uuid = get_uuid()
                        tracks.plate_key = car_no
                        tracks.enter_time = start_time

                        start_gantryid = is_null(first_bo.gantrycode)
                        tracks.entollstationid = start_gantryid
                        if start_gantryid in gantry_mao:
                            ods_szdn_gantry = gantry_mao.get(start_gantryid)
                            tracks.entollstationname = ods_szdn_gantry.gantry_name  # 门架名称

                            if is_not_blank(ods_szdn_gantry.lon):
                                tracks.start_lon = ods_szdn_gantry.lon  # 经度
                            if is_not_blank(ods_szdn_gantry.lat):
                                tracks.strat_lat = ods_szdn_gantry.lat  # 经度

                        tracks.envehicletype = is_null(first_bo.cartypecode)  # 车型
                        tracks.envehicleid = car_no  # 车牌号

                        tracks.exit_time = end_time

                        end_gantryid = is_null(end_bo.gantrycode)
                        tracks.extollstationid = end_gantryid
                        if end_gantryid in gantry_mao:
                            ods_szdn_gantry = gantry_mao.get(end_gantryid)
                            tracks.extollstationname = ods_szdn_gantry.gantry_name  # 门架名称

                            if is_not_blank(ods_szdn_gantry.lon):
                                tracks.end_lon = ods_szdn_gantry.lon  # 经度
                            if is_not_blank(ods_szdn_gantry.lat):
                                tracks.end_lat = ods_szdn_gantry.lat  # 经度

                        tracks.exvehicleid = car_no  # 车牌号

                        if is_not_blank(tracks.start_lon):
                            tracks.start_lon_dec = _to_decimal(tracks.start_lon)
                        if is_not_blank(tracks.strat_lat):
                            tracks.strat_lat_dec = _to_decimal(tracks.strat_lat)
                        if is_not_blank(tracks.end_lon):
                            tracks.end_lon_dec = _to_decimal(tracks.end_lon)
                        if is_not_blank(tracks.end_lat):
                            tracks.end_lat_dec = _to_decimal(tracks.end_lat)

                        # -------------- 车辆轨迹点
                        josn_list: list[TrailBo] = []
                        for snapshot_bo in snapshot_list:
                            trail_bo = TrailBo()

                            gantry_code = is_null(snapshot_bo.gantrycode)

                            trail_bo.state_type = state_type
                            trail_bo.platenumber = snapshot_bo.platenumber
                            trail_bo.location_id = gantry_code
                            trail_bo.location_code = gantry_code
                            trail_bo.point_uuid = snapshot_bo.datauuid
                            trail_bo.section_code = snapshot_bo.sectioncode

                            capture_time = snapshot_bo.snapshottime
                            if capture_time is not None:
                                trail_bo.capture_time = _format_date(format2, capture_time)

                            trail_bo.dev_code = gantry_code  # 设备编号
                            if gantry_code in gantry_mao:
                                ods_szdn_gantry = gantry_mao.get(gantry_code)
                                lon = ods_szdn_gantry.lon
                                lat = ods_szdn_gantry.lat

                                trail_bo.pileno = ods_szdn_gantry.pile_no  # 桩号
                                if is_not_blank(lon):
                                    trail_bo.lon = _to_decimal(lon)
                                if is_not_blank(lat):
                                    trail_bo.lat = _to_decimal(lat)

                                trail_bo.dev_name = ods_szdn_gantry.gantry_name  # 设备名称

                            # 设备名称没有默认位置信息--------------
                            if is_blank(trail_bo.dev_name):
                                trail_bo.dev_name = gantry_code

                            trail_bo.road_code = road_code
                            josn_list.append(trail_bo)

                        escaped_type_remark = (
                            _java_str(section_name)
                            + "路段全程屏蔽：其中门架牌识流水数量:"
                            + _java_str(len(snapshot_list))
                            + "，门架交易成功流水数量:0。"
                        )
                        escaped_type = CONST_ESCAPED_TYPE_20
                        tracks.escaped_type = escaped_type  # 屏蔽
                        tracks.escaped_type_remark = escaped_type_remark
                        tracks.escaped_tfcj = "3"  # 路段屏蔽

                        # 车牌颜色
                        tracks.plate_color = platecolor

                        trail_info = TrailInfo()
                        trail_info.tracks = tracks
                        trail_info.trail_list = josn_list
                        trail_info.trail_uuid = car_no

                        # 判断门架抓拍是否经过了虚拟门架
                        if self.get_is_virtual_flag(trail_info.trail_list):
                            kykey = self.get_suspicious_key(redis_date, _java_str(car_no))
                            is_exist_obj = self.redis_cache.get_cache_object(kykey)
                            if is_exist_obj is None:
                                self.redis_cache.set_cache_object(kykey, trail_info)

    # -------------------------------------------------------------------------
    # separateUnfiitingList
    # -------------------------------------------------------------------------

    def separate_unfiiting_list(
        self,
        carlist_rtn: list[ZdataTrailTracks],
        fee_records01_map: dict[str, OdsLwzxsfsjFeeRecords01],
    ) -> None:
        """根据 流水节点 ---和 获取门架交易流水 对比。"""
        now = datetime.now()
        redis_date = now.strftime(_FMT_DATE_COMPACT)
        bite = Decimal("0.5")  # 门架抓拍和流水抓拍占比

        log.info("生成可疑的数据开始：" + _java_str(datetime.now()))
        log.info("参数:轨迹点数量" + _java_str(len(carlist_rtn)))

        if carlist_rtn is not None and len(carlist_rtn) > 0 and fee_records01_map is not None:
            for tracks in carlist_rtn:
                if tracks is not None:
                    car_no = is_null(tracks.plate_key)
                    key_value = tracks.trail_points  # 行驶轨迹
                    type_flag = is_null(tracks.flag)
                    josn_list: list[TrailBo] = []
                    if is_not_blank(key_value):
                        # JSON.parseArray(keyValue, TrailBo.class)
                        josn_list = _parse_array_to_trail_bo_list(key_value)
                        if josn_list is not None and len(josn_list) > 0:
                            # 没有轨迹点的s
                            if type_flag == "0":
                                tracks.flag = "currentTrack"  # 设置起点和终点

                            # ---------------------------分析场景: 路段抓拍和流水抓拍 占比
                            conut_gantry_capture = 0  # 门架抓拍流水
                            conut_fee_record = 0  # 门架抓拍流水（原注释如此）
                            suss_fee_record = 0  # 成功门架抓拍流水

                            for rtn_trail_bo in josn_list:
                                state_type = is_null(rtn_trail_bo.state_type)
                                point_uuid = is_null(rtn_trail_bo.point_uuid)
                                if state_type == GANTRY_CAPTURE:
                                    # 门架抓拍
                                    conut_gantry_capture += 1
                                elif state_type == FeeRecord:
                                    # 卡口流水
                                    conut_fee_record += 1
                                    if is_not_blank(point_uuid):
                                        fee_record_obj = fee_records01_map.get(point_uuid)
                                        if fee_record_obj is not None:
                                            # Java 中为强制类型转换，Python 无需转换
                                            rtn_fee_records01 = fee_record_obj
                                            fee = rtn_fee_records01.fee
                                            if fee is not None and fee > Decimal(0):
                                                suss_fee_record += 1

                            add_flag = False
                            escaped_tfcj = ""  # 逃费场景
                            escaped_type_remark = ""  # 场景描述
                            escaped_type = ""
                            if conut_fee_record == 0:
                                # 全屏蔽
                                escaped_type_remark = (
                                    "全程屏蔽：其中门架牌识流水数量:"
                                    + _java_str(conut_gantry_capture)
                                    + "，门架交易流水数量:"
                                    + _java_str(conut_fee_record)
                                    + "。"
                                )
                                escaped_tfcj = "1"
                                escaped_type = CONST_ESCAPED_TYPE_20
                                add_flag = True
                            else:
                                if suss_fee_record == 0:
                                    escaped_type_remark = (
                                        "全程屏蔽(交易成功)：其中门架牌识流水数量:"
                                        + _java_str(conut_gantry_capture)
                                        + "，门架交易流水数量:"
                                        + _java_str(conut_fee_record)
                                        + "，"
                                        + "，门架交易流水成功数量:"
                                        + _java_str(suss_fee_record)
                                        + "。"
                                    )
                                    escaped_tfcj = "3"
                                    escaped_type = CONST_ESCAPED_TYPE_20
                                    add_flag = True
                                else:
                                    # 【Java→Python】new BigDecimal(a).divide(new BigDecimal(b),
                                    # 4, ROUND_HALF_UP) ≙ Decimal 除法 + quantize(4 位, HALF_UP)
                                    cost_bite = (
                                        Decimal(conut_fee_record) / Decimal(suss_fee_record)
                                    ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                                    if bite.compare(cost_bite) >= 0:
                                        escaped_type_remark = (
                                            "部分屏蔽(交易成功)：其中门架牌识流水数量:"
                                            + _java_str(conut_gantry_capture)
                                            + "，门架交易流水数量:"
                                            + _java_str(conut_fee_record)
                                            + "，"
                                            + "，门架交易流水成功数量:"
                                            + _java_str(suss_fee_record)
                                            + "。"
                                        )
                                        escaped_tfcj = "2"
                                        escaped_type = CONST_ESCAPED_TYPE_20
                                        add_flag = True

                            if add_flag:
                                tracks.escaped_tfcj = escaped_tfcj  # 逃费场景
                                tracks.escaped_type = escaped_type
                                tracks.escaped_type_remark = escaped_type_remark

                                trail_info = self.change_data(tracks, josn_list)  # 获取设备的经纬度

                                # 车牌颜色
                                tracks.plate_color = self.get_plate_color(trail_info.trail_list)
                                trail_info.trail_uuid = car_no

                                suspicious_key = self.get_suspicious_key(redis_date, car_no)
                                self.redis_cache.set_cache_object(suspicious_key, trail_info)

        log.info("生成可疑车辆的数据结束：" + _java_str(datetime.now()))

    # -------------------------------------------------------------------------
    # syncSuspiciousCarDB
    # -------------------------------------------------------------------------

    def sync_suspicious_car_db(self) -> None:
        """数据推送。"""
        # 从redis拿
        trail_info_list: list[TrailInfo] = []
        now = datetime.now()
        formatted_date = now.strftime(_FMT_DATE_COMPACT)

        keys = self.redis_cache.keys(CONST_CAR_USPICIOUS + formatted_date + "*")
        if keys is not None and len(keys) > 0:
            for key in keys:
                trail_info = self.redis_cache.get_cache_object(key)
                trail_info_list.append(trail_info)

        # 签名key
        signature_key = "car_monit_pt"

        # 时间戳(毫秒)
        time_stamp = int(time.time() * 1000)

        # 签名
        try:
            signature = sha_encode(signature_key + str(time_stamp))
        except Exception as e:
            # Java: throw new RuntimeException(e);
            raise RuntimeError(e) from e

        suspicious_car_vo = SuspiciousCarVO()
        suspicious_car_vo.signature_key = signature_key
        suspicious_car_vo.time_stamp = time_stamp
        suspicious_car_vo.signature = signature
        suspicious_car_vo.trail_info_list = trail_info_list
        log.info("调用接口开始--------：" + _java_str(datetime.now()))
        json_object = self.http_sys_util_api_service.syncSuspiciousCarTask(suspicious_car_vo)
        response_code = _json_get_integer(json_object, AjaxResult.CODE_TAG)
        log.info("调用接口结束--------：" + _java_str(datetime.now()))
        # JSONObject.toJSONString() ≙ json.dumps
        log.info(
            json.dumps(json_object, ensure_ascii=False, default=_json_ready)
            if isinstance(json_object, (dict, list))
            else _java_str(json_object)
        )
        # 【Java→Python】Java 的 `Integer == int` 会自动拆箱，responseCode 为 null 时抛 NPE；
        # Python 中 None == 200 只是 False，不会抛错（异常表现不同，业务分支一致）
        if response_code == HttpStatus.SUCCESS:
            log.info("调用接口成功返回--------：" + _java_str(datetime.now()))
            if keys is not None and len(keys) > 0:
                # 删除redis
                self.redis_cache.delete_object(keys)
