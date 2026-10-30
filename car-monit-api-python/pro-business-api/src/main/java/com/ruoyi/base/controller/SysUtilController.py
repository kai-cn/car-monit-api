# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.SysUtilController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/SysUtilController.java

【Java→Python】关键差异
1) 路由前缀 ``/base/sysutil`` → 类常量 ``BASE_PATH``。
2) 两个 ``@Autowired``（``ISysUtilService`` + ``RedisCache``）→ 构造器注入，
   缺省 ``SysUtilServiceImpl()`` / ``RedisCache()``。
3) ``import com.ruoyi.base.domain.*`` 的通配导入 → Python 显式逐个 import
   （Python 没有“包级通配导入”的等价写法，且显式导入更利于静态检查）。
4) ``new PageInfo(list).getTotal()`` → 框架替身 ``com.github.pagehelper.PageInfo``
   （读 PageUtils 的分页上下文，无上下文时等于 len(list)）。
5) ``(List) obj`` 强转：Java 泛型擦除后只做 List 类型检查，不符抛 ``ClassCastException``；
   Python 无强转，这里显式 ``isinstance(obj, list)`` 并抛 ``TypeError``
   （行为对齐：类型不符即失败，而不是静默把 str 当列表用）。
6) ``new BigDecimal(String)`` → ``java.math.BigDecimal`` 替身 + 落库字段是 float
   （t05 的统一映射：BigDecimal → float），故赋值处写成
   ``float(BigDecimal(...))``，与 SysUtilServiceImpl 内的 ``_bdFloat`` 同一处理方式。
7) ``@GetMapping`` / ``@PostMapping`` / ``@RequestBody`` / ``@RequestParam`` 等注解
   在 Python 侧不自动注册路由：方法签名与 Java 一致，HTTP 方法/路径写在 docstring，
   请求体参数按 Java 的 ``@RequestBody`` 语义直接传对象。
8) Java 第 39~70 行是被**块注释**整段注释掉的 ``syncTrack`` / ``syncSuspiciousCar``
   （源码里因嵌套注释写成 ``/*  *//** ... *//*``），这里同样以注释保留，不翻译为方法。
9) ``for (TrailBo trailBo : trailList)`` 增强 for → ``for trail_bo in trail_list``；
   局部变量 ``list`` → ``list_``（避免遮蔽内置 list）。
"""
from __future__ import annotations

from typing import List, Optional

from com.github.pagehelper.PageInfo import PageInfo
from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.CarVO import CarVO
from com.ruoyi.base.domain.SysUtil import SysUtil
from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.TrailInfo import TrailInfo
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.service.ISysUtilService import ISysUtilService
from com.ruoyi.base.service.impl.SysUtilServiceImpl import SysUtilServiceImpl
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.constant.HttpStatus import HttpStatus
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo
from com.ruoyi.common.core.redis.RedisCache import RedisCache
from com.ruoyi.common.utils import CommonUtil
from java.math.BigDecimal import BigDecimal

__all__ = ["SysUtilController"]


class SysUtilController(BaseController):
    """系统工具Controller（轨迹查询、Redis 配置保存）。"""

    # Java: @RequestMapping("/base/sysutil")
    BASE_PATH = "/base/sysutil"

    def __init__(self,
                 sysUtilService: Optional[ISysUtilService] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        super().__init__()
        # Java: @Autowired private ISysUtilService sysUtilService;
        self.sysUtilService = sysUtilService or SysUtilServiceImpl()
        # Java: @Autowired private RedisCache redisCache;
        self.redisCache = redisCache or RedisCache()

    def saveRedis(self, sysUtil: SysUtil) -> AjaxResult:
        """保存 Redis 配置（GET /base/sysutil/saveRedis）。"""
        return self.sysUtilService.saveRedis(sysUtil)

    # Java 第 39~70 行：以下两个接口在源码中被**整段注释**（含 @PostMapping 注解），
    # 因原始注释里又嵌套了注释，源码呈现为 `/*  *//** ... *//*`。
    # 忠实保留其内容（仅作为注释，不注册为方法）：
    #
    #   @PostMapping(value = "/syncTrack")
    #   public Map<String, List<TrailBo>> syncTrack(@RequestBody CarParaVO carParaVO) {
    #       Map<ZdataTrailTracks, List<TrailBo>> carMap = sysUtilService.syncTrack(carParaVO);
    #       Map<String, List<TrailBo>> josnMap = new HashMap<>(); // 返回对象
    #       if (null != carMap) {
    #           for (Map.Entry<ZdataTrailTracks, List<TrailBo>> entry : carMap.entrySet()) {
    #               josnMap.put(JSON.toJSONString(entry.getKey()), entry.getValue());
    #           }
    #       }
    #       return josnMap;
    #   }
    #
    #   /**
    #    * 同步可疑车俩
    #    */
    #   @PostMapping(value = "/syncSuspiciousCar")
    #   public Map<String, List<TrailBo>> syncSuspiciousCar(@RequestBody CarParaVO carParaVO) {
    #       Map<ZdataTrailTracks, List<TrailBo>> carMap = sysUtilService.syncSuspiciousCar(carParaVO);
    #       Map<String, List<TrailBo>> josnMap = new HashMap<>(); // 返回对象
    #       if (null != carMap) {
    #           for (Map.Entry<ZdataTrailTracks, List<TrailBo>> entry : carMap.entrySet()) {
    #               josnMap.put(JSON.toJSONString(entry.getKey()), entry.getValue());
    #           }
    #       }
    #       return josnMap;
    #   }

    def carTrackQueryByCarNo(self, carParaVO: CarParaVO) -> TableDataInfo:
        """车辆历史轨迹：根据车牌号查询（GET /base/sysutil/carTrackQueryByCarNo）。"""
        self.startPage()
        list_: List[ZdataTrailTracks] = []
        if CommonUtil.isNotBlank(carParaVO.getCarNo()):
            carParaVO.setFlag("bannian")  # 默认查询半年的数据
            list_ = self.sysUtilService.carTrackQueryNew(carParaVO)
        rtnList: List[TrailInfo] = []
        if list_ is not None and len(list_) > 0:
            for tracks in list_:
                carNo = CommonUtil.isNull(tracks.getPlateKey())
                keyValue = tracks.getTrailPoints()  # 行驶轨迹
                jsonList: List[TrailBo] = []
                if CommonUtil.isNotBlank(keyValue):
                    jsonList = self.sysUtilService.getTrailBoList(keyValue)
                    tracks.setTrailPoints("")  # 行驶轨迹

                    # 获取设备的经纬度
                    trailInfo = self.sysUtilService.changeData(tracks, jsonList)
                    trailInfo.setTrailUuid(carNo)
                    rtnList.append(trailInfo)

        # 手工组装 TableDataInfo（Java 未调用 getDataTable）
        rspData = TableDataInfo()
        rspData.setCode(HttpStatus.SUCCESS)
        rspData.setMsg("查询成功")
        rspData.setRows(rtnList)
        rspData.setTotal(PageInfo(list_).getTotal())
        return rspData

    def carTrackQueryByTime(self, carParaVO: CarParaVO) -> TableDataInfo:
        """车辆历史轨迹：根据车牌号时间段查询（GET /base/sysutil/carTrackQueryByTime）。"""
        self.startPage()
        list_: List[ZdataTrailTracks] = []
        # 重点车辆库
        carlist: List[CarVO] = []
        obj = self.redisCache.getCacheObject(Constants.car_list_jc)
        if obj is not None:
            # Java: carlist = (List) obj; 泛型擦除后仅校验 List，类型不符抛 ClassCastException
            if not isinstance(obj, list):
                raise TypeError(
                    "java.lang.ClassCastException: " + type(obj).__name__
                    + " cannot be cast to java.util.List")
            carlist = obj

        if carlist is not None and len(carlist) > 0:
            carParaVO.setCarlist(carlist)
            list_ = self.sysUtilService.carTrackQueryNew(carParaVO)

        rtnList: List[TrailInfo] = []
        if list_ is not None and len(list_) > 0:
            for tracks in list_:
                carNo = CommonUtil.isNull(tracks.getPlateKey())
                keyValue = tracks.getTrailPoints()  # 行驶轨迹
                jsonList: List[TrailBo] = []
                if CommonUtil.isNotBlank(keyValue):
                    jsonList = self.sysUtilService.getTrailBoList(keyValue)
                    # Java 原文此处被注释掉：tracks.setTrailPoints("");

                    # 获取设备的经纬度
                    trailInfo = self.sysUtilService.changeData(tracks, jsonList)
                    trailInfo.setTrailUuid(carNo)
                    rtnList.append(trailInfo)

        rspData = TableDataInfo()
        rspData.setCode(HttpStatus.SUCCESS)
        rspData.setMsg("查询成功")
        rspData.setRows(rtnList)
        rspData.setTotal(PageInfo(list_).getTotal())
        return rspData

    def changeTrailInfo(self, trailInfo: TrailInfo) -> TrailInfo:
        """对象转换（POST /base/sysutil/changeTrailInfo）。

        【Java→Python】参数来自 ``@RequestBody``；Python 侧由 Web 框架反序列化后传入，
        方法体逐行照搬（含 BigDecimal → float 的落库映射）。
        """
        if trailInfo is not None:
            tracks: ZdataTrailTracks = trailInfo.getTracks()
            trailList: List[TrailBo] = trailInfo.getTrailList()
            if tracks is not None and trailList is not None and len(trailList) > 0:
                if CommonUtil.isNotBlank(tracks.getStartLon()):
                    tracks.setStartLonDec(float(BigDecimal(tracks.getStartLon())))
                if CommonUtil.isNotBlank(tracks.getStratLat()):
                    tracks.setStratLatDec(float(BigDecimal(tracks.getStratLat())))
                if CommonUtil.isNotBlank(tracks.getEndLon()):
                    tracks.setEndLonDec(float(BigDecimal(tracks.getEndLon())))
                if CommonUtil.isNotBlank(tracks.getEndLat()):
                    tracks.setEndLatDec(float(BigDecimal(tracks.getEndLat())))
                for trailBo in trailList:
                    trailBo.setIsQuery("1")  # 需要查询数据-----------
                carNo = CommonUtil.isNull(tracks.getPlateKey())
                # 获取设备的经纬度
                changeBo = self.sysUtilService.changeData(trailInfo.getTracks(),
                                                          trailInfo.getTrailList())
                changeBo.setTrailUuid(carNo)
                return changeBo
        return trailInfo

    def getByTrailBo(self, trailBo: TrailBo) -> TrailBo:
        """获取抓拍对象（GET /base/sysutil/getByTrailBo）。"""
        return self.sysUtilService.getByTrailBo(trailBo)
