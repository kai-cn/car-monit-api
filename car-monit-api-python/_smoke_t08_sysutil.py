# -*- coding: utf-8 -*-
"""t08h：SysUtilServiceImpl 冒烟测试（不连库、不连 Redis，全部内存桩）。"""
import io
import logging
import os
import sys
import contextlib
from datetime import datetime

ROOT = os.path.abspath(os.path.dirname(__file__))
for _p in (ROOT, os.path.join(ROOT, "pro-base-common", "src", "main", "java"),
           os.path.join(ROOT, "pro-business-api", "src", "main", "java")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from com.alibaba.fastjson2.JSONObject import JSONObject
from com.ruoyi.base.domain.OdsCxztFwqclls import OdsCxztFwqclls
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode import (
    OdsRtSzdnSnapshotFlowProvcaptureAddcode,
)
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode import (
    OdsRtSzdnSnapshotFlowStationcaptureAddcode,
)
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure import (
    OdsSzdnProvinceBorderVehicleWeightNewstructure,
)
from com.ruoyi.base.domain.OdsSzdnSection import OdsSzdnSection
from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.TrailTracksVo import TrailTracksVo
from com.ruoyi.base.domain.ZdataLocationDict import ZdataLocationDict
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.forest.HttpSysUtilApiService import HttpSysUtilApiService
from com.ruoyi.base.service.IOdsCxztFwqcllsService import IOdsCxztFwqcllsService
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
from com.ruoyi.base.service.IZdataLocationDictService import IZdataLocationDictService
from com.ruoyi.base.service.IZdataTrailTracksService import IZdataTrailTracksService
from com.ruoyi.base.service.impl.SysUtilServiceImpl import SysUtilServiceImpl
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache, _InMemoryRedisTemplate

logging.disable(logging.CRITICAL)

_PASS = []
_FAIL = []


def check(name, actual, expected):
    if actual == expected:
        _PASS.append(name)
    else:
        _FAIL.append("%s: 期望 %r，实际 %r" % (name, expected, actual))


def check_true(name, cond, detail=""):
    if cond:
        _PASS.append(name)
    else:
        _FAIL.append("%s: 断言为假 %s" % (name, detail))


def _noop(*args, **kwargs):
    return None


def _complete_cls(cls):
    """把桩类未实现的抽象方法补成 noop，并清空 __abstractmethods__（只影响桩自身）。"""
    for name in list(getattr(cls, "__abstractmethods__", frozenset())):
        if name not in cls.__dict__:
            setattr(cls, name, _noop)
    cls.__abstractmethods__ = frozenset()
    return cls


def _empty(interface):
    """给没有行为的接口造一个空桩实例（方法返回 None，需要 dict 的地方显式覆盖）。"""
    cls = _complete_cls(type("Empty_" + interface.__name__, (interface,), {}))
    return cls()


# ---------------------------------------------------------------- 桩实现
class _GantryStub(IOdsSzdnGantryService):
    def __init__(self, rows=None):
        self.rows = rows or []

    def getGantryRedis(self):
        return list(self.rows)


class _SectionStub(IOdsSzdnSectionService):
    def __init__(self, rows=None, mapping=None):
        self.rows = rows or []
        self.mapping = mapping or {}

    def getSectionMap(self):
        return dict(self.mapping)

    def getSectionList(self):
        return list(self.rows)


class _LocationStub(IZdataLocationDictService):
    def __init__(self, mapping=None):
        self.mapping = mapping or {}

    def getRedisList(self):
        return dict(self.mapping)


class _TrailStub(IZdataTrailTracksService):
    def __init__(self):
        self.latest = []
        self.unfitting = []
        self.history = []
        self.latest_calls = 0

    def getLatestTrail(self, carParaVO):
        self.latest_calls += 1
        return list(self.latest)

    def getUnFitting(self, carParaVO):
        return list(self.unfitting)

    def getHistoryTrail(self, carParaVO):
        return list(self.history)


class _SnapshotStub(IOdsRtSzdnSnapshotFlowAddcodeService):
    def __init__(self):
        self.list_rows = []
        self.uuid_rows = {}
        self.uuid_calls = 0

    def selectOdsRtSzdnSnapshotFlowAddcodeListNew(self, odsRtSzdnSnapshotFlowAddcode):
        return list(self.list_rows)

    def selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(self, queryUuids, applyTime1, applyTime2):
        self.uuid_calls += 1
        return dict(self.uuid_rows)


class _FeeStub(IOdsLwzxsfsjFeeRecords01Service):
    def __init__(self):
        self.list_rows = []
        self.query_calls = 0
        self.uuid_rows = {}
        self.uuid_calls = 0

    def selectOdsLwzxsfsjFeeRecords01ListNew(self, odsLwzxsfsjFeeRecords01):
        self.query_calls += 1
        return list(self.list_rows)

    def selectOdsLwzxsfsjFeeRecords01ByQueryUuids(self, uuids, applyTime1, applyTime2):
        self.uuid_calls += 1
        return dict(self.uuid_rows)


class _HttpStub(HttpSysUtilApiService):
    def __init__(self):
        self.calls = 0
        self.last = None

    def syncSuspiciousCarTask(self, suspiciousCarVO):
        self.calls += 1
        self.last = suspiciousCarVO
        response = JSONObject()
        response.put("code", 200)
        response.put("msg", "ok")
        return response


class _EnvStub(object):
    def __init__(self, is_localhost="local"):
        self.is_localhost = is_localhost

    def value(self, placeholder, target_type=str):
        if placeholder == "${isLocalhost}":
            return self.is_localhost
        return None


for _cls in (_GantryStub, _SectionStub, _LocationStub, _TrailStub, _SnapshotStub,
             _FeeStub, _HttpStub):
    _complete_cls(_cls)


class _Ctx(object):
    """一次构建：所有桩 + 服务实例，便于用例读取桩的调用记录。"""

    def __init__(self, is_localhost="local", gantries=None, sections=None, section_map=None,
                 location=None):
        self.redis = RedisCache(_InMemoryRedisTemplate())
        self.trail = _TrailStub()
        self.snap = _SnapshotStub()
        self.fee = _FeeStub()
        self.http = _HttpStub()
        self.gantry = _GantryStub(gantries)
        self.section = _SectionStub(sections, section_map)
        self.location = _LocationStub(location)
        self.prov_weight = _empty(IOdsSzdnProvinceBorderVehicleWeightNewstructureService)
        self.prov_capture = _empty(IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService)
        self.station_capture = _empty(IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService)
        self.fwqclls = _empty(IOdsCxztFwqcllsService)
        self.toll_station_ip = _empty(IOdsSzdnTollStationIpService)
        self.gantry_ip = _empty(IOdsSzdnGantryIpService)
        self.toll = _empty(IOdsSzdnTollService)
        self.enter01 = _empty(IOdsLwzxsfsjFeeStationEnter01Service)
        self.exit01 = _empty(IOdsLwzxsfsjFeeStationExit01Service)
        self.toll_station_ip.selectStationIpMap = lambda: {}
        self.gantry_ip.selectOdsSzdnGantryIpMap = lambda: {}
        self.toll.getRedisMap = lambda: {}
        self.prov_weight.selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids = (
            lambda uuids: {})
        self.prov_capture.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids = (
            lambda uuids: {})
        self.station_capture.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids = (
            lambda uuids, a1, a2: {})
        self.fwqclls.selectOdsCxztFwqcllsByQueryUuids = lambda uuids: {}
        self.svc = SysUtilServiceImpl(
            redisCache=self.redis,
            zdataTrailTracksService=self.trail,
            provinceBorderVehicleWeightNewstructureService=self.prov_weight,
            snapshotFlowAddcodeService=self.snap,
            provcaptureAddcodeService=self.prov_capture,
            stationcaptureAddcodeService=self.station_capture,
            odsSzdnTollStationIpService=self.toll_station_ip,
            odsSzdnGantryIpService=self.gantry_ip,
            feeRecords01Service=self.fee,
            feeStationEnter01Service=self.enter01,
            feeStationExit01Service=self.exit01,
            zdataLocationDictService=self.location,
            fwqcllsService=self.fwqclls,
            sectionService=self.section,
            environment=_EnvStub(is_localhost),
            odsSzdnGantryService=self.gantry,
            odsSzdnTollService=self.toll,
            httpSysUtilApiService=self.http)


# ---------------------------------------------------------------- 数据构造
def trail_bo(state_type, location_code="ip-1", capture_time="2026-06-01 12:00:00",
             point_uuid="u-1", images=None, section_code=None, is_virtual=None,
             platenumber="赣A12345", lon="115.1", lat="28.2"):
    tb = TrailBo()
    tb.setStateType(state_type)
    tb.setLocationCode(location_code)
    tb.setCaptureTime(capture_time)
    tb.setPointUuid(point_uuid)
    tb.setPlatenumber(platenumber)
    tb.setSectionCode(section_code)
    tb.setIsVirtual(is_virtual)
    tb.setLon(lon)
    tb.setLat(lat)
    if images is not None:
        tb.setImagesArry(images)
    return tb


def tracks_row(plate_key="赣A12345", trail_points=None, trailtype="1", flag=None,
               enter_time=None, exit_time=None):
    row = ZdataTrailTracks()
    row.setPlateKey(plate_key)
    row.setTrailPoints(trail_points)
    row.setTrailtype(trailtype)
    row.setFlag(flag)
    row.setEnterTime(enter_time or datetime(2026, 6, 1, 8, 0, 0))
    row.setExitTime(exit_time or datetime(2026, 6, 1, 9, 0, 0))
    row.setEntollstationname("入口门架")
    row.setExtollstationname("出口门架")
    return row


def snapshot_row(gantry_code="G1", section_code="SEC1", plate="赣A12345",
                 snap_time=datetime(2026, 6, 1, 12, 0, 0), platenumber="赣A12345"):
    row = OdsRtSzdnSnapshotFlowAddcode()
    row.setGantrycode(gantry_code)
    row.setSectioncode(section_code)
    row.setPlatecolor(plate)
    row.setPlatenumber(platenumber)
    row.setSnapshottime(snap_time)
    row.setDatauuid("data-" + gantry_code)
    row.setCartypecode("1")
    return row


def gantry_row(code="G1", name="门架一", is_virtual="0"):
    g = OdsSzdnGantry()
    g.setGantryCode(code)
    g.setGantryName(name)
    g.setLon("115.5")
    g.setLat("28.5")
    g.setPileNo("K100")
    g.setIsVirtual(is_virtual)
    return g


def fee_row(cid="fee-1", fee=1.0, transtime=datetime(2026, 6, 1, 12, 0, 0),
            plate="赣A12345_1", section="SEC1"):
    row = OdsLwzxsfsjFeeRecords01()
    row.setCid(cid)
    row.setFee(fee)
    row.setTranstime(transtime)
    row.setVehicleplate(plate)
    row.setSectioncode(section)
    return row


# ================================================================ 用例
def case_get_by_trail_bo_branches():
    ctx = _Ctx()
    svc = ctx.svc

    # 门架抓拍
    snap = OdsRtSzdnSnapshotFlowAddcode()
    snap.setSnappicturepath("http://jxjt.isilon.com/a.jpg")
    snap.setPlatecolor("黄色")
    ctx.snap.uuid_rows = {"u-1": snap}
    tb = trail_bo("GantryCapture")
    out = svc.getByTrailBo(tb)
    check("getByTrailBo gantry images", out.getImagesArry(), "http://36.200.30.144:9080/a.jpg")
    check("getByTrailBo gantry platecolor", out.getPlatecolor(), "黄色")

    # 省界称重：JSON 图片数组拼接
    weight = OdsSzdnProvinceBorderVehicleWeightNewstructure()
    weight.setWeighingImagesArry(
        '[{"snapPicturePath":"p1.jpg"},{"snapPicturePath":"p2.jpg"},{"x":"y"}]')
    ctx.prov_weight.selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids = (
        lambda uuids: {"u-2": weight})
    out = svc.getByTrailBo(trail_bo("BorderWeighingCapture", point_uuid="u-2"))
    check("getByTrailBo border weighing images", out.getImagesArry(), "p1.jpg,p2.jpg")

    # 省界抓拍：三张图
    prov = OdsRtSzdnSnapshotFlowProvcaptureAddcode()
    prov.setPlateimage("a.jpg")
    prov.setSideimage("b.jpg")
    prov.setHeadimage("c.jpg")
    ctx.prov_capture.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids = (
        lambda uuids: {"u-3": prov})
    out = svc.getByTrailBo(trail_bo("ProvCapture", point_uuid="u-3"))
    check("getByTrailBo prov images", out.getImagesArry(), "a.jpg,b.jpg,c.jpg")

    # 服务区抓拍
    fwq = OdsCxztFwqclls()
    fwq.setTargetpicurl("t.jpg")
    fwq.setPlatepicurl("p.jpg")
    ctx.fwqclls.selectOdsCxztFwqcllsByQueryUuids = lambda uuids: {"u-4": fwq}
    out = svc.getByTrailBo(trail_bo("ServiceAreaCapture", point_uuid="u-4"))
    check("getByTrailBo service area images", out.getImagesArry(), "t.jpg,p.jpg")

    # 收费站抓拍
    station = OdsRtSzdnSnapshotFlowStationcaptureAddcode()
    station.setSnappicturepath("s.jpg")
    ctx.station_capture.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids = (
        lambda uuids, a1, a2: {"u-5": station})
    out = svc.getByTrailBo(trail_bo("StationCapture", point_uuid="u-5"))
    check("getByTrailBo station images", out.getImagesArry(), "s.jpg")

    # FeeRecord：uuid 未收集 → 永远查不到（忠实保留缺陷）
    ctx.fee.uuid_rows = {"u-6": fee_row()}
    out = svc.getByTrailBo(trail_bo("FeeRecord", point_uuid="u-6"))
    check("getByTrailBo fee record unreachable", out.getImagesArry(), "")
    check("getByTrailBo fee record not queried", ctx.fee.uuid_calls, 0)

    # null 入参
    out = svc.getByTrailBo(None)
    check_true("getByTrailBo null returns empty", out is not None and out.getImagesArry() is None)


def case_virtual_and_plate_color():
    ctx = _Ctx()
    svc = ctx.svc
    normal = trail_bo("GantryCapture")
    virtual = trail_bo("GantryCapture", is_virtual="1")
    check("getIsVirtualFlag normal", svc.getIsVirtualFlag([normal]), True)
    check("getIsVirtualFlag virtual", svc.getIsVirtualFlag([virtual]), False)
    check("getIsVirtualFlag empty", svc.getIsVirtualFlag([]), True)
    check("getIsVirtualFlag None", svc.getIsVirtualFlag(None), True)
    check("getPlateColor empty", svc.getPlateColor([]), "")

    snap = OdsRtSzdnSnapshotFlowAddcode()
    snap.setSnappicturepath("x.jpg")
    snap.setPlatecolor("蓝色")
    ctx.snap.uuid_rows = {"u-1": snap}
    check("getPlateColor first gantry", svc.getPlateColor([normal]), "蓝色")


def case_sync_fee_records():
    ctx = _Ctx()
    svc = ctx.svc
    ctx.fee.list_rows = [fee_row(plate="赣A12345_1", section="SEC1")]
    svc.syncFeeRecords(OdsLwzxsfsjFeeRecords01())
    keys = sorted(ctx.redis.keys(Constants.feeRecordsList + "*"))
    check("syncFeeRecords key", keys, [Constants.feeRecordsList + datetime.now().strftime("%Y%m%d")
                                       + ":SEC1@@赣A12345"])
    check("syncFeeRecords count", len(ctx.redis.getCacheObject(keys[0])), 1)

    # 只有 "_"：Java split 得到长度 0 的数组 → [0] 越界
    ctx.fee.list_rows = [fee_row(plate="_")]
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            svc.syncFeeRecords(OdsLwzxsfsjFeeRecords01())
        check("syncFeeRecords lone underscore raises", False, True)
    except IndexError:
        check("syncFeeRecords lone underscore raises", True, True)

    # 没有 "_"：跳过
    before = len(ctx.redis.keys(Constants.feeRecordsList + "*"))
    ctx.fee.list_rows = [fee_row(plate="赣A99999")]
    svc.syncFeeRecords(OdsLwzxsfsjFeeRecords01())
    check("syncFeeRecords no underscore skipped",
          len(ctx.redis.keys(Constants.feeRecordsList + "*")), before)


def case_sync_snapshot_flow():
    ctx = _Ctx()
    svc = ctx.svc
    row = snapshot_row()
    ctx.snap.list_rows = [row]
    svc.syncSnapshotFlow(OdsRtSzdnSnapshotFlowAddcode())
    keys = sorted(ctx.redis.keys(Constants.snapshotFlowList + "*"))
    check("syncSnapshotFlow key count", len(keys), 1)
    check_true("syncSnapshotFlow key has plate", keys[0].endswith(":SEC1@@赣A12345"), keys[0])
    svc.syncSnapshotFlow(OdsRtSzdnSnapshotFlowAddcode())
    check("syncSnapshotFlow appended", len(ctx.redis.getCacheObject(keys[0])), 2)

    # 车牌空 / 抓拍时间空 → 不写
    ctx.snap.list_rows = [snapshot_row(platenumber="")]
    svc.syncSnapshotFlow(OdsRtSzdnSnapshotFlowAddcode())
    check("syncSnapshotFlow blank plate skipped",
          len(ctx.redis.getCacheObject(keys[0])), 2)


def case_separate_snapshot_flow_time_list():
    ctx = _Ctx(gantries=[gantry_row("G1"), gantry_row("G2")],
               section_map={"SEC1": __section_sec1()})
    svc = ctx.svc
    redis_date = datetime.now().strftime("%Y%m%d")
    rows = [snapshot_row("G1", snap_time=datetime(2026, 6, 1, 12, 0, 0)),
            snapshot_row("G2", snap_time=datetime(2026, 6, 1, 12, 10, 0)),
            snapshot_row("G1", snap_time=datetime(2026, 6, 1, 12, 20, 0))]
    key = Constants.snapshotFlowList + redis_date + ":SEC1@@赣A12345"
    ctx.redis.setCacheObject(key, rows)
    svc.separateSnapshotFlowTimeList()

    suspicious_key = Constants.car_uspicious + redis_date + ":赣A12345"
    trail_info = ctx.redis.getCacheObject(suspicious_key)
    check_true("separateSnapshotFlow creates suspicious", trail_info is not None)
    check("separateSnapshotFlow escapedTfcj", trail_info.getTracks().getEscapedTfcj(), "3")
    check("separateSnapshotFlow escapedType", trail_info.getTracks().getEscapedType(),
          Constants.escapedType_20)
    check("separateSnapshotFlow remark contains section", "SEC1" in
          trail_info.getTracks().getEscapedTypeRemark(), True)
    check("separateSnapshotFlow deletes snapshot keys",
          len(ctx.redis.keys(Constants.snapshotFlowList + "*")), 0)


def case_is_fee_records_exist_with_fee():
    ctx = _Ctx(gantries=[gantry_row("G1")])
    svc = ctx.svc
    redis_date = datetime.now().strftime("%Y%m%d")
    key = Constants.snapshotFlowList + redis_date + ":SEC1@@赣A12345"
    rows = [snapshot_row("G1", snap_time=datetime(2026, 6, 1, 12, 0, 0)),
            snapshot_row("G1", snap_time=datetime(2026, 6, 1, 12, 5, 0)),
            snapshot_row("G1", snap_time=datetime(2026, 6, 1, 12, 10, 0))]
    # 有成功交易流水 → 不生成可疑车
    fee_key = Constants.feeRecordsList + redis_date + ":SEC1@@赣A12345"
    ctx.redis.setCacheObject(fee_key, [fee_row(fee=2.0)])
    svc.isFeeRecordsExist(key, rows, 3, redis_date)
    check("isFeeRecordsExist with fee -> no suspicious",
          ctx.redis.getCacheObject(Constants.car_uspicious + redis_date + ":赣A12345"), None)

    # 有轨迹拟合 → 不生成
    ctx.redis.deleteObject(fee_key)
    fitting_key = Constants.trailFittingList + redis_date + ":赣A12345"
    vo = TrailTracksVo()
    vo.setPlateKey("赣A12345")
    vo.setEnterTime(datetime(2026, 6, 1, 11, 0, 0))
    vo.setExitTime(datetime(2026, 6, 1, 13, 0, 0))
    ctx.redis.setCacheObject(fitting_key, [vo])
    svc.isFeeRecordsExist(key, rows, 3, redis_date)
    check("isFeeRecordsExist with fitting -> no suspicious",
          ctx.redis.getCacheObject(Constants.car_uspicious + redis_date + ":赣A12345"), None)

    # 数量不足 → 直接返回
    ctx.redis.deleteObject(fitting_key)
    svc.isFeeRecordsExist(key, rows[:2], 3, redis_date)
    check("isFeeRecordsExist too few -> no suspicious",
          ctx.redis.getCacheObject(Constants.car_uspicious + redis_date + ":赣A12345"), None)


def case_separate_unfitting_list():
    ctx = _Ctx(gantries=[gantry_row("G1")])
    svc = ctx.svc

    def run(items, fees):
        ctx.redis.deleteObject(ctx.redis.keys(Constants.car_uspicious + "*"))
        row = tracks_row(flag="0")
        row.setTrailPoints(__points_json(items))
        svc.separateUnfiitingList([row], fees)
        key = Constants.car_uspicious + datetime.now().strftime("%Y%m%d") + ":赣A12345"
        info = ctx.redis.getCacheObject(key)
        if info is None:
            return None, row.getFlag()
        return info.getTracks().getEscapedTfcj(), row.getFlag()

    gate = [trail_bo("GantryCapture", point_uuid="g%d" % i) for i in range(6)]

    # 场景 1：完全没有交易流水（conutFeeRecord == 0）
    tfcj, flag = run(gate, {})
    check("separateUnfiiting scenario 1", tfcj, "1")
    check("separateUnfiiting sets currentTrack", flag, "currentTrack")

    # 场景 3：有交易流水但全部未成功（conutFeeRecord > 0 且 sussFeeRecord == 0）
    fee_fail = fee_row(cid="f1", fee=0.0)
    items3 = gate + [trail_bo("FeeRecord", point_uuid="f1")]
    tfcj, _ = run(items3, {"f1": fee_fail})
    check("separateUnfiiting scenario 3", tfcj, "3")

    # 【忠实保留的缺陷】场景 2（部分屏蔽）**不可达**：
    #   costBite = conutFeeRecord / sussFeeRecord，而 sussFeeRecord <= conutFeeRecord，
    #   故 costBite >= 1，永远 > bite(0.5) → `bite.compareTo(costBite) >= 0` 恒为 false。
    fee_ok = fee_row(cid="f2", fee=1.0)
    items2 = gate + [trail_bo("FeeRecord", point_uuid="f2")]
    tfcj, _ = run(items2, {"f2": fee_ok})
    check("separateUnfiiting scenario 2 unreachable", tfcj, None)

    # 多成功流水同样不会生成（2/2 = 1.0 > 0.5）
    fees = {"k%d" % i: fee_row(cid="k%d" % i, fee=1.0) for i in range(2)}
    items4 = gate + [trail_bo("FeeRecord", point_uuid="k%d" % i) for i in range(2)]
    tfcj, _ = run(items4, fees)
    check("separateUnfiiting ratio 1.0 -> none", tfcj, None)


def case_sync_suspicious_car_db():
    ctx = _Ctx()
    svc = ctx.svc
    redis_date = datetime.now().strftime("%Y%m%d")
    key = Constants.car_uspicious + redis_date + ":赣A12345"
    tracks = tracks_row()
    info_cls = __import__("com.ruoyi.base.domain.TrailInfo", fromlist=["TrailInfo"]).TrailInfo()
    info_cls.setTracks(tracks)
    info_cls.setTrailUuid("赣A12345")
    ctx.redis.setCacheObject(key, info_cls)

    svc.syncSuspiciousCarDB()
    check("syncSuspiciousCarDB http called", ctx.http.calls, 1)
    check("syncSuspiciousCarDB trail list size", len(ctx.http.last.getTrailInfoList()), 1)
    check("syncSuspiciousCarDB signature len", len(ctx.http.last.getSignature()), 40)
    check_true("syncSuspiciousCarDB timestamp int", isinstance(ctx.http.last.getTimeStamp(), int))
    check("syncSuspiciousCarDB deletes keys", len(ctx.redis.keys(Constants.car_uspicious + "*")), 0)


def case_car_track_query():
    ctx = _Ctx()
    svc = ctx.svc
    row = tracks_row()
    row.setTrailPoints('[{"captureTime":"2026-06-01T12:00:00","stateType":"GantryCapture",'
                       '"locationCode":"ip-1","pointUuid":"u-1"}]')
    ctx.trail.history = [row]
    result = svc.carTrackQuery(__car_para())
    check("carTrackQuery size", len(result), 1)
    check("carTrackQuery trailUuid", result[0].getTrailUuid(), "赣A12345")
    result2 = svc.carTrackQueryNew(__car_para())
    check("carTrackQueryNew size", len(result2), 1)


def __car_para():
    from com.ruoyi.base.domain.CarParaVO import CarParaVO
    from com.ruoyi.base.domain.CarVO import CarVO

    vo = CarParaVO()
    car = CarVO()
    car.setCarNo("赣A12345")
    vo.setCarlist([car])
    return vo


def case_sync_suspicious_car_qutaz():
    ctx = _Ctx(gantries=[gantry_row("G1")],
               sections=[__section()], section_map={INDEX_SECTION: __section()})
    svc = ctx.svc
    points = [trail_bo("GantryCapture", point_uuid="p%d" % i, section_code=INDEX_SECTION)
              for i in range(6)]
    row = tracks_row(trailtype="0", trail_points=__points_json(points))
    ctx.trail.latest = [row]
    svc.syncSuspiciousCarQutaz(1, 1)
    key = Constants.car_uspicious + datetime.now().strftime("%Y%m%d") + ":赣A12345"
    info = ctx.redis.getCacheObject(key)
    check_true("syncSuspiciousCarQutaz cross-province suspicious", info is not None)
    if info is not None:
        check("syncSuspiciousCarQutaz cross-province tfcj",
              info.getTracks().getEscapedTfcj(), "1")

    # 关注路段屏蔽
    ctx.redis.deleteObject(ctx.redis.keys(Constants.car_uspicious + "*"))
    row2 = tracks_row(trailtype="1", trail_points=__points_json(points))
    ctx.trail.latest = [row2]
    svc.syncSuspiciousCarQutaz(1, 1)
    info = ctx.redis.getCacheObject(key)
    check_true("syncSuspiciousCarQutaz section suspicious", info is not None)
    if info is not None:
        check("syncSuspiciousCarQutaz section tfcj", info.getTracks().getEscapedTfcj(), "2")

    # 节假日 → 不生成
    ctx.redis.deleteObject(ctx.redis.keys(Constants.car_uspicious + "*"))
    ctx.redis.setCacheObject(SysUtilServiceImpl.jholiday_time, "2000-01-01," + __query_date())
    svc.syncSuspiciousCarQutaz(1, 1)
    check("syncSuspiciousCarQutaz holiday skipped",
          ctx.redis.getCacheObject(key), None)


INDEX_SECTION = "200R500450649000"


def __section():
    """必须用 indexSectionCode（泰赣路段编码），否则关注路段分支不会命中。"""
    s = OdsSzdnSection()
    s.setRoadCode("G45")
    s.setSectionCode(INDEX_SECTION)
    s.setSectionName("泰赣路段")
    return s


def __section_sec1():
    s = OdsSzdnSection()
    s.setRoadCode("G45")
    s.setSectionCode("SEC1")
    s.setSectionName("SEC1路段")
    return s


def __points_json(points):
    return __json_dumps([{"stateType": p.getStateType(), "locationCode": p.getLocationCode(),
                          "pointUuid": p.getPointUuid(), "sectionCode": p.getSectionCode(),
                          "platenumber": p.getPlatenumber()} for p in points])


def __query_date():
    from datetime import timedelta
    return (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")


def __json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False)


def case_sync_suspicious_car_qutaz_new():
    ctx = _Ctx(gantries=[gantry_row("G1")],
               sections=[__section()], section_map={INDEX_SECTION: __section()},
               location={__location_key(): __location()})
    svc = ctx.svc
    points = [trail_bo("GantryCapture", point_uuid="n%d" % i, section_code=INDEX_SECTION,
                       location_code=__location_key()) for i in range(6)]
    fitting = tracks_row(trail_points=__points_json(points))
    unfitting = tracks_row(trail_points=__points_json(points), flag=None)
    ctx.trail.latest = [fitting]
    ctx.trail.unfitting = [unfitting]
    svc.syncSuspiciousCarQutazNew(1, 1)
    check("syncSuspiciousCarQutazNew latest called", ctx.trail.latest_calls, 1)
    check("syncSuspiciousCarQutazNew fitting flag", fitting.getFlag(), "1")
    check("syncSuspiciousCarQutazNew unfitting flag", unfitting.getFlag(), "currentTrack")
    check_true("syncSuspiciousCarQutazNew unfitting uuid", unfitting.getUuid() is not None)
    key = Constants.car_uspicious + datetime.now().strftime("%Y%m%d") + ":赣A12345"
    check_true("syncSuspiciousCarQutazNew suspicious", ctx.redis.getCacheObject(key) is not None)


def __location_key():
    return "raw-1"


def __location():
    loc = ZdataLocationDict()
    loc.setRawCode(__location_key())
    loc.setStandardCode("G1")
    return loc


def case_sync_suspicious_car_empty():
    ctx = _Ctx()
    check("syncSuspiciousCar returns empty dict", ctx.svc.syncSuspiciousCar(__car_para()), {})


def main():
    cases = [
        case_get_by_trail_bo_branches,
        case_virtual_and_plate_color,
        case_sync_fee_records,
        case_sync_snapshot_flow,
        case_separate_snapshot_flow_time_list,
        case_is_fee_records_exist_with_fee,
        case_separate_unfitting_list,
        case_sync_suspicious_car_db,
        case_car_track_query,
        case_sync_suspicious_car_qutaz,
        case_sync_suspicious_car_qutaz_new,
        case_sync_suspicious_car_empty,
    ]
    for case in cases:
        try:
            case()
        except Exception:
            import traceback
            _FAIL.append("用例异常 %s\n%s" % (case.__name__, traceback.format_exc()))

    print("=" * 70)
    print("PASS: %d  FAIL: %d" % (len(_PASS), len(_FAIL)))
    for item in _FAIL:
        print("  [FAIL] " + item)
    print("=" * 70)
    return 0 if not _FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
