# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.SysTestController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/SysTestController.java

定时任务触发入口（Controller 形态，供调度平台 HTTP 调用）。

【Java→Python】关键差异
1) 路由前缀 ``/base/sysutilTest`` → 类常量 ``BASE_PATH``。
2) 5 个 ``@Autowired`` + 5 个 service + 1 个 ``@Resource ThreadPoolTaskExecutor``
   → 全部改为构造器可选参数注入（缺省 ``XxxServiceImpl()`` / ``ThreadPoolTaskExecutor()``）。
3) ``@Slf4j`` → 模块级 ``log = logging.getLogger(__name__)``；
   SLF4J 的 ``"{}"`` 占位 → logging 的 ``"%s"``。
4) **lambda 捕获差异（本文件最重要的一点）**：
   Java 写成 ``int finalI = i; threadTaskExecutor.execute(() -> ...(finalI, finalI));``
   —— Java 的 lambda 捕获的是 **effectively final 的当前值**（每个循环变量独立）；
   Python 的闭包按**引用**捕获，若直接写 ``lambda: ...(i, i)``，全部任务都会拿到
   循环结束后的最后一个值。因此 Python 侧必须用**默认参数**把当前值绑定进闭包：
   ``lambda index=finalI: ...``。
5) ``new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date())`` →
   ``SimpleDateFormat`` 替身 + ``datetime.now()``（框架替身见 java/text）。
6) ``"..." + someList.size()`` 之类的字符串拼接 → ``"..." + str(len(someList))``
   （Python 不允许 str + int 隐式转换）。
7) ``(List) obj`` 强转 → 显式 ``isinstance(obj, list)`` 校验并抛 ``TypeError``
   （对应 Java 的 ``ClassCastException``）。
8) ``LocalDateTime now = LocalDateTime.now(); LocalDateTime daysBefore = now.minusDays(7);``
   —— **Java 里 daysBefore 赋值后从未使用**（原工程冗余变量），忠实保留并标注。
9) ``sectionCode.equals("200R500450649000")`` → ``sectionCode == "200R500450649000"``。
10) 局部变量 ``list`` → ``list_``；``Map`` → ``dict``，``containsKey`` → ``in``。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.CarVO import CarVO
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.TrailInfo import TrailInfo
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.service.IDwdLcztFwqjcxxService import IDwdLcztFwqjcxxService
from com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service import \
    IOdsLwzxsfsjFeeRecords01Service
from com.ruoyi.base.service.IOdsSzdnGantryIpService import IOdsSzdnGantryIpService
from com.ruoyi.base.service.IOdsSzdnGantryService import IOdsSzdnGantryService
from com.ruoyi.base.service.IOdsSzdnSectionService import IOdsSzdnSectionService
from com.ruoyi.base.service.IOdsSzdnTollService import IOdsSzdnTollService
from com.ruoyi.base.service.IOdsSzdnTollStationIpService import IOdsSzdnTollStationIpService
from com.ruoyi.base.service.ISysUtilService import ISysUtilService
from com.ruoyi.base.service.IZdataLocationDictService import IZdataLocationDictService
from com.ruoyi.base.service.impl.DwdLcztFwqjcxxServiceImpl import DwdLcztFwqjcxxServiceImpl
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeRecords01ServiceImpl import \
    OdsLwzxsfsjFeeRecords01ServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnGantryIpServiceImpl import OdsSzdnGantryIpServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnGantryServiceImpl import OdsSzdnGantryServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnSectionServiceImpl import OdsSzdnSectionServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnTollServiceImpl import OdsSzdnTollServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnTollStationIpServiceImpl import \
    OdsSzdnTollStationIpServiceImpl
from com.ruoyi.base.service.impl.SysUtilServiceImpl import SysUtilServiceImpl
from com.ruoyi.base.service.impl.ZdataLocationDictServiceImpl import ZdataLocationDictServiceImpl
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.redis.RedisCache import RedisCache
from com.ruoyi.common.utils import CommonUtil
from java.text.SimpleDateFormat import SimpleDateFormat
from java.time.LocalDateTime import LocalDateTime
from org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor import ThreadPoolTaskExecutor

__all__ = ["SysTestController"]

log = logging.getLogger(__name__)

_DATE_TIME_PATTERN = "yyyy-MM-dd HH:mm:ss"


class SysTestController(BaseController):
    """定时任务测试入口Controller。"""

    # Java: @RequestMapping("/base/sysutilTest")
    BASE_PATH = "/base/sysutilTest"

    def __init__(self,
                 redisCache: Optional[RedisCache] = None,
                 odsSzdnGantryIpService: Optional[IOdsSzdnGantryIpService] = None,
                 odsSzdnTollStationIpService: Optional[IOdsSzdnTollStationIpService] = None,
                 sysUtilService: Optional[ISysUtilService] = None,
                 odsSzdnGantryService: Optional[IOdsSzdnGantryService] = None,
                 zdataLocationDictService: Optional[IZdataLocationDictService] = None,
                 dwdLcztFwqjcxxService: Optional[IDwdLcztFwqjcxxService] = None,
                 threadTaskExecutor: Optional[ThreadPoolTaskExecutor] = None,
                 feeRecords01Service: Optional[IOdsLwzxsfsjFeeRecords01Service] = None,
                 odsSzdnTollService: Optional[IOdsSzdnTollService] = None,
                 sectionService: Optional[IOdsSzdnSectionService] = None) -> None:
        super().__init__()
        # Java: @Autowired private RedisCache redisCache;
        self.redisCache = redisCache or RedisCache()
        # Java: @Autowired private IOdsSzdnGantryIpService odsSzdnGantryIpService;
        self.odsSzdnGantryIpService = odsSzdnGantryIpService or OdsSzdnGantryIpServiceImpl()
        # Java: @Autowired private IOdsSzdnTollStationIpService odsSzdnTollStationIpService;
        self.odsSzdnTollStationIpService = (
            odsSzdnTollStationIpService or OdsSzdnTollStationIpServiceImpl())
        # Java: @Autowired private ISysUtilService sysUtilService;
        self.sysUtilService = sysUtilService or SysUtilServiceImpl()
        # Java: @Autowired private IOdsSzdnGantryService odsSzdnGantryService;
        self.odsSzdnGantryService = odsSzdnGantryService or OdsSzdnGantryServiceImpl()
        # Java: @Autowired private IZdataLocationDictService zdataLocationDictService;
        self.zdataLocationDictService = (
            zdataLocationDictService or ZdataLocationDictServiceImpl())
        # Java: @Autowired private IDwdLcztFwqjcxxService dwdLcztFwqjcxxService;
        self.dwdLcztFwqjcxxService = dwdLcztFwqjcxxService or DwdLcztFwqjcxxServiceImpl()
        # Java: @Resource private ThreadPoolTaskExecutor threadTaskExecutor;
        # Spring 容器里由 ThreadPoolConfig#taskExecutor 注册；
        # Python 侧缺省自建一个同参数实例（避免调用方忘记注册时 NPE）。
        self.threadTaskExecutor = threadTaskExecutor or self._defaultExecutor()
        # Java: @Autowired private IOdsLwzxsfsjFeeRecords01Service feeRecords01Service;
        self.feeRecords01Service = feeRecords01Service or OdsLwzxsfsjFeeRecords01ServiceImpl()
        # Java: @Autowired private IOdsSzdnTollService odsSzdnTollService;
        self.odsSzdnTollService = odsSzdnTollService or OdsSzdnTollServiceImpl()
        # Java: @Autowired private IOdsSzdnSectionService sectionService;
        self.sectionService = sectionService or OdsSzdnSectionServiceImpl()

    @staticmethod
    def _defaultExecutor() -> ThreadPoolTaskExecutor:
        """缺省线程池：与 ThreadPoolConfig#taskExecutor 相同的参数（未注册 Bean 时兜底）。"""
        # 延迟导入，避免 config → controller 的循环依赖
        from com.ruoyi.common.config.ThreadPoolConfig import ThreadPoolConfig
        return ThreadPoolConfig().taskExecutor()

    def syncCurrentTrack(self) -> None:
        """车辆实时轨迹同步（GET /base/sysutilTest/syncCurrentTrack）。"""
        log.info("每5分钟（同步当前轨迹轨迹）开始 " + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        self.sysUtilService.syncTrack(CarParaVO())
        log.info("每5分钟（同步当前轨迹轨迹）结束 " + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncBaseInfo(self) -> None:
        """同步基础信息（GET /base/sysutilTest/syncBaseInfo）。"""
        log.info("每天凌晨0点执行（同步基础信息）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        self.odsSzdnGantryService.saveGantryRedis()  # 门架信息：用于门架转名称收费流水列表
        self.odsSzdnGantryIpService.updateRedis()  # 门架ip redis
        self.odsSzdnTollStationIpService.updateRedis()  # վip redis（Java 注释原样，含乱码字符）
        self.zdataLocationDictService.updateRedis()  # 位置点信息
        self.dwdLcztFwqjcxxService.updateRedis()  # 服务区
        self.sectionService.updateRedis()  # 更新路段
        self.odsSzdnTollService.updateRedis()  # 收费站
        log.info("每天凌晨0点执行（同步基础信息）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncHistroyTrack(self) -> None:
        """同步历史轨迹（GET /base/sysutilTest/syncHistroyTrack）。"""
        log.info("每天凌晨4点执行（同步历史轨迹）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        # 重点车辆库
        carlist: List[CarVO] = []
        obj = self.redisCache.getCacheObject(Constants.car_list_jc)
        if obj is not None:
            # Java: carlist = (List) obj;（泛型擦除后仅校验 List）
            if not isinstance(obj, list):
                raise TypeError(
                    "java.lang.ClassCastException: " + type(obj).__name__
                    + " cannot be cast to java.util.List")
            carlist = obj

        if carlist is not None and len(carlist) > 0:
            sdf = SimpleDateFormat(_DATE_TIME_PATTERN)

            log.info("同步车辆数量 " + str(len(carlist)))
            for carVO in carlist:
                carNo = CommonUtil.isNull(carVO.getCarNo())
                if CommonUtil.isNotBlank(carNo):

                    # 车辆的轨迹
                    historyKey = Constants.car_history_trail + carNo
                    trailList: List[TrailInfo] = []
                    uuidMap: Dict[str, str] = {}

                    carParaVO = CarParaVO()
                    carParaVO.setCarNo(carNo)

                    # --- 同步时间存入到缓存 没有就是默认
                    timeKey = Constants.car_sync_time + carNo
                    carSynctime = CommonUtil.isNull(self.redisCache.getCacheObject(timeKey))
                    if carSynctime == "":
                        carParaVO.setFlag("bannian")  # 默认查询半年的数据
                    else:
                        # 同步时间查询
                        carParaVO.setFlag("yiyue")  # 默认查询1月
                    # carParaVO.setFlag("bannian");  // 默认查询半年的数据

                    newList: List[TrailInfo] = self.sysUtilService.carTrackQuery(carParaVO)
                    if newList is not None and len(newList) > 0:
                        for trailInfoRtn in newList:
                            tracks: ZdataTrailTracks = trailInfoRtn.getTracks()
                            tempTrailList: List[TrailBo] = trailInfoRtn.getTrailList()
                            if (tracks is not None and tempTrailList is not None
                                    and len(tempTrailList) > 0):
                                uuid = CommonUtil.isNull(tracks.getUuid())
                                trailList.append(trailInfoRtn)
                                uuidMap[uuid] = uuid

                    oldList: List[TrailInfo] = self.redisCache.getCacheObject(historyKey)
                    if oldList is not None and len(oldList) > 0:
                        for trailInfoRtn in oldList:
                            tracks: ZdataTrailTracks = trailInfoRtn.getTracks()
                            tempTrailList: List[TrailBo] = trailInfoRtn.getTrailList()
                            if (tracks is not None and tempTrailList is not None
                                    and len(tempTrailList) > 0):
                                uuid = CommonUtil.isNull(tracks.getUuid())
                                if uuid not in uuidMap:
                                    trailList.append(trailInfoRtn)

                    self.redisCache.setCacheObject(historyKey, trailList)

                    # --------同步时间
                    now = datetime.now()
                    formattedDate = sdf.format(now)
                    self.redisCache.setCacheObject(timeKey, formattedDate)

        log.info("每天凌晨4点执行（同步历史轨迹）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    # ------------------------------------------------------------------ 可疑车辆分片任务
    # 【Java→Python】下面 10 个方法的循环体在 Java 中完全相同，仅区间不同。
    # 每个方法内都写 `int finalI = i;` 再在 lambda 里使用 finalI ——
    # Python 侧用「默认参数绑定」复刻这一语义（否则闭包会共享同一个 i）。
    def syncSuspiciousCar1(self) -> None:
        """每天凌晨1点执行（同步可疑车辆）（GET /base/sysutilTest/syncSuspiciousCar1）。"""
        log.info("每天凌晨1点执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(1, 11):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨1点执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncSuspiciousCar2(self) -> None:
        """每天凌晨1点15执行（同步可疑车辆2）。"""
        log.info("每天凌晨1点15执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(11, 21):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨1点15点执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncSuspiciousCar3(self) -> None:
        """每天凌晨1点30执行（同步可疑车辆3）。"""
        log.info("每天凌晨1点30执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(21, 31):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨1点30点执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncSuspiciousCar4(self) -> None:
        """每天凌晨1点45执行（同步可疑车辆4）。"""
        log.info("每天凌晨1点45执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(31, 41):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨1点45点执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncSuspiciousCar5(self) -> None:
        """每天凌晨2点执行（同步可疑车辆5）。"""
        log.info("每天凌晨2点执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(41, 51):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨2点点执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncSuspiciousCar6(self) -> None:
        """每天凌晨2点15执行（同步可疑车辆6）。"""
        log.info("每天凌晨2点15执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(51, 61):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨2点15点执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncSuspiciousCar7(self) -> None:
        """每天凌晨2点30执行（同步可疑车辆7）。"""
        log.info("每天凌晨2点30执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(61, 71):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨2点30点执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncSuspiciousCar8(self) -> None:
        """每天凌晨2点45执行（同步可疑车辆8）。"""
        log.info("每天凌晨2点45执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(71, 81):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨2点45点执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncSuspiciousCar9(self) -> None:
        """每天凌晨3点执行（同步可疑车辆9）。"""
        log.info("每天凌晨3点执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(81, 91):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨3点执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncSuspiciousCar10(self) -> None:
        """每天凌晨3点15执行（同步可疑车辆10）。"""
        log.info("每天凌晨3点15执行（同步可疑车俩）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        for i in range(91, 101):
            finalI = i
            self.threadTaskExecutor.execute(
                lambda index=finalI: self.sysUtilService.syncSuspiciousCarQutaz(index, index))
        log.info("每天凌晨3点15执行（同步可疑车俩）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def syncOdsSzdnGantry(self) -> None:
        """同步门架信息（GET /base/sysutilTest/syncOdsSzdnGantry）。"""
        log.info("每天同步门架信息开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        gantryList: List[OdsSzdnGantry] = self.odsSzdnGantryService.getGantryRedis()
        now = LocalDateTime.now()
        # 【Java→Python】Java 里 daysBefore 只赋值、从未使用（原工程冗余变量），忠实保留
        daysBefore = now.minusDays(7)  # 时间段为7天
        for rtnOdsSzdnGantry in gantryList:
            gantryCode = CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode())
            sectionCode = CommonUtil.isNull(rtnOdsSzdnGantry.getSectionCode())
            if sectionCode == "200R500450649000":
                if CommonUtil.isNotBlank(gantryCode):
                    # Java 原文此处被块注释：
                    #   Object objNum = redisCache.getCacheObject(Constants.gantry_list_data
                    #                                               + CommonUtil.isNull(gantryCode));
                    #   if (null != objNum) { } else { }
                    odsLwzxsfsjFeeRecords01 = OdsLwzxsfsjFeeRecords01()
                    odsLwzxsfsjFeeRecords01.setInApplyTime1("2025-11-01 00-00-00")
                    odsLwzxsfsjFeeRecords01.setInApplyTime2("2025-11-12 00-00-00")
                    odsLwzxsfsjFeeRecords01.setGantryid(gantryCode)
                    count = self.feeRecords01Service.selectGantryNum(odsLwzxsfsjFeeRecords01)
                    self.redisCache.setCacheObject(Constants.gantry_list_data + gantryCode, count)

        log.info("每天凌晨同步门架信息结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    def separateSnapshotFlowTimeList(self) -> None:
        """生成可疑车辆 redis（GET /base/sysutilTest/separateSnapshotFlowTimeList）。"""
        log.info("每天凌晨4点30执行（同步可疑车辆到redis）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        self.sysUtilService.separateSnapshotFlowTimeList()
        log.info("每天凌晨4点30执行（同步可疑车辆到redis）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
