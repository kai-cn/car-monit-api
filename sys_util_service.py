# -*- coding: utf-8 -*-
"""
服务区基础信息Service业务层处理
SysUtilServiceImpl.java 的 Python 3.12 一比一（像素级）转写版本，不修改原Java文件。

原文件: pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java
对应包: com.ruoyi.base.service.impl

===========================================================================
【Java 与 Python 差异重点说明（全局约定，方法内不再逐一重复）】
1. Spring 容器：Java 使用 @Service/@Autowired/@Resource/@Value 由容器注入；
   Python 没有等价容器，这里改为构造函数注入（依赖倒置），由调用方装配。
2. Lombok @Data 实体：Java 通过 getXxx()/setXxx() 访问器读写字段；
   Python 直接读写同名属性（去掉 get/set 前缀，保留原 camelCase 字段名，
   例如 trailBo.getStateType() -> trailBo.stateType），便于与原代码逐行对照。
3. 方法/常量命名：为"像素级"可对照，全部保留 Java 原始 camelCase 命名，
   未套用 PEP8 snake_case（Python 语法完全允许，仅作风格取舍）。
4. null vs None：Python 中 ""、[]、0 都是假值，若直接写 `if obj:` 会与 Java
   `obj != null` 语义不一致，因此所有判空一律显式 `is None` / `is not None`。
5. 字符串拼接：Java `"x：" + int值` 会自动调用 String.valueOf；Python 的 +
   不支持 str 与 int 拼接（TypeError），因此日志拼接全部转为 f-string（输出等价）。
6. switch(String)：Java 的 case 可以用静态常量（编译期常量）；Python 3.10+ 的
   match-case 模式中"裸名字"会被当作捕获模式、`模块.常量` 点号路径不能作为
   字面模式，均无法安全对应 Java 行为，因此保留 if/elif 等值比较链（语义一致）。
7. BigDecimal：Java BigDecimal -> Python decimal.Decimal；
   new BigDecimal("0.3") -> Decimal("0.3")；
   compareTo 返回 -1/0/1 -> Decimal 直接支持 < == > 比较运算符；
   divide(d, 4, ROUND_HALF_UP) -> (a / d).quantize(Decimal("0.0001"), ROUND_HALF_UP)
   （decimal.ROUND_HALF_UP 与 Java 舍入模式同名同义）。
8. Date/SimpleDateFormat：Java Date.getTime() 是 epoch 毫秒整数 ->
   Python datetime.timestamp()*1000（本文件封装为 _millis()）；
   SimpleDateFormat.parse 是"宽松解析"（允许可解析前缀，多余字符忽略），
   strptime 是"严格解析"（必须全串匹配）——本文件封装 _parseLenient() 模拟
   Java 宽松行为，涉及处另有单独注释。
   格式符映射：yyyy->%Y, MM->%m, dd->%d, HH->%H, mm->%M, ss->%S
   （Java 的 yyyy 是日历年，Python 的 %y 才是两位年，切勿写成 %yy）。
   Calendar.add(DAY_OF_MONTH, -n) -> datetime - timedelta(days=n)。
9. fastjson2：JSON.parseArray(s) -> json.loads(s) 得到 list[dict]；
   JSONObject.getString(k) -> 本文件封装 _getString()（模拟 fastjson 缺失返回 null、
   非字符串自动转 String 的行为，dict.get 对数字值不会自动转 str）。
   JSON.toJSONString(实体列表) -> json.dumps(..., default=_toDict)：
   fastjson 能把 JavaBean 反射序列化，Python json 默认不认识自定义对象，
   必须提供 __dict__ 兜底序列化器（重点差异）。
   JSON.parseArray(s, TrailBo.class) -> [TrailBo.fromDict(d) ...]，
   需要领域模块提供 dict->实体 的等价反序列化（重点差异）。
10. List.subList(a,b)：Java 返回原列表的"视图"（共享存储）；
    Python 切片 [a:b] 返回浅拷贝（独立对象）。本场景只读不写回，行为等价。
11. Stream/Comparator：stream().sorted(Comparator.comparing(X::getY)) ->
    sorted(list, key=lambda x: x.y)；Java 中 key 为 null 会 NPE，
    Python 中 None 参与比较同样抛 TypeError，失败语义一致。
12. Integer.parseInt / new BigDecimal 对非法输入抛异常：Java NumberFormatException
    -> Python ValueError，调用处保持 try/except 或依赖上游数据合法性（与Java一致）。
13. String.replaceAll 第一个参数是"正则"；Python str.replace 是纯字面量全局替换。
    本项目替换内容无正则元字符，故统一用 replace()，结果等价。
    String.replace 在 Java 中本就是字面量替换，直接对应。
14. JedisCluster：Java 每次 new JedisCluster 使用；Python 用 redis 客户端，
    且 redis-py 默认返回 bytes，需 decode——本文件约定 redisSourceFactory
    的 Python 等价物已返回 str（重点差异）。
15. 访问修饰符：Python 没有 private，私有方法（getCacheKey 等）仅以下划线文档
    约定表达，调用处保持 this.xxx() 与原 Java 一致。
16. 异常：try/catch(Exception e) -> try/except Exception as e；
    e.printStackTrace() -> traceback.print_exc()；
    throw new RuntimeException(e) -> raise RuntimeError(e)。
17. 接口实现：Java `implements ISysUtilService` + @Override ->
    Python 用 abc/协议(Protocol) 或依赖同名方法（鸭子类型），此处按鸭子类型处理。
===========================================================================
"""

from __future__ import annotations

import hashlib
import json
import logging
import traceback
import uuid as _uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 【外部依赖】以下两个模块对应 Java 包，需要另行做同样的 1:1 Python 化：
#   com.ruoyi.base.domain.*   -> base_domain
#   com.ruoyi.base.service.*  -> base_services（均为接口，注入的是其实现类实例）
#   com.ruoyi.base.forest.HttpSysUtilApiService -> base_services
#     （Forest 声明式HTTP客户端，Python 无等价框架，需用 httpx/requests 手写实现，
#       方法 syncSuspiciousCarTask(vo) 返回 dict，对应 Java JSONObject —— 重点差异）
# ---------------------------------------------------------------------------
from base_domain import (  # noqa: F401  实体按"直用属性"约定转换（去 get/set 前缀）
    CarParaVO,
    CarVO,
    OdsLwzxsfsjFeeRecords01,
    OdsLwzxsfsjFeeStationEnter01,
    OdsLwzxsfsjFeeStationExit01,
    OdsRtSzdnSnapshotFlowAddcode,
    OdsRtSzdnSnapshotFlowProvcaptureAddcode,
    OdsRtSzdnSnapshotFlowStationcaptureAddcode,
    OdsSzdnGantry,
    OdsSzdnGantryIp,
    OdsSzdnProvinceBorderVehicleWeightNewstructure,
    OdsSzdnSection,
    OdsSzdnToll,
    OdsSzdnTollStationIp,
    SuspiciousCarVO,
    TrailBo,
    TrailInfo,
    TrailTracksVo,
    ZdataLocationDict,
    ZdataTrailTracks,
)
from base_services import (  # noqa: F401  Service 接口对应实现类（构造函数注入）
    IOdsCxztFwqcllsService,
    IOdsLwzxsfsjFeeRecords01Service,
    IOdsLwzxsfsjFeeStationEnter01Service,
    IOdsLwzxsfsjFeeStationExit01Service,
    IOdsRtSzdnSnapshotFlowAddcodeService,
    IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService,
    IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService,
    IOdsSzdnGantryIpService,
    IOdsSzdnGantryService,
    IOdsSzdnProvinceBorderVehicleWeightNewstructureService,
    IOdsSzdnSectionService,
    IOdsSzdnTollService,
    IOdsSzdnTollStationIpService,
    IZdataLocationDictService,
    IZdataTrailTracksService,
)

# Lombok @Slf4j -> Python logging（重点差异：Java注解生成 log 字段，Python 需显式获取logger）
log = logging.getLogger(__name__)


# ===========================================================================
# 【常量适配器】对应 com.ruoyi.common.constant.Constants / HttpStatus
# Python 无编译期常量概念；类属性值与原 Java 保持逐字符一致。
# ===========================================================================
class Constants:
    trail = "trail:"
    car_list_jc = "car_list_jc"
    car_uspicious = "car_uspicious"
    car_curent_trail = "car_curent_trail:"
    snapshotFlowList = "js_car_snapshot"
    feeRecordsList = "js_car_reerecords"
    trailFittingList = "js_car_trail_fitting"
    trailUnFittingList = "js_car_trail_unfitting"
    escapedType_20 = "20"


class HttpStatus:
    SUCCESS = 200


class AjaxResult:
    """对应 com.ruoyi.common.core.domain.AjaxResult（此处用最小等价 dict 语义）"""
    CODE_TAG = "code"

    @staticmethod
    def success() -> dict:
        return {"code": HttpStatus.SUCCESS, "msg": "操作成功"}


# ===========================================================================
# 【工具适配器】对应 com.ruoyi.common.utils.*，语义逐行对齐 Java 实现
# ===========================================================================
class CommonUtil:
    @staticmethod
    def isNull(names: Any) -> str:
        """Java: null -> ""，否则 String.valueOf(names)。
        重点差异：Python 无 String.valueOf，用 str()；但 str(None)=="None" 是坑，
        必须先行 `is None` 判断（与 Java 行为一致）。"""
        if names is None:
            return ""
        return str(names)

    @staticmethod
    def isBlank(str_: Optional[str]) -> bool:
        """Java StringUtils.isBlank：null / 空串 / 纯空白 均为 True"""
        if str_ is None:
            return True
        return str(str_).strip() == ""

    @staticmethod
    def isNotBlank(str_: Optional[str]) -> bool:
        return not CommonUtil.isBlank(str_)

    @staticmethod
    def deleteEnd(obj: Any) -> str:
        """去掉末尾逗号（可循环去多个？Java 原版只去一个，保持一致）"""
        s = CommonUtil.isNull(obj)
        if s.endswith(","):
            s = s[:-1]
        return s

    @staticmethod
    def repalacePicUrl(imagesArry: Optional[str]) -> str:
        imagesArry = CommonUtil.isNull(imagesArry)
        if CommonUtil.isNotBlank(imagesArry):
            if "http://jxjt.isilon.com/ifs" in imagesArry:  # Java: indexOf(...)>-1
                imagesArry = imagesArry.replace("http://jxjt.isilon.com/ifs", "http://36.200.30.144:9080")
            else:
                imagesArry = imagesArry.replace("http://jxjt.isilon.com", "http://36.200.30.144:9080")
        return imagesArry

    @staticmethod
    def repalaceSzdnTollName(tollName: Optional[str]) -> str:
        tollName = CommonUtil.isNull(tollName)
        if CommonUtil.isNotBlank(tollName):
            tollName = tollName.replace("收费站", "")
            tollName = tollName.replace("江西", "")
            tollName = tollName.replace("站", "")
        return tollName


class StringUtils:
    @staticmethod
    def getUUID() -> str:
        """Java: UUID.randomUUID().toString().replaceAll("-","")
        Python: uuid4().hex 等价（32位小写无连字符）"""
        return _uuid.uuid4().hex


class SecuritySHA1Utils:
    @staticmethod
    def shaEncode(inStr: str) -> str:
        """与 Java 逐位一致：UTF-8 -> SHA-1 -> 小写十六进制（不足两位补0）。
        hashlib.hexdigest() 的输出格式与 Java 手写 Integer.toHexString 循环完全相同。
        重点差异：Java 声明 throws Exception，Python 无受检异常，调用处保留 try/except。"""
        return hashlib.sha1(inStr.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 私有转换辅助（模拟 Java 运行时行为，非原文件方法，仅弥补语言差异）
# ---------------------------------------------------------------------------
def _millis(d: datetime) -> int:
    """Date.getTime() -> epoch毫秒。重点差异：Python timestamp() 返回浮点秒，
    需 *1000 并取整，模拟 Java long 毫秒语义。"""
    return int(d.timestamp() * 1000)


def _parseLenient(text: str, fmt: str) -> datetime:
    """模拟 SimpleDateFormat.parse 的"宽松解析"：只解析能匹配的前缀，忽略尾部多余字符。
    重点差异：Python strptime 要求全串严格匹配，例如
    Java format("yyyy-MM-dd").parse("2025-10-14 13:46:42") 成功（忽略时间部分），
    Python strptime 同输入直接抛 ValueError —— 故按长度逐步回退截断再解析。"""
    last_err: Optional[ValueError] = None
    probe = len(fmt) + 2  # 常见多一位分隔符/毫秒的情况多试2个字符
    for n in range(len(text), 0, -1):
        if n > probe:
            continue
        try:
            return datetime.strptime(text[:n], fmt)
        except ValueError as e:
            last_err = e
    raise last_err if last_err else ValueError(f"无法解析日期: {text}")


def _formatDate(d: datetime, fmt: str) -> str:
    """SimpleDateFormat.format -> strftime（格式符已按约定换算好后传入）"""
    return d.strftime(fmt)


def _getString(jsonObj: dict, key: str) -> Optional[str]:
    """模拟 fastjson2 JSONObject.getString：
    重点差异：缺失键返回 None（同Java）；值为数字/布尔时 Java 会转成字符串，
    Python dict.get 拿到的是原始 int/float，这里显式 str() 对齐 Java。"""
    v = jsonObj.get(key)
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)


def _toDict(obj: Any) -> Any:
    """json.dumps 的 default 钩子：模拟 fastjson 对 JavaBean 的反射序列化。
    约定领域实体均带 snake/camel 属性，用 __dict__ 输出（datetime 转字符串）。"""
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


# ===========================================================================
# 服务区基础信息Service业务层处理
# （原 Java: @Service public class SysUtilServiceImpl implements ISysUtilService）
# ===========================================================================
class SysUtilServiceImpl:

    # ---- public static final 常量：Python 约定用全大写类属性，值逐字符一致 ----
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

    def __init__(
        self,
        redisCache,                       # 对应 @Autowired RedisCache
        redisSourceFactory,               # 对应 @Autowired RedisSourceFactory
        redisConfig,                      # 对应 @Resource RedisConfig
        zdataTrailTracksService: IZdataTrailTracksService,
        provinceBorderVehicleWeightNewstructureService: IOdsSzdnProvinceBorderVehicleWeightNewstructureService,
        snapshotFlowAddcodeService: IOdsRtSzdnSnapshotFlowAddcodeService,
        provcaptureAddcodeService: IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService,
        stationcaptureAddcodeService: IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService,
        odsSzdnTollStationIpService: IOdsSzdnTollStationIpService,
        odsSzdnGantryIpService: IOdsSzdnGantryIpService,
        feeRecords01Service: IOdsLwzxsfsjFeeRecords01Service,
        feeStationEnter01Service: IOdsLwzxsfsjFeeStationEnter01Service,
        feeStationExit01Service: IOdsLwzxsfsjFeeStationExit01Service,
        zdataLocationDictService: IZdataLocationDictService,
        fwqcllsService: IOdsCxztFwqcllsService,
        fwqjcxxService,                   # IDwdLcztFwqjcxxService（原文件仅注释代码使用）
        sectionService: IOdsSzdnSectionService,
        isLocalhost: str,                 # 对应 @Value("${isLocalhost}") 配置注入
        odsSzdnGantryService: IOdsSzdnGantryService,
        odsSzdnTollService: IOdsSzdnTollService,
        httpSysUtilApiService,            # 对应 @Resource HttpSysUtilApiService (Forest)
    ):
        """重点差异：Spring @Autowired/@Resource/@Value 字段注入 -> 构造函数显式注入。
        Java 字段可为 null 且容器保证非空；Python 由装配方（如 factory 函数/DI框架）负责。"""
        self.redisCache = redisCache
        self.redisSourceFactory = redisSourceFactory
        self.redisConfig = redisConfig
        self.zdataTrailTracksService = zdataTrailTracksService
        self.provinceBorderVehicleWeightNewstructureService = provinceBorderVehicleWeightNewstructureService
        self.snapshotFlowAddcodeService = snapshotFlowAddcodeService
        self.provcaptureAddcodeService = provcaptureAddcodeService
        self.stationcaptureAddcodeService = stationcaptureAddcodeService
        self.odsSzdnTollStationIpService = odsSzdnTollStationIpService
        self.odsSzdnGantryIpService = odsSzdnGantryIpService
        self.feeRecords01Service = feeRecords01Service
        self.feeStationEnter01Service = feeStationEnter01Service
        self.feeStationExit01Service = feeStationExit01Service
        self.zdataLocationDictService = zdataLocationDictService
        self.fwqcllsService = fwqcllsService
        self.fwqjcxxService = fwqjcxxService
        self.sectionService = sectionService
        self.isLocalhost = isLocalhost
        self.odsSzdnGantryService = odsSzdnGantryService
        self.odsSzdnTollService = odsSzdnTollService
        self.httpSysUtilApiService = httpSysUtilApiService

    # -----------------------------------------------------------------------
    # 以下方法按原 Java 文件行序 1:1 转写
    # -----------------------------------------------------------------------

    def getCacheKey(self, configKey: str) -> str:
        """
        设置cache key

        @param configKey 参数键
        @return 缓存键key
        """
        return Constants.trail + configKey

    def getSuspiciousKey(self, curData: str, configKey: str) -> str:
        """
        可疑车辆

        @param configKey 参数键
        @return 缓存键key
        """
        return Constants.car_uspicious + curData + ":" + configKey

    def snapshotFlowListKey(self, curData: str, configKey: str) -> str:
        """
        门架抓拍流水

        @param configKey 参数键
        @return 缓存键key
        """
        return Constants.snapshotFlowList + curData + ":" + configKey

    def feeRecordsListKey(self, curData: str, configKey: str) -> str:
        """
        门架流水key

        @param configKey 参数键
        @return 缓存键key
        """
        return Constants.feeRecordsList + curData + ":" + configKey

    def trailFittingKey(self, curData: str, configKey: str) -> str:
        """
        轨迹点key：有轨迹

        @param configKey 参数键
        @return 缓存键key
        """
        return Constants.trailFittingList + curData + ":" + configKey

    def trailUnFittingKey(self, curData: str, configKey: str) -> str:
        """
        轨迹点key：无轨迹

        @param configKey 参数键
        @return 缓存键key
        """
        return Constants.trailUnFittingList + curData + ":" + configKey

    def saveRedis(self, sysUtil) -> dict:
        """
        新增或者修改车辆信息

        @param sysUtil 基础类
        @return 结果
        """
        # Java: "字符串" + 变量 自动转串；Python f-string 等价输出（重点差异第5条）
        log.info(f"获取的配置信息：{self.redisConfig.getClusterNodes()}--本地配置：{self.isLocalhost}")

        # ----------测试JedisCluster（原Java 197~271行为整段注释代码，此处像素级保留其内容）
        # jedisCluster = self.redisSourceFactory.createSource(self.redisConfig)
        # carList = ["苏CMA262", "苏F5HK60", "苏FD0A86", "苏MF3652", "赣A0253J"]
        # for carNo in carList:
        #     key = self.getCacheKey(carNo)
        #     keyValue = jedisCluster.get(key)
        #     log.info(f"生产redis：{key}对应的轨迹点：{keyValue}")
        #     self.redisCache.setCacheObject(key, keyValue)
        #
        # ----------zdata_trail_tracks作废
        # zdataTrailTracks = ZdataTrailTracks()
        # zdataTrailTracks.plateKey = "赣CEA826"
        # trackList1 = self.zdataTrailTracksService.selectZdataTrailTracksList(zdataTrailTracks)
        # for trackBo in trackList1:
        #     josnList = json.loads(trackBo.trailPoints)  # Java: JSON.parseArray(str, TrailBo.class)
        #
        # carParaVO = CarParaVO()
        # carParaVO.carNo = "赣FC0278"
        # trackList = self.zdataTrailTracksService.getHistoryTrail(carParaVO)
        # for trackBo in trackList:
        #     try:
        #         trailBoList = self.getTrailBoList(trackBo.trailPoints)
        #         test = "111"
        #     except Exception as e:
        #         traceback.print_exc()
        #         log.error("解析错误！")
        #
        # keys = self.redisCache.keys(residDist + "*")
        # if keys is not None and len(keys) > 0:
        #     for key in keys:
        #         keyValue = self.redisCache.getCacheObject(key)
        #         josnList = []
        #         if CommonUtil.isNotBlank(keyValue):
        #             josnList = json.loads(keyValue)
        #         log.info(f"本地redis：{key}对应的轨迹点：{keyValue}")
        #
        # carNo = "闽B105AK"
        # key = self.getCacheKey(carNo)
        # keyValue = self.redisCache.getCacheObject(key)
        # josnList = []
        # if CommonUtil.isNotBlank(keyValue):
        #     josnList = json.loads(keyValue)
        #     trailBo = TrailBo()
        #     trailBo.pointUuid = StringUtils.getUUID()
        #     trailBo.stateType = "ServiceAreaCapture"
        #     trailBo.captureTime = "2025-10-14 13:46:42"
        #     trailBo.locationCode = "serviceip:172.16.204.101"
        #     trailBo.locationName = "泰和北服务区"
        #     trailBo.standardCode = "G1517360826W0030"
        #     trailBo.locationId = "G1517360826W0030"
        #     trailBo.platenumber = carNo
        #     josnList.append(trailBo)
        #     self.redisCache.setCacheObject(key, json.dumps(josnList, default=_toDict))
        # keyValue1 = self.redisCache.getCacheObject(key)

        return AjaxResult.success()

    def syncTrack(self, carParaVO) -> None:
        """
        同步轨迹

        @param carParaVO carParaVO 车俩列表
        @return 结果
        """
        carlist = []
        obj = self.redisCache.getCacheObject(Constants.car_list_jc)
        if obj is not None:
            carlist = obj  # Java: (List) obj 强制转换；Python 无编译期泛型，直接赋值（重点差异第4条）

        mapCar: dict = {}  # 原Java声明了 Map<ZdataTrailTracks, List<TrailBo>> mapCar 但方法体未使用，像素级保留
        if carlist is not None and len(carlist) > 0:

            log.info(f"获取的配置信息：{self.redisConfig.getClusterNodes()}--本地配置：{self.isLocalhost}"
                     f"--同步车辆数量：{len(carlist)}")
            # 重点差异第14条：Java 每次新建 JedisCluster；Python redis 客户端应复用连接池，
            # 这里保持与原代码相同的调用形式（createSource），生命周期由工厂实现负责。
            jedisCluster = self.redisSourceFactory.createSource(self.redisConfig)

            # 去掉重合的
            # Java "yyyy-MM-dd HH:mm:ss" -> Python "%Y-%m-%d %H:%M:%S"（重点差异第8条格式符映射）
            fmtDateTime = "%Y-%m-%d %H:%M:%S"
            threeMinutesInMillis = 24 * 60 * 60 * 1000  # 24小时转换为毫秒（变量名保留Java原拼写）

            for carVO in carlist:
                carNo = CommonUtil.isNull(carVO.carNo)
                keyValue = ""

                if CommonUtil.isNull(self.isLocalhost) == "local":  # Java .equals -> Python ==（str比较语义一致）
                    # 本地
                    keyValue = self.redisCache.getCacheObject(self.getCacheKey(carNo))
                else:
                    # 生产-------------
                    keyValue = jedisCluster.get(self.getCacheKey(carNo))

                josnList = []
                if CommonUtil.isNotBlank(keyValue):

                    # 先转josn数组 然后循环 一个一个手动赋值
                    # Java JSONArray/JSONObject -> Python list/dict（重点差异第9条）
                    array = json.loads(keyValue)
                    for o in array:
                        jsonObj = o  # Java: (JSONObject) o 显式向下转型；Python 无需转型（鸭子类型）
                        trailBo = TrailBo()
                        trailBo.pointUuid = _getString(jsonObj, "pointUuid")
                        trailBo.stateType = _getString(jsonObj, "stateType")
                        trailBo.captureTime = _getString(jsonObj, "captureTime")
                        trailBo.locationCode = _getString(jsonObj, "locationCode")
                        trailBo.locationName = _getString(jsonObj, "locationName")
                        trailBo.standardCode = _getString(jsonObj, "standardCode")
                        trailBo.locationId = _getString(jsonObj, "locationId")
                        trailBo.platenumber = _getString(jsonObj, "platenumber")

                        lon = _getString(jsonObj, "longitude")
                        lat = _getString(jsonObj, "latitude")

                        if CommonUtil.isNotBlank(lon):
                            trailBo.lon = Decimal(lon)  # new BigDecimal(str) -> Decimal(str)（重点差异第7条）
                        if CommonUtil.isNotBlank(lat):
                            trailBo.lat = Decimal(lat)

                        trailBo.devCode = trailBo.standardCode
                        trailBo.devName = trailBo.locationName

                        # 判断和当前时间相差24小时就不加
                        if CommonUtil.isNull(self.isLocalhost) == "local":
                            josnList.append(trailBo)
                        else:
                            if CommonUtil.isNotBlank(trailBo.captureTime):
                                try:
                                    captureTimeDate1 = _parseLenient(trailBo.captureTime, fmtDateTime)
                                    captureTimeDate2 = datetime.now()  # new Date()
                                    diff = abs(_millis(captureTimeDate2) - _millis(captureTimeDate1))  # Math.abs
                                    if diff <= threeMinutesInMillis:
                                        josnList.append(trailBo)
                                except Exception as e:
                                    log.info(f"实时轨迹日期解析失败------------{e}")

                    rtnList = self.mapTrailBoList(josnList)
                    # 最后一个轨迹点需要查询
                    if rtnList is not None and len(rtnList) > 0:

                        # Java sdf.format(new Date()) -> Python
                        formattedDate = _formatDate(datetime.now(), "%Y%m%d")

                        tracks = ZdataTrailTracks()
                        tracks.plateKey = carNo
                        tracks.uuid = carNo + "@@" + formattedDate
                        tracks.flag = "currentTrack"  # 实时轨迹

                        trailInfo = self.changeData(tracks, rtnList)  # 获取设备的经纬度

                        trailInfo.trailUuid = carNo

                        key = Constants.car_curent_trail + carNo
                        self.redisCache.setCacheObject(key, trailInfo)

    def changeData(self, tracks: ZdataTrailTracks, josnList: list) -> TrailInfo:
        """
        数据转换

        @param josnList
        @return 结果
        """
        trailInfo = TrailInfo()

        if josnList is not None and len(josnList) > 0:
            pass  # 原Java此处为空 if 块（`if(...){ }else{...}`），像素级保留结构
        else:
            trailInfo.tracks = tracks
            tempList = []
            trailInfo.trailList = tempList
            return trailInfo

        serviceAreaCaptureUUids = ""  # 服务区抓拍

        for trailBo in josnList:
            pointUuid = trailBo.pointUuid
            stateType = CommonUtil.isNull(trailBo.stateType)
            if stateType == self.SERVICE_AREA_CAPTURE:
                serviceAreaCaptureUUids += pointUuid + ","  # Java 字符串 += ：Python 等价但性能更差，
                # 重点差异：Java编译器会优化为StringBuilder，Python循环拼接是O(n^2)；
                # 为像素级一致保留写法（数据量小，无实际影响）。

        # 服务区抓拍（原Java 420~424为注释代码，像素级保留）
        # fwqcllsMap = {}
        # serviceAreaCaptureUUids = CommonUtil.deleteEnd(serviceAreaCaptureUUids)
        # if CommonUtil.isNotBlank(serviceAreaCaptureUUids):
        #     fwqcllsMap = self.fwqcllsService.selectOdsCxztFwqcllsByQueryUuids(serviceAreaCaptureUUids)

        # 收费站ip
        szdnTollMap = self.odsSzdnTollStationIpService.selectStationIpMap()

        # 收费站code
        odsSzdnTollMap = self.odsSzdnTollService.getRedisMap()

        # 门架IP
        szdnGantryMap = self.odsSzdnGantryIpService.selectOdsSzdnGantryIpMap()

        # 位置信息
        locationMap = self.zdataLocationDictService.getRedisList()

        # 服务区信息（原Java 439~440为注释代码）
        # serviceNameMap = self.fwqjcxxService.getServiceNameMap()

        # 根据路段查询路线map
        sectionMap = self.sectionService.getSectionMap()

        firtStationCode = ""
        # 入栈口名称
        firtStationName = ""
        # 入栈口时间
        firtStationTime = ""

        """ 车牌颜色（字典：1白色2黑色） """
        plateColor = ""

        """ 车型 """
        carType = ""

        """ 车种 """
        carVehicle = ""

        """ 轴数 """
        carNum = None  # Java Long carNum = null -> Python None（重点差异：无包装类型）

        # 1-OBU 2-CPC卡 3-纸券 9-无通行介质,4- M1卡
        passType = ""

        # 查询类型
        # 重点差异：Java switch 无 default 分支，未命中时保留上一轮循环的旧值；
        # 下方 if/elif 链不加 else 分支以精确复刻该"状态泄漏"行为（请勿"顺手修复"）。
        indexType = ""

        for trailBo in josnList:
            # --------------抓拍信息
            pointUuid = trailBo.pointUuid
            locationCode = CommonUtil.isNull(trailBo.locationCode)  # 设备IP地址
            stateType = CommonUtil.isNull(trailBo.stateType)  # 流水来源类型标识:可作为维度字段，用于回溯数据来源、确定查找目标表

            sectionCode = CommonUtil.isNull(trailBo.sectionCode)
            pileno = CommonUtil.isNull(trailBo.pileno)
            lon = trailBo.lon
            lat = trailBo.lon  # !!! 原Java第482行即为 getLon()（疑似笔误：lat 取了 lon），
            # 用户要求"像素级重构、不修复原逻辑"，此处一比一保留（重点注释）。

            roadCode = ""

            # 这个要查询数据库拿---
            if CommonUtil.isNotBlank(sectionCode):
                if sectionCode in sectionMap:  # Java containsKey -> Python in（语义一致）
                    section = sectionMap[sectionCode]
                    roadCode = CommonUtil.isNull(section.roadCode)
                    trailBo.roadCode = roadCode

            # Java switch(stateType){ case 常量: ... } -> if/elif 链（重点差异第6条：
            # Python match-case 无法用"类属性常量"作字面模式，裸名会变成捕获模式，故不用 match）
            if stateType == self.BORDER_WEIGHING_CAPTURE:
                # 省界称重
                indexType = "gantryType"  # 门架
            elif stateType == self.GANTRY_CAPTURE:
                # 门架抓拍
                indexType = "gantryType"  # 门架
            elif stateType == self.PROV_CAPTURE:
                # 省界抓拍
                indexType = "gantryType"  # 门架
            elif stateType == self.SERVICE_AREA_CAPTURE:
                # 服务区抓拍
                indexType = "service_area"  # 服务区
            elif stateType == self.STATION_CAPTURE:
                # 收费站抓拍
                indexType = "stationType"  # 收费站
            elif stateType == self.FeeRecord:
                # 卡口流水
                indexType = "gantryType"  # 门架
            elif stateType == self.FeeStationEnter:
                # 收费站入口流水
                indexType = "stationType"  # 收费站
            elif stateType == self.FeeStationExit:
                # 收费站出口流水
                indexType = "stationType"  # 收费站

            # ---------------通过位置信息查询设备
            devLocatCode = ""
            if locationCode in locationMap:
                devLocatCode = CommonUtil.isNull(locationMap[locationCode].standardCode)  # 收费站/门架code

            devCodeId = CommonUtil.isNull(trailBo.devCode)  # 通过设备编码先查询

            if indexType == "stationType":
                # 收费站ip 或者CODE查询
                stationIpBO = None

                # 从位置信息
                if CommonUtil.isNotBlank(devLocatCode):
                    stationIpBO = szdnTollMap.get(devLocatCode)

                # 从设备id拿
                if stationIpBO is None:
                    # 从设备id拿
                    if CommonUtil.isNotBlank(devCodeId):
                        stationIpBO = szdnTollMap.get(devCodeId)

                # 从当前位置拿
                if stationIpBO is None:
                    if CommonUtil.isNotBlank(locationCode):
                        stationIpBO = szdnTollMap.get(locationCode)

                if stationIpBO is not None:
                    # trailBo.stationIpBO = stationIpBO
                    # trailBo.locationFlag = "1"  # 有数据（原Java 564~565为注释代码）

                    stationIpBO_toll = stationIpBO  # Java 变量 stationIpBO 直接沿用即可，此处仅提高可读性
                    trailBo.devCode = stationIpBO_toll.tollCode  # 设备编号
                    trailBo.devName = stationIpBO_toll.tollName  # 设备名称

                    odsSzdnToll = stationIpBO_toll.odsSzdnToll
                    if odsSzdnToll is not None:

                        if lon is None:
                            # 经度
                            if CommonUtil.isNotBlank(odsSzdnToll.longitude):
                                trailBo.lon = Decimal(odsSzdnToll.longitude)

                        if lat is None:
                            # 经度
                            if CommonUtil.isNotBlank(odsSzdnToll.latitude):
                                trailBo.lat = Decimal(odsSzdnToll.latitude)

                        if CommonUtil.isBlank(roadCode):
                            # 路线编号
                            trailBo.roadCode = CommonUtil.isNull(odsSzdnToll.roadCode)

                        if CommonUtil.isBlank(sectionCode):
                            # 路段
                            trailBo.sectionCode = CommonUtil.isNull(odsSzdnToll.sectionCode)

                        if CommonUtil.isBlank(pileno):
                            # 桩号
                            trailBo.pileno = CommonUtil.isNull(odsSzdnToll.pileNo)

                        # trailBo.direction = odsSzdnToll.direction  # 方向（原Java注释）

            elif indexType == "gantryType":
                # 门架ip
                gantryIpBO = None

                # 从位置信息
                if CommonUtil.isNotBlank(devLocatCode):
                    gantryIpBO = szdnGantryMap.get(devLocatCode)

                # 从设备id拿
                if gantryIpBO is None:
                    # 从设备id拿
                    if CommonUtil.isNotBlank(devCodeId):
                        gantryIpBO = szdnGantryMap.get(devCodeId)

                # 从当前位置拿
                if gantryIpBO is None:
                    if CommonUtil.isNotBlank(locationCode):
                        gantryIpBO = szdnGantryMap.get(locationCode)

                if gantryIpBO is not None:
                    # trailBo.gantryIpBO = gantryIpBO
                    # trailBo.locationFlag = "1"  # 有数据（原Java 634~635为注释代码）

                    trailBo.devCode = gantryIpBO.gantryCode  # 设备编号
                    trailBo.devName = gantryIpBO.gantryName  # 设备名称

                    odsSzdnGantry = gantryIpBO.odsSzdnGantry
                    if odsSzdnGantry is not None:

                        if lon is None:
                            # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.lon):
                                trailBo.lon = Decimal(odsSzdnGantry.lon)  # 经度

                        if lat is None:
                            # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.lat):
                                trailBo.lat = Decimal(odsSzdnGantry.lat)  # 经度

                        if CommonUtil.isBlank(roadCode):
                            # 路线编号
                            trailBo.roadCode = CommonUtil.isNull(odsSzdnGantry.roadCode)

                        if CommonUtil.isBlank(sectionCode):
                            # 路段编号
                            trailBo.sectionCode = CommonUtil.isNull(odsSzdnGantry.sectionCode)

                        if CommonUtil.isBlank(pileno):
                            # 桩号
                            trailBo.pileno = CommonUtil.isNull(odsSzdnGantry.pileNo)  # 桩号

                        trailBo.direction = odsSzdnGantry.direction  # 方向

                        # 虚拟门架
                        trailBo.isVirtual = odsSzdnGantry.isVirtual

            elif indexType == "service_area":
                # log.info("轨迹点服务区的地址：" + locationCode)
                # 服务区
                # Java replaceAll 是正则替换；模式 "devip:" 无正则元字符，Python replace 等价（重点差异第13条）
                locationCode = locationCode.replace("devip:", "serviceip:")
                if locationCode in locationMap:
                    # log.info("找到服务区：" + locationCode)
                    locationDict = locationMap[locationCode]

                    trailBo.devCode = locationDict.standardCode  # 设备编号
                    trailBo.devName = locationDict.name  # 设备名称

                    # 经度
                    if locationDict.longitude is not None:
                        trailBo.lon = locationDict.longitude

                    # 经度
                    if locationDict.latitude is not None:
                        trailBo.lat = locationDict.latitude

                    # 路线编号
                    trailBo.roadCode = CommonUtil.isNull(locationDict.roadcode)

                    # 路段
                    trailBo.sectionCode = CommonUtil.isNull(locationDict.sectioncode)

                    # 桩号
                    trailBo.pileno = CommonUtil.isNull(locationDict.pileNo)

                    trailBo.direction = locationDict.direction  # 方向

                    # （原Java 712~731为整段空注释代码块，内容均为空if体，从略）

            # 设备名称没有默认位置信息--------------
            if CommonUtil.isBlank(trailBo.devName):
                trailBo.devName = CommonUtil.isNull(locationCode).replace("serviceip:", "")

        tracks.firtStationCode = firtStationCode
        tracks.firtStationName = firtStationName
        tracks.firtStationTime = firtStationTime
        tracks.plateColor = plateColor
        tracks.carType = carType
        tracks.carVehicle = carVehicle
        tracks.carNum = carNum
        tracks.passType = passType

        # -------------------------获取起点 终点 的经纬度
        jwdList = []
        if josnList is not None and len(josnList) > 0:
            for trailBo in josnList:
                if trailBo.lon is not None and trailBo.lat is not None:
                    jwdList.append(trailBo)

        if CommonUtil.isNull(tracks.flag) == "currentTrack":
            # 实时轨迹
            if jwdList is not None and len(jwdList) > 0:
                firstTrailBo = jwdList[0]  # Java list.get(0) -> Python 下标（重点差异：越界时
                # Java 抛 IndexOutOfBoundsException，Python 抛 IndexError，语义等价）

                tracks.entollstationid = CommonUtil.isNull(firstTrailBo.devCode)
                tracks.entollstationname = CommonUtil.isNull(firstTrailBo.devName)
                tracks.startLon = CommonUtil.isNull(firstTrailBo.lon)  # 经度
                tracks.stratLat = CommonUtil.isNull(firstTrailBo.lat)  # 经度

                if len(jwdList) > 1:
                    endTrailBo = jwdList[len(jwdList) - 1]  # 也可写 jwdList[-1]，为对照保留原式
                    tracks.extollstationid = CommonUtil.isNull(endTrailBo.devCode)
                    tracks.extollstationname = CommonUtil.isNull(endTrailBo.devName)
                    tracks.endLon = CommonUtil.isNull(endTrailBo.lon)  # 经度
                    tracks.endLat = CommonUtil.isNull(endTrailBo.lat)  # 经度
        else:
            # 历史轨迹：
            firstCode = CommonUtil.isNull(tracks.entollstationid)  # 入口收费站编号
            firstName = CommonUtil.repalaceSzdnTollName(tracks.entollstationname)  # 入口收费站名称
            endCode = CommonUtil.isNull(tracks.extollstationid)  # 出口收费站编号
            endName = CommonUtil.repalaceSzdnTollName(tracks.extollstationname)  # 出口收费站名称

            if CommonUtil.isNotBlank(firstCode):
                # 收费站ip
                if firstCode in odsSzdnTollMap:
                    odsSzdnToll = odsSzdnTollMap[firstCode]
                    if odsSzdnToll is not None:
                        if CommonUtil.isNotBlank(odsSzdnToll.longitude):
                            tracks.startLon = odsSzdnToll.longitude  # 经度
                        if CommonUtil.isNotBlank(odsSzdnToll.latitude):
                            tracks.stratLat = odsSzdnToll.latitude  # 经度
                        tracks.entollstationid = CommonUtil.isNull(odsSzdnToll.tollCode)
                else:
                    # 门架
                    if firstCode in szdnGantryMap:
                        gantryIpBO = szdnGantryMap[firstCode]
                        odsSzdnGantry = gantryIpBO.odsSzdnGantry
                        if odsSzdnGantry is not None:
                            if CommonUtil.isNotBlank(odsSzdnGantry.lon):
                                tracks.startLon = odsSzdnGantry.lon  # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.lat):
                                tracks.stratLat = odsSzdnGantry.lat  # 经度
            # （重点差异注释：原Java此处 else 分支链在 821 行结束，与后续"按名称兜底"独立执行）

            # --------- 如果拿不到就根据名称来拿
            if CommonUtil.isBlank(tracks.startLon):
                if CommonUtil.isNotBlank(firstName):
                    # 收费站ip
                    if firstName in szdnTollMap:
                        stationIpBO = szdnTollMap[firstName]
                        odsSzdnToll = stationIpBO.odsSzdnToll
                        if odsSzdnToll is not None:
                            if CommonUtil.isNotBlank(odsSzdnToll.longitude):
                                tracks.startLon = odsSzdnToll.longitude  # 经度
                            if CommonUtil.isNotBlank(odsSzdnToll.latitude):
                                tracks.stratLat = odsSzdnToll.latitude  # 经度
                        tracks.entollstationid = CommonUtil.isNull(stationIpBO.tollCode)
                    else:
                        # 门架
                        if firstName in szdnGantryMap:
                            gantryIpBO = szdnGantryMap[firstName]
                            odsSzdnGantry = gantryIpBO.odsSzdnGantry
                            if odsSzdnGantry is not None:
                                if CommonUtil.isNotBlank(odsSzdnGantry.lon):
                                    tracks.startLon = odsSzdnGantry.lon  # 经度
                                if CommonUtil.isNotBlank(odsSzdnGantry.lat):
                                    tracks.stratLat = odsSzdnGantry.lat  # 经度
                            tracks.entollstationid = CommonUtil.isNull(gantryIpBO.gantryCode)

            if CommonUtil.isNotBlank(endCode):
                # 收费站ip
                if endCode in odsSzdnTollMap:
                    odsSzdnToll = odsSzdnTollMap[endCode]
                    if odsSzdnToll is not None:
                        if CommonUtil.isNotBlank(odsSzdnToll.longitude):
                            tracks.endLon = odsSzdnToll.longitude  # 经度
                        if CommonUtil.isNotBlank(odsSzdnToll.latitude):
                            tracks.endLat = odsSzdnToll.latitude  # 经度
                        tracks.extollstationid = CommonUtil.isNull(odsSzdnToll.tollCode)
                else:
                    # 门架
                    if endCode in szdnGantryMap:
                        gantryIpBO = szdnGantryMap[endCode]
                        odsSzdnGantry = gantryIpBO.odsSzdnGantry
                        if odsSzdnGantry is not None:
                            if CommonUtil.isNotBlank(odsSzdnGantry.lon):
                                tracks.endLon = odsSzdnGantry.lon  # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.lat):
                                tracks.endLat = odsSzdnGantry.lat  # 经度

            # --------- 如果拿不到就根据名称来拿
            if CommonUtil.isBlank(tracks.endLon):
                if CommonUtil.isNotBlank(endName):
                    # 收费站ip
                    if endName in szdnTollMap:
                        stationIpBO = szdnTollMap[endName]
                        odsSzdnToll = stationIpBO.odsSzdnToll
                        if odsSzdnToll is not None:
                            if CommonUtil.isNotBlank(odsSzdnToll.longitude):
                                tracks.endLon = odsSzdnToll.longitude  # 经度
                            if CommonUtil.isNotBlank(odsSzdnToll.latitude):
                                tracks.endLat = odsSzdnToll.latitude  # 经度
                        tracks.extollstationid = CommonUtil.isNull(stationIpBO.tollCode)
                    else:
                        # 门架
                        if endName in szdnGantryMap:
                            gantryIpBO = szdnGantryMap[endName]
                            odsSzdnGantry = gantryIpBO.odsSzdnGantry
                            if odsSzdnGantry is not None:
                                if CommonUtil.isNotBlank(odsSzdnGantry.lon):
                                    tracks.endLon = odsSzdnGantry.lon  # 经度
                                if CommonUtil.isNotBlank(odsSzdnGantry.lat):
                                    tracks.endLat = odsSzdnGantry.lat  # 经度
                            tracks.extollstationid = CommonUtil.isNull(gantryIpBO.gantryCode)

            # 如果获取的经纬度为空的话（原Java 926~940为注释代码，像素级保留）
            # if CommonUtil.isBlank(tracks.startLon):
            #     if jwdList is not None and len(jwdList) > 0:
            #         firstTrailBo = jwdList[0]
            #         tracks.startLon = CommonUtil.isNull(firstTrailBo.lon)  # 经度
            #         tracks.stratLat = CommonUtil.isNull(firstTrailBo.lat)  # 经度
            # if CommonUtil.isBlank(tracks.endLon):
            #     if jwdList is not None and len(jwdList) > 1:
            #         endTrailBo = jwdList[len(jwdList) - 1]
            #         tracks.endLon = CommonUtil.isNull(endTrailBo.lon)  # 经度
            #         tracks.endLat = CommonUtil.isNull(endTrailBo.lat)  # 经度

        if CommonUtil.isNotBlank(tracks.startLon):
            tracks.startLonDec = Decimal(tracks.startLon)
        if CommonUtil.isNotBlank(tracks.stratLat):
            tracks.stratLatDec = Decimal(tracks.stratLat)
        if CommonUtil.isNotBlank(tracks.endLon):
            tracks.endLonDec = Decimal(tracks.endLon)
        if CommonUtil.isNotBlank(tracks.endLat):
            tracks.endLatDec = Decimal(tracks.endLat)

        trailInfo.tracks = tracks
        trailInfo.trailList = josnList

        return trailInfo

    def getByTrailBo(self, trailBo: TrailBo) -> TrailBo:
        """
        获取抓拍对象
        @param trailBo
        @return
        """
        if trailBo is None:
            return TrailBo()

        borderWeighingCaptureUUids = ""  # 省界称重
        gantryCaptureUUids = ""  # 门架抓拍
        provCaptureUUids = ""  # 省界抓拍
        serviceAreaCaptureUUids = ""  # 服务区抓拍
        stationCaptureUUids = ""  # 收费站抓拍
        feeRecordUUids = ""  # 卡口流水
        feeStationEnterUUids = ""  # 收费站入口流水
        feeStationExitUUids = ""  # 收费站出口流水

        captureTime = CommonUtil.isNull(trailBo.captureTime)
        applyTime1 = ""
        applyTime2 = ""
        if CommonUtil.isNotBlank(captureTime):
            # 获取开始时间
            # 重点差异（本方法核心坑位）：Java SimpleDateFormat("yyyy-MM-dd").parse()
            # 是宽松解析——输入 "2025-10-14 13:46:42" 只取日期前缀即成功；
            # Python strptime 严格匹配会抛 ValueError。故用 _parseLenient 模拟（见文件头第8条）。
            fmtDate = "%Y-%m-%d"
            try:
                captureTimeDate1 = _parseLenient(captureTime, fmtDate)
                baseQueryTime = _formatDate(captureTimeDate1, fmtDate)
                applyTime1 = baseQueryTime + " 00:00:00"
                applyTime2 = baseQueryTime + " 23:59:59"
            except Exception as e:
                log.info(f"日期解析失败------------{e}")

        stateType = CommonUtil.isNull(trailBo.stateType)
        pointUuid = trailBo.pointUuid

        # switch -> if/elif（重点差异第6条；每个 case 的 break 即 elif 链天然互斥）
        if stateType == self.BORDER_WEIGHING_CAPTURE:
            # 省界称重
            borderWeighingCaptureUUids += pointUuid + ","
        elif stateType == self.GANTRY_CAPTURE:
            # 门架抓拍
            gantryCaptureUUids += pointUuid + ","
        elif stateType == self.PROV_CAPTURE:
            # 省界抓拍
            provCaptureUUids += pointUuid + ","
        elif stateType == self.SERVICE_AREA_CAPTURE:
            # 服务区抓拍
            serviceAreaCaptureUUids += pointUuid + ","
        elif stateType == self.STATION_CAPTURE:
            # 收费站抓拍
            stationCaptureUUids += pointUuid + ","
        elif stateType == self.FeeRecord:
            # 卡口流水
            # feeRecordUUids += pointUuid + ",";（原Java即注释）
            pass
        elif stateType == self.FeeStationEnter:
            # 收费站入口流水
            # feeStationEnterUUids += pointUuid + ",";（原Java即注释）
            pass
        elif stateType == self.FeeStationExit:
            # 收费站出口流水
            # feeStationExitUUids += pointUuid + ",";（原Java即注释）
            pass

        # 省界称重
        # Java Map<String,X> = new HashMap<>() -> Python dict（重点差异：Java HashMap.get(null)
        # 返回null不抛错；Python dict.get(None) 同样返回None，行为一致）
        weightNewstructureMap = {}
        borderWeighingCaptureUUids = CommonUtil.deleteEnd(borderWeighingCaptureUUids)
        if CommonUtil.isNotBlank(borderWeighingCaptureUUids):
            weightNewstructureMap = self.provinceBorderVehicleWeightNewstructureService \
                .selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(borderWeighingCaptureUUids)

        # 门架抓拍
        snapshotFlowAddcodeMap = {}
        gantryCaptureUUids = CommonUtil.deleteEnd(gantryCaptureUUids)
        if CommonUtil.isNotBlank(gantryCaptureUUids):
            snapshotFlowAddcodeMap = self.snapshotFlowAddcodeService \
                .selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(gantryCaptureUUids, applyTime1, applyTime2)

        # 省界抓拍
        provcaptureAddcodeMap = {}
        provCaptureUUids = CommonUtil.deleteEnd(provCaptureUUids)
        if CommonUtil.isNotBlank(provCaptureUUids):
            provcaptureAddcodeMap = self.provcaptureAddcodeService \
                .selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(provCaptureUUids)

        # 服务区抓拍
        fwqcllsMap = {}
        serviceAreaCaptureUUids = CommonUtil.deleteEnd(serviceAreaCaptureUUids)
        if CommonUtil.isNotBlank(serviceAreaCaptureUUids):
            fwqcllsMap = self.fwqcllsService.selectOdsCxztFwqcllsByQueryUuids(serviceAreaCaptureUUids)

        # 收费站抓拍
        stationcaptureAddcodeMap = {}
        stationCaptureUUids = CommonUtil.deleteEnd(stationCaptureUUids)
        if CommonUtil.isNotBlank(stationCaptureUUids):
            stationcaptureAddcodeMap = self.stationcaptureAddcodeService \
                .selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(stationCaptureUUids, applyTime1, applyTime2)

        # 卡口流水
        feeRecordMap = {}
        feeRecordUUids = CommonUtil.deleteEnd(feeRecordUUids)
        if CommonUtil.isNotBlank(feeRecordUUids):
            feeRecordMap = self.feeRecords01Service \
                .selectOdsLwzxsfsjFeeRecords01ByQueryUuids(feeRecordUUids, applyTime1, applyTime2)

        # 收费站入口流水
        feeStationEnterMap = {}
        feeStationEnterUUids = CommonUtil.deleteEnd(feeStationEnterUUids)
        if CommonUtil.isNotBlank(feeStationEnterUUids):
            feeStationEnterMap = self.feeStationEnter01Service \
                .selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids(feeStationEnterUUids)

        # 收费站入口流水（原Java注释即如此，第二处"出口"，保留原文）
        feeStationExitMap = {}
        feeStationExitUUids = CommonUtil.deleteEnd(feeStationExitUUids)
        if CommonUtil.isNotBlank(feeStationExitUUids):
            feeStationExitMap = self.feeStationExit01Service \
                .selectOdsLwzxsfsjFeeStationExit01ByQueryUuids(feeStationExitUUids)

        # （原Java 1098~1108为注释代码块：查询收费站ip/门架IP/位置信息/服务区信息，像素级保留）
        # szdnTollMap = self.odsSzdnTollStationIpService.selectStationIpMap()
        # szdnGantryMap = self.odsSzdnGantryIpService.selectOdsSzdnGantryIpMap()
        # locationMap = self.zdataLocationDictService.getRedisList()
        # serviceNameMap = self.fwqjcxxService.getServiceNameMap()

        if stateType == self.BORDER_WEIGHING_CAPTURE:
            # 省界称重
            if pointUuid in weightNewstructureMap:
                borderWeighingCaptureBO = weightNewstructureMap[pointUuid]

                # 抓拍照片
                imagesStr = CommonUtil.isNull(borderWeighingCaptureBO.weighingImagesArry)
                if CommonUtil.isNotBlank(imagesStr):
                    imagesSrc = ""
                    imgesJsonArray = json.loads(imagesStr)
                    zz = 0
                    # Java for(int zz=0; zz<array.size(); zz++) -> while 下标循环（像素级保留索引写法；
                    # Python 惯用 for 迭代，此处为对照原索引语义不从简）
                    while zz < len(imgesJsonArray):
                        # Java getJSONObject(zz)：元素非对象时返回null；Python json 得到 dict/非dict，
                        # 用 isinstance 复刻"非对象即None"语义（重点差异第9条）
                        imageTempJosn = imgesJsonArray[zz] if isinstance(imgesJsonArray[zz], dict) else None
                        if imageTempJosn is not None:
                            tempImageSrc = CommonUtil.isNull(_getString(imageTempJosn, "snapPicturePath"))
                            if CommonUtil.isNotBlank(tempImageSrc):
                                imagesSrc += tempImageSrc + ","
                        zz += 1
                    trailBo.imagesArry = CommonUtil.deleteEnd(imagesSrc)  # 抓拍照片
        elif stateType == self.GANTRY_CAPTURE:
            if pointUuid in snapshotFlowAddcodeMap:
                gantryCaptureBO = snapshotFlowAddcodeMap[pointUuid]
                trailBo.imagesArry = gantryCaptureBO.snappicturepath  # 抓拍照片

                # 车牌颜色
                trailBo.platecolor = CommonUtil.isNull(gantryCaptureBO.platecolor)
        elif stateType == self.PROV_CAPTURE:
            # 省界抓拍
            if pointUuid in provcaptureAddcodeMap:
                imagesSrc = ""
                provCaptureBO = provcaptureAddcodeMap[pointUuid]
                # 车牌图路径
                if CommonUtil.isNotBlank(provCaptureBO.plateimage):
                    imagesSrc += provCaptureBO.plateimage + ","

                # 车身图路径
                if CommonUtil.isNotBlank(provCaptureBO.sideimage):
                    imagesSrc += provCaptureBO.sideimage + ","

                # 车头图路径
                if CommonUtil.isNotBlank(provCaptureBO.headimage):
                    imagesSrc += provCaptureBO.headimage + ","
                trailBo.imagesArry = CommonUtil.deleteEnd(imagesSrc)  # 抓拍照片
        elif stateType == self.SERVICE_AREA_CAPTURE:
            # 服务区抓拍
            if pointUuid in fwqcllsMap:
                fwqclls = fwqcllsMap[pointUuid]
                imagesSrc = ""
                # 抓拍照片url
                if CommonUtil.isNotBlank(fwqclls.targetpicurl):
                    imagesSrc += fwqclls.targetpicurl + ","

                # 车牌照片
                if CommonUtil.isNotBlank(fwqclls.platepicurl):
                    imagesSrc += fwqclls.platepicurl + ","

                # 抓拍照片
                trailBo.imagesArry = CommonUtil.deleteEnd(imagesSrc)  # 抓拍照片
        elif stateType == self.STATION_CAPTURE:
            # 收费站抓拍
            if pointUuid in stationcaptureAddcodeMap:
                stationCapture = stationcaptureAddcodeMap[pointUuid]
                trailBo.imagesArry = stationCapture.snappicturepath  # 抓拍照片
        elif stateType == self.FeeRecord:
            # 卡口流水
            if pointUuid in feeRecordMap:
                feeRecords = feeRecordMap[pointUuid]
                trailBo.devCode = feeRecords.gantryid  # 设备编号
                trailBo.imagesArry = ""  # 抓拍照片
        elif stateType == self.FeeStationEnter:
            # 收费站入口流水
            if pointUuid in feeStationEnterMap:
                feeStationEnter = feeStationEnterMap[pointUuid]  # Java取了变量未使用（像素级保留）
                trailBo.imagesArry = ""  # 抓拍照片
        elif stateType == self.FeeStationExit:
            # 收费站出口流水
            if pointUuid in feeStationExitMap:
                feeStationExit = feeStationExitMap[pointUuid]  # Java取了变量未使用（像素级保留）
                trailBo.imagesArry = ""  # 抓拍照片

        # 图片替换----
        imagesArry = CommonUtil.deleteEnd(trailBo.imagesArry)
        trailBo.imagesArry = CommonUtil.repalacePicUrl(imagesArry)

        return trailBo

    def syncSuspiciousCar(self, carParaVO) -> dict:
        """
        同步可疑车俩

        @param carParaVO
        @return
        """
        # Java new HashMap<>() -> Python {}（重点差异：泛型键值类型 Map<ZdataTrailTracks,List<TrailBo>>
        # 在Python中无编译期约束，由类型注解读侧校验）
        return {}

    def syncSuspiciousCarQutaz(self, startNum: int, endNum: int) -> None:
        """
        同步可疑车俩：定时
        startNum : 起始页面 1  最后页面 10

        @return
        """
        pageSize = 10
        starTime = 2
        endTime = 4
        bite = Decimal("0.3")  # 门架抓拍和流水抓拍占比（new BigDecimal(String) -> Decimal(str)，
        # 重点差异：必须传字符串构造，Decimal(0.3) 会得到 0.2999...，与 Java BigDecimal(double) 的坑一致）

        supoerMjnum = 5  # 跨省：同步可疑车辆门架抓拍数量5个以上
        roadSupoerMjnum = 3  # 路段：门架抓拍数量和门架流水数量对比

        # -------------- 从缓存取得对应的配置
        # 重点差异：Java redisCache.<String>getCacheObject 按声明类型隐式强转；
        # Python 拿到什么就是什么，int()/Decimal() 对非 str 输入的报错方式也不同
        # （Java NumberFormatException/ClassCastException -> Python ValueError/TypeError）。
        redisTimeValue = self.redisCache.getCacheObject(self.redisTimeKey)  # 默认2天
        if CommonUtil.isNotBlank(redisTimeValue):
            starTime = int(redisTimeValue)  # Integer.parseInt -> int()
            log.info(f"从缓存取得时间配置--------：{redisTimeValue}")

        redisBiteValue = self.redisCache.getCacheObject(self.redisBiteKey)  # 比例默认为0.3
        if CommonUtil.isNotBlank(redisBiteValue):
            bite = Decimal(redisBiteValue)
            log.info(f"从缓存取得占比配置------：{bite}")

        supoerMjnumValue = self.redisCache.getCacheObject(self.supoer_mjnum)  # 比例默认为5
        if CommonUtil.isNotBlank(supoerMjnumValue):
            supoerMjnum = int(supoerMjnumValue)
            log.info(f"从缓存取得跨省：门架抓拍数量------：{supoerMjnum}")

        roadSupoeMjnumValue = self.redisCache.getCacheObject(self.road_supoer_mjnum)  # 比例默认为3
        if CommonUtil.isNotBlank(roadSupoeMjnumValue):
            roadSupoerMjnum = int(roadSupoeMjnumValue)
            log.info(f"从缓存路段：取得门架抓拍数量------：{roadSupoeMjnumValue}")

        # 判断节假日
        jholidayTimeValue = CommonUtil.isNull(self.redisCache.getCacheObject(self.jholiday_time))  # 节假日
        log.info(f"从缓存路段：取得节假日------：{jholidayTimeValue}")

        if CommonUtil.isNull(self.isLocalhost) == "local":
            log.info(f"本地配置------：{CommonUtil.isNull(self.isLocalhost)}")
            # 本地  分页1000条 30 到 1 天
            pageSize = 2000
            endTime = starTime * 2
            # starTime = 1
            # endTime = 60（原Java注释代码，像素级保留）
        else:
            log.info(f"生产配置------：{CommonUtil.isNull(self.isLocalhost)}")
            # 生产------------- 分页1000条 14 到 7 天
            pageSize = 2000
            endTime = starTime * 2

        log.info(f"分页配置：{pageSize}--时间范围{starTime}到{endTime}")

        carParaVO = CarParaVO()
        # ----------7 到 14天
        carParaVO.starTime = starTime
        carParaVO.endTime = endTime

        gantryList = self.odsSzdnGantryService.getGantryRedis()
        gantryMao = {}
        for rtnOdsSzdnGantry in gantryList:
            gantryMao[CommonUtil.isNull(rtnOdsSzdnGantry.gantryCode)] = rtnOdsSzdnGantry

        # 位置信息
        locationMap = self.zdataLocationDictService.getRedisList()

        # 根据路段查询路线map
        sectionMap = self.sectionService.getSectionMap()

        # 查询路段list
        sectionlist = self.sectionService.getSectionList()

        # 筛选的路段信息-------------
        # indexRoadCode = "G45"  # 大广高速（原Java注释）
        indexSectionCode = "200R500450649000"  # 泰赣路段编码
        indexSectionName = "泰赣路段"  # 泰赣路段
        indexRoadCodeMap = {}
        sectionsQueryList = []
        for odsSzdnSection in sectionlist:
            roadCode = CommonUtil.isNull(odsSzdnSection.roadCode)  # 路线
            sectionCode = CommonUtil.isNull(odsSzdnSection.sectionCode)  # 路段编码
            if CommonUtil.isNotBlank(roadCode) and CommonUtil.isNotBlank(sectionCode):
                # 大广高速
                if sectionCode == indexSectionCode:
                    sectionsQueryList.append(sectionCode)
                    indexRoadCodeMap[sectionCode] = roadCode

        sectionCodeList = []
        sectionCodeList.append(indexSectionCode)

        # -------可疑车辆存储时间
        now = datetime.now()  # new Date()（重点差异：datetime为不可变对象，无Date可变语义）
        formattedDate = _formatDate(now, "%Y%m%d")

        # -------获取当前时间的前2天
        # 重点差异：Java Calendar.add(DAY_OF_MONTH, -n)（可变、跨月自动进位）
        #        -> Python timedelta（不可变、同样自动处理跨月/跨年）
        currentDate = datetime.now()
        twoDaysAgo = currentDate - timedelta(days=starTime)
        queryDate = _formatDate(twoDaysAgo, "%Y-%m-%d")

        queryStartTime = queryDate + " 00:00:00"
        queryEndTime = queryDate + " 23:59:59"
        log.info(f"查询时间范围{queryStartTime}到{queryEndTime}")

        # 门架抓拍流水
        snapshotFlow = OdsRtSzdnSnapshotFlowAddcode()
        snapshotFlow.platecolor = "黄色"
        snapshotFlow.sectionList = sectionCodeList
        snapshotFlow.applyTime1 = queryStartTime
        snapshotFlow.applyTime2 = queryEndTime

        # 门架交易流水
        feeRecords01 = OdsLwzxsfsjFeeRecords01()
        feeRecords01.plateColor = "_1"
        feeRecords01.sectionList = sectionCodeList
        feeRecords01.inApplyTime1 = queryStartTime
        feeRecords01.inApplyTime2 = queryEndTime

        # 是否不是节假日
        # 重点差异：Java jholidayTimeValue.indexOf(x) > -1 -> Python `x in jholidayTimeValue`（等价子串判断）
        isNotExitsjholidayFlag = True
        if queryDate in jholidayTimeValue:
            isNotExitsjholidayFlag = False

        # 重点差异：Java for(i=startNum; i<=endNum; i++) 双闭区间
        #        -> Python range(startNum, endNum + 1)（右开，需+1对齐）
        for i in range(startNum, endNum + 1):
            # ----- 分页范围 ： 2000一次性查询
            carParaVO.startNum = pageSize
            if i > 1:
                endRange = (i - 1) * pageSize  # 当前页 -1
                carParaVO.endNum = endRange

            # 查询门架抓拍流水
            snapshotFlow.startNum = carParaVO.startNum
            snapshotFlow.endNum = carParaVO.endNum
            self.syncSnapshotFlow(snapshotFlow)

            # 门架交易流水
            feeRecords01.startNum = carParaVO.startNum
            feeRecords01.endNum = carParaVO.endNum
            self.syncFeeRecords(feeRecords01)

            # -------------轨迹点6000一次查询
            pageSizeNew = 6000
            carParaVO.startNum = pageSizeNew
            if i > 1:
                endRange = (i - 1) * pageSizeNew  # 当前页 -1
                carParaVO.endNum = endRange

            carParaVO.applyTime1 = queryStartTime
            carParaVO.applyTime2 = queryEndTime
            log.info(f"轨迹点SQL开始查询----------{datetime.now()}")
            carlistAll = self.zdataTrailTracksService.getLatestTrail(carParaVO)
            log.info(f"轨迹点SQL结束查询----------{datetime.now()}--数据：{len(carlistAll)}")

            # ---------------------------------- 跨省全程屏蔽
            carlistQspb = []
            # ---------------------------------- 关注路段屏蔽
            carlistLdpb = []

            for zdataTrailTracksVo in carlistAll:
                trailtype = CommonUtil.isNull(zdataTrailTracksVo.trailtype)

                firstCode = CommonUtil.isNull(zdataTrailTracksVo.entollstationid)  # 入口收费站编号
                firstName = CommonUtil.repalaceSzdnTollName(zdataTrailTracksVo.entollstationname)  # 入口收费站名称
                endCode = CommonUtil.isNull(zdataTrailTracksVo.extollstationid)  # 出口收费站编号
                endName = CommonUtil.repalaceSzdnTollName(zdataTrailTracksVo.extollstationname)  # 出口收费站名称

                carNo = CommonUtil.isNull(zdataTrailTracksVo.plateKey)

                # 外省进 外省出的车
                if trailtype == "0" and ("门架" in firstName) and ("门架" in endName):
                    if isNotExitsjholidayFlag:
                        carlistQspb.append(zdataTrailTracksVo)
                else:
                    # 判断是否包含大广路段
                    keyValue = zdataTrailTracksVo.trailPoints  # 行驶轨迹
                    if CommonUtil.isNotBlank(keyValue):
                        exflag = False
                        for sectionCodeValue in sectionsQueryList:
                            if sectionCodeValue in keyValue:
                                exflag = True
                        if exflag:
                            if isNotExitsjholidayFlag:
                                carlistLdpb.append(zdataTrailTracksVo)
                            trailTracksVo = TrailTracksVo()
                            trailTracksVo.plateKey = carNo
                            trailTracksVo.enterTime = zdataTrailTracksVo.enterTime
                            trailTracksVo.exitTime = zdataTrailTracksVo.exitTime

                            # 按照车牌存放当天轨迹
                            keyList = []

                            trailFittingRedisKey = self.trailFittingKey(formattedDate, carNo)
                            oldFittingList = self.redisCache.getCacheObject(trailFittingRedisKey)
                            if oldFittingList is not None and len(oldFittingList) > 0:
                                keyList = oldFittingList
                            keyList.append(trailTracksVo)

                            self.redisCache.setCacheObject(trailFittingRedisKey, keyList)

            # ---------------------------------- 跨省全程屏蔽
            if carlistQspb is not None and len(carlistQspb) > 0:
                for tracks in carlistQspb:
                    carNo = CommonUtil.isNull(tracks.plateKey)
                    keyValue = tracks.trailPoints  # 行驶轨迹
                    escapedType = ""
                    josnList = []
                    if CommonUtil.isNotBlank(keyValue):
                        josnList = self.getTrailBoList(keyValue)
                        tracks.trailPoints = ""  # 行驶轨迹
                        # ---------------------------分析场景: 门架抓拍和流水抓拍 占比
                        conutGantryCapture = 0
                        conutFeeRecord = 0
                        for rtnTrailBo in josnList:
                            stateType = CommonUtil.isNull(rtnTrailBo.stateType)
                            if stateType == self.GANTRY_CAPTURE:
                                # 门架抓拍
                                conutGantryCapture += 1  # Java conutGantryCapture++ -> +=1
                                # 重点差异：Python 无 ++ 自增运算符，也无 += 后隐式截断
                            elif stateType == self.FeeRecord:
                                # 卡口流水
                                conutFeeRecord += 1

                        # ---------------屏蔽:
                        if conutGantryCapture > supoerMjnum:
                            escapedTypeRemark = ""
                            addFlag = False
                            if conutFeeRecord == 0:
                                escapedTypeRemark = (f"跨省全程屏蔽：其中门架牌识流水数量:{conutGantryCapture}，"
                                                     f"门架交易流水数量:{conutFeeRecord}。")
                                addFlag = True
                            if addFlag:
                                escapedType = Constants.escapedType_20
                                tracks.escapedType = escapedType  # 屏蔽
                                tracks.escapedTypeRemark = escapedTypeRemark
                                tracks.escapedTfcj = "1"  # 逃费场景

                                trailInfo = self.changeData(tracks, josnList)  # 获取设备的经纬度

                                # 判断门架抓拍是否经过了虚拟门架
                                if self.getIsVirtualFlag(trailInfo.trailList):
                                    # 车牌颜色
                                    tracks.plateColor = self.getPlateColor(trailInfo.trailList)
                                    trailInfo.trailUuid = carNo

                                    key = self.getSuspiciousKey(formattedDate, carNo)
                                    self.redisCache.setCacheObject(key, trailInfo)

            # ---------------------------------- 关注路段屏蔽
            if carlistLdpb is not None and len(carlistLdpb) > 0:
                for tracks in carlistLdpb:
                    carNo = CommonUtil.isNull(tracks.plateKey)
                    keyValue = tracks.trailPoints  # 行驶轨迹
                    escapedType = ""
                    josnList = []
                    if CommonUtil.isNotBlank(keyValue):
                        josnList = self.getTrailBoList(keyValue)
                        tracks.trailPoints = ""  # 行驶轨迹

                        # ---------------------------分析场景: 路段抓拍和流水抓拍 占比
                        conutGantryCapture = 0
                        conutFeeRecord = 0

                        for rtnTrailBo in josnList:
                            sectionCode = CommonUtil.isNull(rtnTrailBo.sectionCode)  # 路段信息
                            stateType = CommonUtil.isNull(rtnTrailBo.stateType)
                            # 原Java 1558~1562为注释代码（通过位置信息查standardCode），像素级保留：
                            # locationCode = CommonUtil.isNull(rtnTrailBo.locationCode)
                            # devLocatCode = ""
                            # if locationCode in locationMap:
                            #     devLocatCode = CommonUtil.isNull(locationMap[locationCode].standardCode)

                            if CommonUtil.isNotBlank(sectionCode):
                                if sectionCode in indexRoadCodeMap:
                                    if stateType == self.GANTRY_CAPTURE:
                                        # 门架抓拍
                                        conutGantryCapture += 1
                                        # 原Java 1570~1584为注释代码（虚拟门架判断），像素级保留：
                                        # isNotXymjFlag = True
                                        # if CommonUtil.isNotBlank(devLocatCode):
                                        #     if devLocatCode in gantryMao:
                                        #         gantry = gantryMao[devLocatCode]
                                        #         if CommonUtil.isNull(gantry.isVirtual) == "1":
                                        #             isNotXymjFlag = False
                                        # if isNotXymjFlag:
                                        #     conutGantryCapture += 1
                                    elif stateType == self.FeeRecord:
                                        # 卡口流水
                                        conutFeeRecord += 1
                        # 该路段门架比例一定的--------- conutGantryCapture > 0 && conutGantryCapture > conutFeeRecord
                        if conutGantryCapture > roadSupoerMjnum:
                            # 原Java 1594注释：divide 求占比（BigDecimal.divide），此处保留注释状态
                            # costBite = (Decimal(conutFeeRecord) / Decimal(conutGantryCapture)) \
                            #     .quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                            escapedTypeRemark = ""
                            addFlag = False
                            if conutFeeRecord == 0:
                                escapedTypeRemark = (f"{indexSectionName}全程屏蔽：其中门架牌识流水数量:{conutGantryCapture}，"
                                                     f"门架交易流水数量:{conutFeeRecord}。")
                                addFlag = True
                            # 原Java 1602~1607为注释代码（部分屏蔽占比判断），像素级保留：
                            # else:
                            #     if bite >= costBite:
                            #         escapedTypeRemark = indexSectionName + "部分屏蔽：..."
                            #         addFlag = True

                            if addFlag:
                                escapedType = Constants.escapedType_20
                                tracks.escapedType = escapedType  # 屏蔽
                                tracks.escapedTypeRemark = escapedTypeRemark
                                tracks.escapedTfcj = "2"  # 路段屏蔽

                                trailInfo = self.changeData(tracks, josnList)  # 获取设备的经纬度

                                # 判断门架抓拍是否经过了虚拟门架
                                if self.getIsVirtualFlag(trailInfo.trailList):
                                    # 车牌颜色
                                    tracks.plateColor = self.getPlateColor(trailInfo.trailList)
                                    trailInfo.trailUuid = carNo

                                    key = self.getSuspiciousKey(formattedDate, carNo)
                                    self.redisCache.setCacheObject(key, trailInfo)

    def syncSuspiciousCarQutazNew(self, startNum: int, endNum: int) -> None:
        """
        同步可疑车俩：定时
        startNum : 起始页面 1  最后页面 10

        @return
        """
        pageSize = 10
        starTime = 2
        endTime = 4

        supoerMjnum = 5  # 跨省：同步可疑车辆门架抓拍数量5个以上

        # -------------- 从缓存取得对应的配置
        # 原Java 1656~1667为注释代码（读缓存配置），像素级保留：
        # redisTimeValue = self.redisCache.getCacheObject(self.redisTimeKey)  # 默认2天
        # if CommonUtil.isNotBlank(redisTimeValue):
        #     starTime = int(redisTimeValue)
        # supoerMjnumValue = self.redisCache.getCacheObject(self.supoer_mjnum)  # 比例默认为5
        # if CommonUtil.isNotBlank(supoerMjnumValue):
        #     supoerMjnum = int(supoerMjnumValue)

        # 判断节假日
        jholidayTimeValue = "2025-01-01,2025-01-02,2025-01-03"  # 节假日
        # log.info(f"从缓存路段：取得节假日------：{jholidayTimeValue}")（原Java注释）

        if CommonUtil.isNull(self.isLocalhost) == "local":
            log.info(f"本地配置------：{CommonUtil.isNull(self.isLocalhost)}")
            # 本地  分页1000条 30 到 1 天
            pageSize = 6000
            endTime = starTime * 2
            # starTime = 1
            # endTime = 60（原Java注释代码）
        else:
            log.info(f"生产配置------：{CommonUtil.isNull(self.isLocalhost)}")
            # 生产------------- 分页1000条 14 到 7 天
            pageSize = 6000
            endTime = starTime * 2

        carParaVO = CarParaVO()
        # ----------7 到 14天
        carParaVO.starTime = starTime
        carParaVO.endTime = endTime

        # 门架
        gantryList = self.odsSzdnGantryService.getGantryRedis()
        gantryMao = {}
        for rtnOdsSzdnGantry in gantryList:
            gantryMao[CommonUtil.isNull(rtnOdsSzdnGantry.gantryCode)] = rtnOdsSzdnGantry

        # 位置信息
        locationMap = self.zdataLocationDictService.getRedisList()

        # 根据路段查询路线map
        sectionMap = self.sectionService.getSectionMap()

        # -------可疑车辆存储时间
        now = datetime.now()
        formattedDate = _formatDate(now, "%Y%m%d")

        # -------获取当前时间的前2天
        currentDate = datetime.now()
        twoDaysAgo = currentDate - timedelta(days=starTime)
        queryDate = _formatDate(twoDaysAgo, "%Y-%m-%d")

        queryStartTime = queryDate + " 00:00:00"
        queryEndTime = queryDate + " 23:59:59"
        log.info(f"查询时间范围{queryStartTime}到{queryEndTime}")

        # 是否不是节假日
        isNotExitsjholidayFlag = True
        if queryDate in jholidayTimeValue:
            isNotExitsjholidayFlag = False

        fmtDateTime = "%Y-%m-%d %H:%M:%S"  # Java "yyyy-MM-dd HH:mm:ss"

        for i in range(startNum, endNum + 1):  # Java i<=endNum -> range右开+1（重点差异）

            queryStartDate = twoDaysAgo
            try:
                queryStartDate = _parseLenient(queryStartTime, fmtDateTime)
            except Exception:
                traceback.print_exc()  # e.printStackTrace() -> traceback（重点差异第16条）
                log.error(f"日期解析错误！{queryStartTime}")

            # ----- 分页范围 ： 2000一次性查询
            carParaVO.startNum = pageSize
            if i > 1:
                endRange = (i - 1) * pageSize  # 当前页 -1
                carParaVO.endNum = endRange

            carParaVO.applyTime1 = queryStartTime
            carParaVO.applyTime2 = queryEndTime

            carlistAll = []

            if isNotExitsjholidayFlag:
                # --------- 有拟合轨迹的
                log.info(f"轨迹点开始------{datetime.now()}分页配置："
                         f"{carParaVO.startNum}到{carParaVO.endNum}")
                carlistFittinglist = self.zdataTrailTracksService.getLatestTrail(carParaVO)
                log.info(f"轨迹点结束-----{datetime.now()}--数据：{len(carlistFittinglist)}")
                for zdataTrailTracksVo in carlistFittinglist:
                    zdataTrailTracksVo.flag = "1"  # 有的轨迹点
                    carlistAll.append(zdataTrailTracksVo)

                # -------------沒有拟合轨迹的  4000一次查询
                pageSizeNew = 4000
                carParaVO.startNum = pageSizeNew
                if i > 1:
                    endRange = (i - 1) * pageSizeNew  # 当前页 -1
                    carParaVO.endNum = endRange
                log.info(f"不存在轨迹点开始---{datetime.now()}分页配置："
                         f"{carParaVO.startNum}到{carParaVO.endNum}")
                carUnFittingList = self.zdataTrailTracksService.getUnFitting(carParaVO)
                log.info(f"不存在轨迹点结束----{datetime.now()}--数据：{len(carUnFittingList)}")
                for zdataTrailTracksVo in carUnFittingList:
                    zdataTrailTracksVo.uuid = StringUtils.getUUID()
                    zdataTrailTracksVo.flag = "0"  # 沒有的轨迹点
                    carlistAll.append(zdataTrailTracksVo)

            feeRecordsUuidList = []  # 门架流水轨迹点

            # 符合业务的轨迹点
            carlistRtn = []
            feeRecords01Map = {}

            for tracks in carlistAll:

                uuidValue = CommonUtil.isNull(tracks.uuid)  # 轨迹点id
                # 重点差异：Java 局部变量名 uuid 不冲突；Python 此处避免遮蔽上方 import 的
                # uuid 模块，改名 uuidValue（仅命名避让，语义与原值完全一致）。
                keyValue = tracks.trailPoints  # 行驶轨迹
                josnList = []
                if CommonUtil.isNotBlank(keyValue):
                    enterTime = tracks.enterTime
                    if enterTime is not None:
                        # 如果指定的时间 大于 轨迹开始时间的话
                        if _millis(queryStartDate) > _millis(enterTime):
                            queryStartDate = enterTime
                    josnList = self.getTrailBoList(keyValue)
                    # JSON.toJSONString(josnList)：fastjson反射序列化JavaBean ->
                    # Python json.dumps + default=_toDict（重点差异第9条；字段名顺序/
                    # null字段是否输出等细节与fastjson默认配置可能存在差异，
                    # fastjson默认跳过null，Python需按需 allow_nan/skipkeys 配置）
                    tracks.trailPoints = json.dumps(josnList, default=_toDict)
                    isNotXymjFlag = True  # 是否不包含虚拟门架
                    conutGantryCapture = 0
                    for trailBo in josnList:
                        locationCode = CommonUtil.isNull(trailBo.locationCode)  # 设备IP地址
                        stateType = CommonUtil.isNull(trailBo.stateType)  # 流水来源类型标识:可作为维度字段，用于回溯数据来源、确定查找目标表
                        if stateType == self.GANTRY_CAPTURE:
                            # 门架抓拍
                            conutGantryCapture += 1
                            if CommonUtil.isNotBlank(locationCode):
                                if locationCode in locationMap:
                                    devLocatCode = CommonUtil.isNull(locationMap[locationCode].standardCode)  # 收费站/门架code
                                    # 判断是否是虚拟门架---------
                                    if CommonUtil.isNotBlank(devLocatCode):
                                        # 找到门架信息
                                        if devLocatCode in gantryMao:
                                            gantry = gantryMao[devLocatCode]
                                            if CommonUtil.isNull(gantry.isVirtual) == "1":
                                                isNotXymjFlag = False

                    # 门架抓拍数量 > 5 并且没有经过虚拟门架
                    if conutGantryCapture > supoerMjnum and isNotXymjFlag:
                        for trailBo in josnList:
                            stateType = CommonUtil.isNull(trailBo.stateType)  # 流水来源类型标识:可作为维度字段，用于回溯数据来源、确定查找目标表
                            pointUuid = CommonUtil.isNull(trailBo.pointUuid)
                            if stateType == self.FeeRecord:
                                if CommonUtil.isNotBlank(pointUuid):
                                    feeRecordsUuidList.append(pointUuid)
                        carlistRtn.append(tracks)

            feeRecords01 = OdsLwzxsfsjFeeRecords01()
            feeRecords01.inApplyTime1 = _formatDate(queryStartDate, fmtDateTime)  # format2.format(...)
            feeRecords01.inApplyTime2 = queryEndTime

            if len(feeRecordsUuidList) > 0:
                batchSize = 2000
                if len(feeRecordsUuidList) <= batchSize:
                    # 小于1000，（原Java注释即写1000，保留原文）
                    feeRecords01.cidList = feeRecordsUuidList
                    feeRecords01List = self.queryFeeRecords01List(feeRecords01)  # 查询数据
                    for rtnFeeRecords01 in feeRecords01List:
                        feeRecords01Map[CommonUtil.isNull(rtnFeeRecords01.cid)] = rtnFeeRecords01
                else:
                    # Java: for(int yy=0; yy<list.size(); yy+=batchSize) + list.subList(yy, min(...))
                    # 重点差异第10条：Java subList 返回"视图"（与原体共享底层数组，
                    # 仅在本方法中只读传递，故与Python切片（浅拷贝）行为等价）
                    yy = 0
                    while yy < len(feeRecordsUuidList):
                        subList = feeRecordsUuidList[yy:min(yy + batchSize, len(feeRecordsUuidList))]
                        # 处理subList，例如保存到数据库或进行其他操作
                        feeRecords01.cidList = subList
                        feeRecords01List = self.queryFeeRecords01List(feeRecords01)  # 查询数据
                        for rtnFeeRecords01 in feeRecords01List:
                            feeRecords01Map[CommonUtil.isNull(rtnFeeRecords01.cid)] = rtnFeeRecords01
                        yy += batchSize

            # 生成可疑车辆
            self.separateUnfiitingList(carlistRtn, feeRecords01Map)

            # 执行完了 还原
            carlistRtn = []
            feeRecords01Map = {}

    def queryFeeRecords01List(self, feeRecords01: OdsLwzxsfsjFeeRecords01) -> list:
        """
        历史轨迹查询
        @param feeRecords01
        （原Java为 private，Python无真正私有，命名保持公开以便对照）
        """
        # 原Java 1900为注释日志，像素级保留：
        # log.info(f"门架流水开始------{datetime.now()}时间：{feeRecords01.inApplyTime1}"
        #          f"到{feeRecords01.inApplyTime2} 轨迹点数量：{len(feeRecords01.cidList)}")
        feeRecords01List = self.feeRecords01Service.selectOdsLwzxsfsjFeeRecords01ListNew(feeRecords01)
        log.info(f"门架流水结束----{datetime.now()}--数据：{len(feeRecords01List)}")
        return feeRecords01List

    def getIsVirtualFlag(self, trailList: list) -> bool:
        """
        判断是否有虚拟门架

        @param trailList
        @return
        """
        isVirtualFlag = True
        if trailList is not None and len(trailList) > 0:
            for trailBo in trailList:
                stateType = CommonUtil.isNull(trailBo.stateType)
                isVirtual = CommonUtil.isNull(trailBo.isVirtual)
                if stateType == self.GANTRY_CAPTURE and isVirtual == "1":
                    isVirtualFlag = False
        return isVirtualFlag

    def getPlateColor(self, trailList: list) -> str:
        """
        获取车牌颜色

        @param trailList
        @return
        """
        plateColor = ""
        if trailList is not None and len(trailList) > 0:
            countNum = 0
            for trailBo in trailList:
                stateType = CommonUtil.isNull(trailBo.stateType)
                if stateType == self.GANTRY_CAPTURE:
                    # 查询第一个门架抓拍的车牌号
                    if countNum == 0:
                        changeTrailBo = self.getByTrailBo(trailBo)
                        if changeTrailBo is not None:
                            plateColor = CommonUtil.isNull(changeTrailBo.platecolor)
                            return plateColor
                    countNum += 1
        return plateColor

    def carTrackQuery(self, carParaVO: CarParaVO) -> list:
        """
        查询车俩历史记录
        @param carParaVO
        @return
        """
        carlistPara = carParaVO.carlist
        if carlistPara is not None and len(carlistPara) > 0:
            # Java stream().map(CarVO::getCarNo).collect(Collectors.toList())
            # -> Python 列表推导式（重点差异第11条：语义等价，惰性/即时求值差异此处不影响结果）
            carNoList = [carVO.carNo for carVO in carlistPara]
            carParaVO.carNoList = carNoList
        carlist = self.zdataTrailTracksService.getHistoryTrail(carParaVO)
        rtnList = []
        if carlist is not None and len(carlist) > 0:
            for tracks in carlist:
                carNo = CommonUtil.isNull(tracks.plateKey)
                keyValue = tracks.trailPoints  # 行驶轨迹
                josnList = []
                if CommonUtil.isNotBlank(keyValue):
                    josnList = self.getTrailBoList(keyValue)
                    # tracks.trailPoints = ""  # 行驶轨迹（原Java即注释）

                    trailInfo = self.changeData(tracks, josnList)  # 获取设备的经纬度
                    trailInfo.trailUuid = carNo
                    rtnList.append(trailInfo)
        return rtnList

    def carTrackQueryNew(self, carParaVO: CarParaVO) -> list:
        """
        轨迹查询 : 界面上查询-------------

        @param carParaVO
        @return
        """
        carlistPara = carParaVO.carlist
        if carlistPara is not None and len(carlistPara) > 0:
            carNoList = [carVO.carNo for carVO in carlistPara]  # stream().map().collect()（同上）
            carParaVO.carNoList = carNoList
        list_ = self.zdataTrailTracksService.getHistoryTrail(carParaVO)
        # 重点差异：Java 局部变量名 list 合法；Python 中 list 是内置类型名，
        # 遮蔽后同方法内不能再使用内置list()，故改名 list_（语义完全一致）。

        return list_

    def getTrailBoListString(self, paraTrailPoints: str) -> str:
        """
        dws josn2字符串转换
        @param paraTrailPoints
        @return
        """
        trailPoints = CommonUtil.isNull(paraTrailPoints)
        if CommonUtil.isNotBlank(trailPoints):
            # Java replace 即字面量替换，与 Python replace 一致（重点差异第13条：
            # 若是 replaceAll 则需注意正则转义，此处原代码全部为 replace）
            trailPoints = trailPoints.replace("\\", "")
            trailPoints = trailPoints.replace("{\"{", "[{")
            trailPoints = trailPoints.replace("}\"}", "}]")
            trailPoints = trailPoints.replace("\",\"{", ",{")

            trailPoints = trailPoints.replace("ZdTrails:", "")
        return trailPoints

    def getTrailBoList(self, paraTrailPoints: str) -> list:
        """
        转josn
        @param paraTrailPoints
        @return
        """
        trailBoList = []
        trailPoints = self.getTrailBoListString(paraTrailPoints)
        if CommonUtil.isNotBlank(trailPoints) and trailPoints != "{}":
            try:
                # 先转josn数组 然后循环 一个一个手动赋值
                array = json.loads(trailPoints)  # JSON.parseArray -> json.loads（重点差异第9条）
                fmtIso = "%Y-%m-%dT%H:%M:%S"  # Java "yyyy-MM-dd'T'HH:mm:ss"（引号内T为字面量，
                # Python格式符中 T 本就非特殊字符，直接写字面T，输出等价）
                fmtDateTime = "%Y-%m-%d %H:%M:%S"
                for o in array:
                    jsonObj = o  # Java (JSONObject) o 显式转型 -> Python 鸭子类型无需转型
                    captureTime = _getString(jsonObj, "captureTime")
                    stateType = _getString(jsonObj, "stateType")
                    platenumber = _getString(jsonObj, "platenumber")
                    locationId = _getString(jsonObj, "locationId")
                    locationCode = _getString(jsonObj, "locationCode")
                    pointUuid = _getString(jsonObj, "pointUuid")
                    sectionCode = _getString(jsonObj, "sectionCode")
                    orgCode = _getString(jsonObj, "orgCode")
                    pileNo = _getString(jsonObj, "pileNo")
                    lon = _getString(jsonObj, "lon")
                    lat = _getString(jsonObj, "lat")
                    trailBo = TrailBo()
                    captureTime = CommonUtil.isNull(captureTime)
                    if "T" in captureTime:  # Java captureTime.indexOf("T") > -1
                        # 重点差异：若此处格式不符，Java宽松解析与Python严格解析行为不同，
                        # 统一走 _parseLenient 模拟（文件头第8条）；解析失败异常抛出方式一致：
                        # Java ParseException/ValueError 均被本方法外层 except 捕获，中断整批解析
                        dateTime = _parseLenient(captureTime, fmtIso)
                        # 步骤2：使用DateTimeFormatter转字符串
                        formattedDateStr = _formatDate(dateTime, fmtDateTime)
                        trailBo.captureTime = formattedDateStr
                    trailBo.stateType = stateType
                    trailBo.platenumber = platenumber
                    trailBo.locationId = locationId
                    trailBo.locationCode = locationCode
                    trailBo.pointUuid = pointUuid
                    trailBo.sectionCode = sectionCode
                    trailBo.orgCode = orgCode
                    trailBo.pileno = pileNo
                    if CommonUtil.isNotBlank(lon):
                        trailBo.lon = Decimal(lon)
                    if CommonUtil.isNotBlank(lat):
                        trailBo.lat = Decimal(lat)
                    trailBoList.append(trailBo)
            except Exception:
                traceback.print_exc()
                log.error(f"解析错误！{trailPoints}")
        rtnList = self.mapTrailBoList(trailBoList)

        return rtnList

    def mapTrailBoList(self, trailBoList: list) -> list:
        """
        处理 : 合并门架抓拍和收费站抓拍流水------

        @param trailBoList
        @return
        """
        mapList = []

        # 按照时间排序----------（原Java 2096~2099为注释代码：stream().sorted(Comparator...), 像素级保留）
        # if trailBoList is not None and len(trailBoList) > 0:
        #     trailBoList = sorted(trailBoList, key=lambda t: t.captureTime)

        # 去掉重合的
        fmtDateTime = "%Y-%m-%d %H:%M:%S"
        threeMinutesInMillis = 4 * 60 * 1000  # 三分钟转换为毫秒（原注释如此，实际为4分钟，像素级保留原值）

        map = {}
        if trailBoList is not None and len(trailBoList) > 0:
            for trailBo in trailBoList:
                stateType = CommonUtil.isNull(trailBo.stateType)  # 类型
                locationCode = CommonUtil.isNull(trailBo.locationCode)  # 设备IP地址
                captureTime = CommonUtil.isNull(trailBo.captureTime)  # 抓拍时间
                imagesArry = CommonUtil.deleteEnd(trailBo.imagesArry)  # 抓拍图片
                mapKey = stateType + locationCode
                if mapKey in map:
                    trailBoTemp = map[mapKey]
                    captureTimeTemp = CommonUtil.isNull(trailBoTemp.captureTime)
                    if CommonUtil.isNotBlank(captureTime) and CommonUtil.isNotBlank(captureTimeTemp):
                        try:
                            captureTimeDate1 = _parseLenient(captureTime, fmtDateTime)
                            captureTimeDate2 = _parseLenient(captureTimeTemp, fmtDateTime)
                            diff = abs(_millis(captureTimeDate2) - _millis(captureTimeDate1))
                            if diff > threeMinutesInMillis:
                                mapList.append(trailBo)
                            else:
                                # 抓拍图片累加--------------
                                imagesArryTemp = CommonUtil.deleteEnd(trailBoTemp.imagesArry)
                                if imagesArry != "":
                                    if imagesArryTemp == "":
                                        trailBoTemp.imagesArry = imagesArry
                                    else:
                                        trailBoTemp.imagesArry = imagesArryTemp + "," + imagesArry
                        except Exception as e:
                            mapList.append(trailBo)
                            log.info(f"日期解析失败------------{e}")
                    else:
                        mapList.append(trailBo)
                else:
                    mapList.append(trailBo)

                if stateType == self.GANTRY_CAPTURE or stateType == self.STATION_CAPTURE:
                    map[mapKey] = trailBo

        return mapList

    def syncSnapshotFlow(self, snapshotFlow: OdsRtSzdnSnapshotFlowAddcode) -> None:
        """
        获取门架抓拍流水

        @param snapshotFlow
        """
        log.info(f"门架抓拍流水SQL开始查询----------{datetime.now()}")
        now = datetime.now()
        redisDate = _formatDate(now, "%Y%m%d")
        # ----- 分页范围
        list_ = self.snapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeListNew(snapshotFlow)
        log.info(f"门架抓拍流水SQL结束查询----------{datetime.now()}--数据：{len(list_)}")
        for snapshotFlowAddcode in list_:
            if CommonUtil.isNotBlank(snapshotFlowAddcode.platenumber) and snapshotFlowAddcode.snapshottime is not None:
                keyList = []
                # 按照路段和车牌
                key = (CommonUtil.isNull(snapshotFlowAddcode.sectioncode) + "@@"
                       + CommonUtil.isNull(snapshotFlowAddcode.platenumber))
                redisKey = self.snapshotFlowListKey(redisDate, key)
                oldList = self.redisCache.getCacheObject(redisKey)
                # 重点差异：Java泛型 List<X> oldList 直接接住缓存对象；
                # Python 缓存层反序列化出的元素必须是同名领域类实例，否则后续属性访问才报 AttributeError
                if oldList is not None and len(oldList) > 0:
                    keyList = oldList
                keyList.append(snapshotFlowAddcode)
                self.redisCache.setCacheObject(redisKey, keyList)

    def syncFeeRecords(self, feeRecords: OdsLwzxsfsjFeeRecords01) -> None:
        """
        获取门架交易流水

        @param feeRecords
        """
        log.info(f"门架交易流水SQL开始查询----------{datetime.now()}")
        now = datetime.now()
        redisDate = _formatDate(now, "%Y%m%d")
        # ----- 分页范围
        feeRecords.orderByFlag = "order"
        list_ = self.feeRecords01Service.selectOdsLwzxsfsjFeeRecords01ListNew(feeRecords)
        log.info(f"门架交易流水SQL开始查询----------{datetime.now()}数据--{len(list_)}")
        for feeRecords01 in list_:
            vehicleplate = CommonUtil.isNull(feeRecords01.vehicleplate)  # 车牌号_颜色
            if "_" in vehicleplate:
                # 重点差异：Java split 会丢弃尾部空串（"A_".split("_")==["A"]），
                # Python split 保留（"A_".split("_")==["A",""]）；本处只取[0]，结果等价。
                vehicleplateStr = vehicleplate.split("_")
                vehicleplateChange = CommonUtil.isNull(vehicleplateStr[0])
                if CommonUtil.isNotBlank(vehicleplateChange):
                    # 按照路段和车牌
                    keyList = []
                    key = CommonUtil.isNull(feeRecords01.sectioncode) + "@@" + CommonUtil.isNull(vehicleplateChange)
                    redisKey = self.feeRecordsListKey(redisDate, key)
                    oldList = self.redisCache.getCacheObject(redisKey)
                    if oldList is not None and len(oldList) > 0:
                        keyList = oldList
                    keyList.append(feeRecords01)
                    self.redisCache.setCacheObject(redisKey, keyList)

    def separateSnapshotFlowTimeList(self) -> None:
        """
        门架抓拍流水 和 获取门架交易流水 对比
        """

        now = datetime.now()
        redisDate = _formatDate(now, "%Y%m%d")

        roadSupoerMjnum = 3  # 路段：门架抓拍数量和门架流水数量对比
        roadSupoeMjnumValue = self.redisCache.getCacheObject(self.road_supoer_mjnum)  # 比例默认为3
        if CommonUtil.isNotBlank(roadSupoeMjnumValue):
            roadSupoerMjnum = int(roadSupoeMjnumValue)
            log.info(f"从缓存路段：取得门架抓拍数量------：{roadSupoeMjnumValue}")

        thirtyMinutesInMillis = 60 * 60 * 1000  # 30分钟转换为毫秒（原注释如此，实际1小时，像素级保留）

        keys = self.redisCache.keys(Constants.snapshotFlowList + redisDate + "*")
        # 重点差异：Jedis/redis-py KEYS 返回集合；Python redis 客户端默认返回bytes，
        # 约定此处 Python 等价 RedisCache 已解码为 str 集合（重点差异第14条）
        if keys is not None and len(keys) > 0:
            for key in keys:
                keyList = self.redisCache.getCacheObject(key)
                if keyList is not None and len(keyList) >= roadSupoerMjnum:
                    # 按照车辆时间排序
                    # Java keyList.stream().sorted(Comparator.comparing(X::getSnapshottime)).collect(...)
                    # -> Python sorted()（重点差异第11条：snapshottime为None时
                    # Java抛NPE、Python抛TypeError，失败语义一致；均按datetime升序）
                    keyList = sorted(keyList, key=lambda item: item.snapshottime)

                    # 判断有几次通行
                    snapshotList = []
                    for i in range(len(keyList)):  # Java for(int i=0;i<size;i++) -> range(len(...))
                        rtndata = keyList[i]
                        if i == 0:
                            snapshotList.append(rtndata)
                        else:
                            # 时间相差1个小时之内为同一组
                            preSnapshottime = keyList[i - 1].snapshottime
                            snapshottime = rtndata.snapshottime

                            diff = abs(_millis(snapshottime) - _millis(preSnapshottime))
                            if diff > thirtyMinutesInMillis:
                                # 超过了60分钟
                                self.isFeeRecordsExist(key, snapshotList, roadSupoerMjnum, redisDate)

                                # 重新计算---------------
                                # Java snapshotList = new ArrayList<>() -> Python []
                                # （重点差异：Python列表字面量等价新建，无Java泛型参数）
                                snapshotList = []
                                snapshotList.append(rtndata)
                            else:
                                snapshotList.append(rtndata)
                    self.isFeeRecordsExist(key, snapshotList, roadSupoerMjnum, redisDate)

        # 删除redis
        if keys is not None and len(keys) > 0:
            # 删除redis
            self.redisCache.deleteObject(keys)

        freeKeys = self.redisCache.keys(Constants.feeRecordsList + redisDate + "*")
        if freeKeys is not None and len(freeKeys) > 0:
            # 删除redis
            self.redisCache.deleteObject(freeKeys)

        trailFittingKeys = self.redisCache.keys(Constants.trailFittingList + redisDate + "*")
        if trailFittingKeys is not None and len(trailFittingKeys) > 0:
            # 删除redis
            self.redisCache.deleteObject(trailFittingKeys)

    def isFeeRecordsExist(self, key: str, snapshotList: list, roadSupoerMjnum: int, redisDate: str) -> None:
        """
        对比找到可疑车辆
        @param key
        @param snapshotList
        @param roadSupoerMjnum
        """

        if (CommonUtil.isNotBlank(key) and snapshotList is not None
                and len(snapshotList) >= roadSupoerMjnum and len(snapshotList) >= 2):
            roadCarKeyStr = key.split(":")
            # 重点差异：Java split(":") 对 "a:b" 得 ["a","b"]，与Python一致；
            # 但Java会去除尾部空串，Python保留——此处只判断length>1并取[1]，结果等价。

            # 门架----------
            gantryList = self.odsSzdnGantryService.getGantryRedis()
            gantryMao = {}
            for rtnOdsSzdnGantry in gantryList:
                gantryMao[CommonUtil.isNull(rtnOdsSzdnGantry.gantryCode)] = rtnOdsSzdnGantry

            # 根据路段查询路线map
            sectionMap = self.sectionService.getSectionMap()

            stateType = self.GANTRY_CAPTURE  # 门架抓拍
            fmtDateTime = "%Y-%m-%d %H:%M:%S"

            if len(roadCarKeyStr) > 1:

                firstBo = snapshotList[0]  # 第一个
                endBo = snapshotList[len(snapshotList) - 1]  # 最后一个

                startTime = firstBo.snapshottime  # Java Date -> Python datetime
                endTime = endBo.snapshottime

                startTimeLong = _millis(startTime)
                endTimeLong = _millis(endTime)

                roadCarKey = roadCarKeyStr[1]
                sectionCode = CommonUtil.isNull(firstBo.sectioncode)

                sectionName = ""
                roadCode = ""
                if sectionCode in sectionMap:
                    odsSzdnSection = sectionMap[sectionCode]
                    sectionName = odsSzdnSection.sectionName
                    roadCode = odsSzdnSection.roadCode

                redisKey = self.feeRecordsListKey(redisDate, roadCarKey)
                isAddFlag = False
                oldList = self.redisCache.getCacheObject(redisKey)
                if oldList is not None and len(oldList) > 0:
                    freeCountNum = 0  # 计费模块响应计费结果 0 成功 1失败
                    for feeRecords01 in oldList:
                        transtime = feeRecords01.transtime
                        if transtime is not None:
                            transtimelong = _millis(transtime)
                            if startTimeLong <= transtimelong <= endTimeLong:
                                # 时间在范围里
                                # 重点差异：Java链式比较不存在，写作 a<=x&&x<=b；
                                # Python支持数学式链式比较，此处用惯用写法（语义一致）
                                fee = feeRecords01.fee
                                if fee is not None and fee > Decimal(0):
                                    # BigDecimal.compareTo(ZERO)>0 -> Decimal 直接比较（重点差异第7条）
                                    freeCountNum = freeCountNum + 1
                    if freeCountNum > 0:
                        # 有数据 后续做部分
                        pass  # Java空语句块 -> Python pass（不可省略，否则语法错误）
                    else:
                        isAddFlag = True
                else:
                    # 无数据------------
                    isAddFlag = True

                if isAddFlag:
                    carNo = firstBo.platenumber

                    trailFitting = 0  # 是否有轨迹点

                    # ------------ 判断是否有出入口轨迹
                    trailFittingRedisKey = self.trailFittingKey(redisDate, carNo)
                    oldFittingList = self.redisCache.getCacheObject(trailFittingRedisKey)
                    if oldFittingList is not None and len(oldFittingList) > 0:
                        for trailTracksVo in oldFittingList:
                            trailTtartTime = trailTracksVo.enterTime  # 进入时间
                            trailEndTime = trailTracksVo.exitTime  # 离开时间
                            if trailTtartTime is not None and trailEndTime is not None:
                                if (_millis(trailTtartTime) <= endTimeLong
                                        and endTimeLong <= _millis(trailEndTime)):
                                    trailFitting = trailFitting + 1

                    if trailFitting == 0:
                        platecolor = firstBo.platecolor

                        tracks = ZdataTrailTracks()
                        tracks.uuid = StringUtils.getUUID()
                        tracks.plateKey = carNo
                        # tracks.envehicleid = carNo（原Java注释）
                        # tracks.enaxlecount = 0
                        tracks.enterTime = startTime

                        startGantryid = CommonUtil.isNull(firstBo.gantrycode)
                        tracks.entollstationid = startGantryid
                        if startGantryid in gantryMao:
                            odsSzdnGantry = gantryMao[startGantryid]
                            tracks.entollstationname = odsSzdnGantry.gantryName  # 门架名称

                            if CommonUtil.isNotBlank(odsSzdnGantry.lon):
                                tracks.startLon = odsSzdnGantry.lon  # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.lat):
                                tracks.stratLat = odsSzdnGantry.lat  # 经度

                        tracks.envehicletype = CommonUtil.isNull(firstBo.cartypecode)  # 车型
                        tracks.envehicleid = carNo  # 车牌号

                        tracks.exitTime = endTime

                        endGantryid = CommonUtil.isNull(endBo.gantrycode)
                        tracks.extollstationid = endGantryid
                        if endGantryid in gantryMao:
                            odsSzdnGantry = gantryMao[endGantryid]
                            tracks.extollstationname = odsSzdnGantry.gantryName  # 门架名称

                            if CommonUtil.isNotBlank(odsSzdnGantry.lon):
                                tracks.endLon = odsSzdnGantry.lon  # 经度
                            if CommonUtil.isNotBlank(odsSzdnGantry.lat):
                                tracks.endLat = odsSzdnGantry.lat  # 经度

                        tracks.exvehicleid = carNo  # 车牌号

                        if CommonUtil.isNotBlank(tracks.startLon):
                            tracks.startLonDec = Decimal(tracks.startLon)
                        if CommonUtil.isNotBlank(tracks.stratLat):
                            tracks.stratLatDec = Decimal(tracks.stratLat)
                        if CommonUtil.isNotBlank(tracks.endLon):
                            tracks.endLonDec = Decimal(tracks.endLon)
                        if CommonUtil.isNotBlank(tracks.endLat):
                            tracks.endLatDec = Decimal(tracks.endLat)

                        # -------------- 车辆轨迹点
                        josnList = []
                        for snapshotBo in snapshotList:
                            trailBo = TrailBo()

                            gantryCode = CommonUtil.isNull(snapshotBo.gantrycode)

                            trailBo.stateType = stateType
                            trailBo.platenumber = snapshotBo.platenumber
                            trailBo.locationId = gantryCode
                            trailBo.locationCode = gantryCode
                            trailBo.pointUuid = snapshotBo.datauuid
                            trailBo.sectionCode = snapshotBo.sectioncode

                            captureTime = snapshotBo.snapshottime
                            if captureTime is not None:
                                trailBo.captureTime = _formatDate(captureTime, fmtDateTime)

                            trailBo.devCode = gantryCode  # 设备编号
                            if gantryCode in gantryMao:
                                odsSzdnGantry = gantryMao[gantryCode]
                                lon = odsSzdnGantry.lon
                                lat = odsSzdnGantry.lat

                                trailBo.pileno = odsSzdnGantry.pileNo  # 桩号
                                if CommonUtil.isNotBlank(lon):
                                    trailBo.lon = Decimal(lon)
                                if CommonUtil.isNotBlank(lat):
                                    trailBo.lat = Decimal(lat)

                                trailBo.devName = odsSzdnGantry.gantryName  # 设备名称

                            # 设备名称没有默认位置信息--------------
                            if CommonUtil.isBlank(trailBo.devName):
                                trailBo.devName = gantryCode

                            trailBo.roadCode = roadCode
                            josnList.append(trailBo)

                        escapedTypeRemark = (f"{sectionName}路段全程屏蔽：其中门架牌识流水数量:{len(snapshotList)}，"
                                             f"门架交易成功流水数量:0。")
                        escapedType = Constants.escapedType_20
                        tracks.escapedType = escapedType  # 屏蔽
                        tracks.escapedTypeRemark = escapedTypeRemark
                        tracks.escapedTfcj = "3"  # 路段屏蔽

                        # 车牌颜色
                        tracks.plateColor = platecolor

                        trailInfo = TrailInfo()
                        trailInfo.tracks = tracks
                        trailInfo.trailList = josnList
                        trailInfo.trailUuid = carNo

                        # 判断门架抓拍是否经过了虚拟门架
                        if self.getIsVirtualFlag(trailInfo.trailList):
                            kykey = self.getSuspiciousKey(redisDate, carNo)
                            isExistObj = self.redisCache.getCacheObject(kykey)
                            if isExistObj is None:  # Java == null -> Python is None
                                self.redisCache.setCacheObject(kykey, trailInfo)

    def separateUnfiitingList(self, carlistRtn: list, feeRecords01Map: dict) -> None:
        """
        根据 流水节点 ---和 获取门架交易流水 对比
        （原Java为 private）
        """
        now = datetime.now()
        redisDate = _formatDate(now, "%Y%m%d")
        bite = Decimal("0.5")  # 门架抓拍和流水抓拍占比

        log.info(f"生成可疑的数据开始：{datetime.now()}")
        log.info(f"参数:轨迹点数量{len(carlistRtn)}")

        if carlistRtn is not None and len(carlistRtn) > 0 and feeRecords01Map is not None:
            for tracks in carlistRtn:
                if tracks is not None:
                    carNo = CommonUtil.isNull(tracks.plateKey)
                    keyValue = tracks.trailPoints  # 行驶轨迹
                    typeFlag = CommonUtil.isNull(tracks.flag)
                    josnList = []
                    if CommonUtil.isNotBlank(keyValue):
                        # 重点差异（本方法核心）：Java JSON.parseArray(keyValue, TrailBo.class)
                        # 由fastjson反射按字段名自动填充JavaBean；
                        # Python json.loads 只能得到 list[dict]，需领域实体显式提供 fromDict
                        # 反序列化（对应关系须与Java字段名一致）
                        josnList = [TrailBo.fromDict(item) for item in json.loads(keyValue)]
                        if josnList is not None and len(josnList) > 0:
                            # 没有轨迹点的s
                            if typeFlag == "0":
                                tracks.flag = "currentTrack"  # 设置起点和终点

                            # ---------------------------分析场景: 路段抓拍和流水抓拍 占比
                            conutGantryCapture = 0  # 门架抓拍流水
                            conutFeeRecord = 0  # 门架抓拍流水
                            sussFeeRecord = 0  # 成功门架抓拍流水

                            for rtnTrailBo in josnList:
                                stateType = CommonUtil.isNull(rtnTrailBo.stateType)
                                pointUuid = CommonUtil.isNull(rtnTrailBo.pointUuid)
                                if stateType == self.GANTRY_CAPTURE:
                                    # 门架抓拍
                                    conutGantryCapture += 1
                                elif stateType == self.FeeRecord:
                                    # 卡口流水
                                    conutFeeRecord += 1
                                    if CommonUtil.isNotBlank(pointUuid):
                                        feeRecordObj = feeRecords01Map.get(pointUuid)
                                        if feeRecordObj is not None:
                                            # Java显式向下转型 (OdsLwzxsfsjFeeRecords01) feeRecordObj；
                                            # Python鸭子类型无需转型（若类型不符在属性访问时才报错——重点差异）
                                            rtnFeeRecords01 = feeRecordObj
                                            fee = rtnFeeRecords01.fee
                                            if fee is not None and fee > Decimal(0):
                                                sussFeeRecord += 1

                            addFlag = False
                            escapedTfcj = ""  # 逃费场景
                            escapedTypeRemark = ""  # 场景描述
                            escapedType = ""
                            if conutFeeRecord == 0:
                                # 全屏蔽
                                escapedTypeRemark = (f"全程屏蔽：其中门架牌识流水数量:{conutGantryCapture}，"
                                                     f"门架交易流水数量:{conutFeeRecord}。")
                                escapedTfcj = "1"
                                escapedType = Constants.escapedType_20
                                addFlag = True
                            else:
                                if sussFeeRecord == 0:
                                    escapedTypeRemark = (f"全程屏蔽(交易成功)：其中门架牌识流水数量:{conutGantryCapture}，"
                                                         f"门架交易流水数量:{conutFeeRecord}，，"
                                                         f"门架交易流水成功数量:{sussFeeRecord}。")
                                    escapedTfcj = "3"
                                    escapedType = Constants.escapedType_20
                                    addFlag = True
                                else:
                                    # BigDecimal.divide(divisor, 4, ROUND_HALF_UP) ->
                                    # (a / b).quantize(Decimal("0.0001"), ROUND_HALF_UP)（重点差异第7条）
                                    # 除零：Java ArithmeticException <-> Python decimal.DivisionByZero
                                    # （ZeroDivisionError的ArithmeticError同族，均未被本方法捕获，直接上抛）
                                    costBite = (Decimal(conutFeeRecord) / Decimal(sussFeeRecord)) \
                                        .quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                                    if bite >= costBite:  # BigDecimal.compareTo(x)>=0 -> Decimal >= 比较
                                        escapedTypeRemark = (f"部分屏蔽(交易成功)：其中门架牌识流水数量:{conutGantryCapture}，"
                                                             f"门架交易流水数量:{conutFeeRecord}，，"
                                                             f"门架交易流水成功数量:{sussFeeRecord}。")
                                        escapedTfcj = "2"
                                        escapedType = Constants.escapedType_20
                                        addFlag = True

                            if addFlag:
                                tracks.escapedTfcj = escapedTfcj  # 逃费场景
                                tracks.escapedType = escapedType  #
                                tracks.escapedTypeRemark = escapedTypeRemark

                                trailInfo = self.changeData(tracks, josnList)  # 获取设备的经纬度

                                # 车牌颜色
                                tracks.plateColor = self.getPlateColor(trailInfo.trailList)
                                trailInfo.trailUuid = carNo

                                suspiciousKey = self.getSuspiciousKey(redisDate, carNo)
                                self.redisCache.setCacheObject(suspiciousKey, trailInfo)

        log.info(f"生成可疑车辆的数据结束：{datetime.now()}")

    def syncSuspiciousCarDB(self) -> None:
        """
        数据推送
        """
        # 从redis拿
        trailInfoList = []
        now = datetime.now()
        formattedDate = _formatDate(now, "%Y%m%d")

        keys = self.redisCache.keys(Constants.car_uspicious + formattedDate + "*")
        if keys is not None and len(keys) > 0:
            for key in keys:
                trailInfo = self.redisCache.getCacheObject(key)
                trailInfoList.append(trailInfo)

        # 签名key
        signatureKey = "car_monit_pt"

        # 时间戳(毫秒)
        # System.currentTimeMillis() -> 封装为毫秒整数（重点差异第8条：Java返回long原生毫秒）
        timeStamp = _millis(datetime.now())

        # 签名
        # Java signatureKey + timeStamp 自动把Long转字符串；
        # Python 必须显式 str(timeStamp)（重点差异第5条）
        signature = ""
        try:
            signature = SecuritySHA1Utils.shaEncode(signatureKey + str(timeStamp))
        except Exception as e:
            # Java throw new RuntimeException(e) -> raise RuntimeError(e)（重点差异第16条；
            # 注意：Java异常链保留cause，Python此处等价于 e 作为参数的新异常，
            # 若需完整链可写 `raise RuntimeError(e) from e`，为像素级对齐采用前者）
            raise RuntimeError(e)

        suspiciousCarVO = SuspiciousCarVO()
        suspiciousCarVO.signatureKey = signatureKey
        suspiciousCarVO.timeStamp = timeStamp
        suspiciousCarVO.signature = signature
        suspiciousCarVO.trailInfoList = trailInfoList
        log.info(f"调用接口开始--------：{datetime.now()}")
        # Forest声明式HTTP客户端 -> Python需httpx/requests等价实现，
        # 返回 dict（对应Java JSONObject）——重点差异：JSON库返回类型体系不同
        jsonObject = self.httpSysUtilApiService.syncSuspiciousCarTask(suspiciousCarVO)
        # Java jsonObject.getInteger(CODE_TAG)：缺失键返回null，字符串"200"自动转Integer；
        # Python dict.get 原样返回。若远端返回字符串需手动int()转换，否则 == 200 恒为False（重点差异！）
        responseCode = jsonObject.get(AjaxResult.CODE_TAG)
        log.info(f"调用接口结束--------：{datetime.now()}")
        # fastjson toJSONString 默认输出中文不转义；Python json.dumps 默认 ensure_ascii=True
        # 会把中文转\uXXXX，此处显式 ensure_ascii=False 对齐Java输出（重点差异第9条）
        log.info(json.dumps(jsonObject, ensure_ascii=False, default=_toDict))
        if responseCode == HttpStatus.SUCCESS:
            # 重点差异：Java Integer==int 自动拆箱比较数值；Python str与int比较恒False、
            # None==200 恒False。若Python版HTTP实现未做类型归一，需在此先 int(responseCode)。
            log.info(f"调用接口成功返回--------：{datetime.now()}")
            if keys is not None and len(keys) > 0:
                # 删除redis
                self.redisCache.deleteObject(keys)
