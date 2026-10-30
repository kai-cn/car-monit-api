# -*- coding: utf-8 -*-
"""com.ruoyi.base.task.TrackTask

源文件：pro-business-api/src/main/java/com/ruoyi/base/task/TrackTask.java

轨迹/基础信息同步定时任务（3 个 @Scheduled 方法）。

【Java→Python】关键差异
1) ``@Component`` + ``@EnableScheduling`` + ``@Scheduled(cron = "...")``
   → Python 用 ``org.springframework.scheduling.annotation.Scheduled`` 装饰器还原
   （元数据挂在函数属性 ``__scheduled__`` 上），由 ``app/scheduler`` 在 FastAPI
   lifespan 启动时扫描，经 ``ScheduledTaskRegistrar`` 交给 ``ThreadPoolTaskScheduler``
   按 cron 排期。三个 cron 如下：
     - ``syncCurrentTrack`` : ``0 0/3 * * * ?``   每 3 分钟
     - ``syncBaseInfo``     : ``0 0 0 * * ?``     每天 0 点
     - ``syncHistroyTrack`` : ``0 0 4 * * ?``     每天 4 点
   （方法名 ``syncHistroyTrack`` 的拼写错误来自 Java 源码，原样保留。）
2) 9 个 ``@Autowired`` → 构造器可选参数注入，缺省用对应 ``XxxServiceImpl()``；
   字段名与 Java 完全一致（camelCase），便于 Spring→Python 对照。
3) ``@Slf4j`` → 模块级 ``log``；本文件日志没有 ``{}`` 占位符，全部是字符串拼接。
4) ``new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date())``
   → ``SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now())``
   （``SimpleDateFormat`` 替身见 refactor/java/text/SimpleDateFormat.py，
   内部把 Java 模式串转成 strftime，``yyyy-MM-dd HH:mm:ss`` → ``%Y-%m-%d %H:%M:%S``）。
5) ``carlist = (List) obj;``（泛型擦除后的强制转换）→ 显式 ``isinstance(obj, list)``，
   类型不符抛 ``TypeError``（对应 Java 的 ``ClassCastException``）。
6) ``carlist.size()`` → ``len(carlist)``；``"同步车辆数量 " + carlist.size()``
   在 Python 会 TypeError，必须 ``str(len(carlist))``（Java 的 int 会自动转字符串）。
7) ``uuidMap.containsKey(uuid)`` → ``uuid in uuidMap``；``Map<String,String>`` → ``dict``。
8) ``java.util.List`` 的宽松赋值（``List<TrailInfo> oldList = redisCache.getCacheObject(...)``）
   Python 没有泛型，``getCacheObject`` 直接返回任意对象，类型由运行时决定。
9) ``private void`` → Python 无访问修饰符；方法名保持 Java 驼峰且**不加**下划线前缀
   （与 refactor 其他文件的约定一致）。
10) 原文笔误原样保留：“重点车俩库”“车俩实时轨迹同步”“同步当前轨迹轨迹”。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.CarVO import CarVO
from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.TrailInfo import TrailInfo
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.service.IDwdLcztFwqjcxxService import IDwdLcztFwqjcxxService
from com.ruoyi.base.service.IOdsSzdnGantryIpService import IOdsSzdnGantryIpService
from com.ruoyi.base.service.IOdsSzdnGantryService import IOdsSzdnGantryService
from com.ruoyi.base.service.IOdsSzdnSectionService import IOdsSzdnSectionService
from com.ruoyi.base.service.IOdsSzdnTollService import IOdsSzdnTollService
from com.ruoyi.base.service.IOdsSzdnTollStationIpService import IOdsSzdnTollStationIpService
from com.ruoyi.base.service.ISysUtilService import ISysUtilService
from com.ruoyi.base.service.IZdataLocationDictService import IZdataLocationDictService
from com.ruoyi.base.service.impl.DwdLcztFwqjcxxServiceImpl import DwdLcztFwqjcxxServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnGantryIpServiceImpl import OdsSzdnGantryIpServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnGantryServiceImpl import OdsSzdnGantryServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnSectionServiceImpl import OdsSzdnSectionServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnTollServiceImpl import OdsSzdnTollServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnTollStationIpServiceImpl import \
    OdsSzdnTollStationIpServiceImpl
from com.ruoyi.base.service.impl.SysUtilServiceImpl import SysUtilServiceImpl
from com.ruoyi.base.service.impl.ZdataLocationDictServiceImpl import ZdataLocationDictServiceImpl
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache
from com.ruoyi.common.utils import CommonUtil
from java.text.SimpleDateFormat import SimpleDateFormat
from org.springframework.scheduling.annotation.Scheduled import Scheduled

__all__ = ["TrackTask"]

# Java: @Slf4j
log = logging.getLogger(__name__)

_DATE_TIME_PATTERN = "yyyy-MM-dd HH:mm:ss"


class TrackTask(object):
    """轨迹同步定时任务（``@Component``）。"""

    def __init__(self,
                 redisCache: Optional[RedisCache] = None,
                 odsSzdnGantryIpService: Optional[IOdsSzdnGantryIpService] = None,
                 odsSzdnTollStationIpService: Optional[IOdsSzdnTollStationIpService] = None,
                 sysUtilService: Optional[ISysUtilService] = None,
                 odsSzdnGantryService: Optional[IOdsSzdnGantryService] = None,
                 zdataLocationDictService: Optional[IZdataLocationDictService] = None,
                 dwdLcztFwqjcxxService: Optional[IDwdLcztFwqjcxxService] = None,
                 sectionService: Optional[IOdsSzdnSectionService] = None,
                 odsSzdnTollService: Optional[IOdsSzdnTollService] = None) -> None:
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
        # Java: @Autowired private IOdsSzdnSectionService sectionService;
        self.sectionService = sectionService or OdsSzdnSectionServiceImpl()
        # Java: @Autowired private IOdsSzdnTollService odsSzdnTollService;
        self.odsSzdnTollService = odsSzdnTollService or OdsSzdnTollServiceImpl()

    # ------------------------------------------------------------------
    # @Scheduled(cron = "0 0/3 * * * ?")
    # ------------------------------------------------------------------
    @Scheduled(cron="0 0/3 * * * ?")
    def syncCurrentTrack(self) -> None:
        """每三分钟执行一次：车辆实时轨迹同步（cron ``0 0/3 * * * ?``）。"""
        log.info("每3分钟（同步当前轨迹轨迹）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        self.sysUtilService.syncTrack(CarParaVO())
        log.info("每3分钟（同步当前轨迹轨迹）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    # ------------------------------------------------------------------
    # @Scheduled(cron = "0 0 0 * * ?")
    # ------------------------------------------------------------------
    @Scheduled(cron="0 0 0 * * ?")
    def syncBaseInfo(self) -> None:
        """每天凌晨 0 点：同步基础信息（cron ``0 0 0 * * ?``）。

        调用顺序与 Java 一致（后面 3 行没有空格对齐，源码就是这样）：
        """
        log.info("每天凌晨0点执行（同步基础信息）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        self.odsSzdnGantryService.saveGantryRedis()  # 门架信息：用于门架转名称收费流水列表
        self.odsSzdnGantryIpService.updateRedis()  # 门架ip redis
        self.odsSzdnTollStationIpService.updateRedis()  # 站ip redis
        self.zdataLocationDictService.updateRedis()  # 位置点信息
        self.dwdLcztFwqjcxxService.updateRedis()  # 服务区
        self.sectionService.updateRedis()  # 更新路段
        self.odsSzdnTollService.updateRedis()  # 收费站
        log.info("每天凌晨0点执行（同步基础信息）结束 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))

    # ------------------------------------------------------------------
    # @Scheduled(cron = "0 0 4 * * ?")
    # ------------------------------------------------------------------
    @Scheduled(cron="0 0 4 * * ?")
    def syncHistroyTrack(self) -> None:
        """每天凌晨 4 点：同步历史轨迹（cron ``0 0 4 * * ?``）。

        与 ``SysTestController.syncHistroyTrack`` 是同一段逻辑（Java 里两处各写一遍），
        这里同样保留完整实现，不做复用。
        """
        log.info("每天凌晨4点执行（同步历史轨迹）开始 "
                 + SimpleDateFormat(_DATE_TIME_PATTERN).format(datetime.now()))
        # 重点车俩库
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
