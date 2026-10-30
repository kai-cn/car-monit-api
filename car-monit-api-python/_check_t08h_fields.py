# -*- coding: utf-8 -*-
"""t08h 前置校验：SysUtilServiceImpl 依赖的实体字段 / 接口方法是否齐备。"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

FIELDS = {
    "com.ruoyi.base.domain.TrailBo": [
        "pointUuid", "stateType", "captureTime", "locationCode", "locationName", "standardCode",
        "locationId", "platenumber", "lon", "lat", "devCode", "devName", "sectionCode", "pileno",
        "roadCode", "imagesArry", "platecolor", "direction", "isVirtual", "orgCode",
    ],
    "com.ruoyi.base.domain.ZdataTrailTracks": [
        "uuid", "plateKey", "trailPoints", "trailtype", "flag", "enterTime", "exitTime",
        "entollstationid", "entollstationname", "extollstationid", "extollstationname",
        "firtStationCode", "firtStationName", "firtStationTime", "plateColor", "carType",
        "carVehicle", "carNum", "passType", "startLon", "stratLat", "endLon", "endLat",
        "startLonDec", "stratLatDec", "endLonDec", "endLatDec", "escapedType",
        "escapedTypeRemark", "escapedTfcj", "envehicletype", "envehicleid", "exvehicleid",
    ],
    "com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode": [
        "platecolor", "platenumber", "snapshottime", "sectioncode", "gantrycode", "datauuid",
        "startNum", "endNum", "applyTime1", "applyTime2", "sectionList",
    ],
    "com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01": [
        "plateColor", "sectionList", "inApplyTime1", "inApplyTime2", "startNum", "endNum",
        "cidList", "vehicleplate", "sectioncode", "transtime", "fee", "cid", "orderByFlag",
    ],
    "com.ruoyi.base.domain.OdsSzdnGantry": [
        "gantryCode", "gantryName", "lon", "lat", "roadCode", "sectionCode", "pileNo",
        "direction", "isVirtual",
    ],
    "com.ruoyi.base.domain.OdsSzdnSection": ["sectionCode", "sectionName", "roadCode"],
    "com.ruoyi.base.domain.OdsSzdnToll": [
        "tollCode", "tollName", "longitude", "latitude", "roadCode", "sectionCode", "pileNo",
    ],
    "com.ruoyi.base.domain.OdsSzdnTollStationIp": ["tollCode", "tollName", "odsSzdnToll"],
    "com.ruoyi.base.domain.OdsSzdnGantryIp": ["gantryCode", "gantryName", "odsSzdnGantry"],
    "com.ruoyi.base.domain.ZdataLocationDict": [
        "standardCode", "name", "longitude", "latitude", "roadcode", "sectioncode", "pileNo",
        "direction",
    ],
    "com.ruoyi.base.domain.OdsCxztFwqclls": ["targetpicurl", "platepicurl"],
    "com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode": [
        "plateimage", "sideimage", "headimage",
    ],
    "com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode": ["snappicturepath"],
    "com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure": ["weighingImagesArry"],
    "com.ruoyi.base.domain.CarParaVO": [
        "carlist", "carNoList", "starTime", "endTime", "startNum", "endNum", "applyTime1",
        "applyTime2", "pageSize", "lastExitTime",
    ],
    "com.ruoyi.base.domain.TrailTracksVo": ["plateKey", "enterTime", "exitTime"],
    "com.ruoyi.base.domain.SuspiciousCarVO": [
        "signatureKey", "timeStamp", "signature", "trailInfoList",
    ],
    "com.ruoyi.base.domain.TrailInfo": ["tracks", "trailList", "trailUuid"],
    "com.ruoyi.base.domain.CarVO": ["carNo"],
}

SERVICES = {
    "com.ruoyi.base.service.IZdataTrailTracksService": [
        "getLatestTrail", "getUnFitting", "getHistoryTrail", "getLatestTrailByCursor",
    ],
    "com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService": [
        "selectOdsRtSzdnSnapshotFlowAddcodeListNew",
        "selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids",
    ],
    "com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service": [
        "selectOdsLwzxsfsjFeeRecords01ListNew", "selectOdsLwzxsfsjFeeRecords01ByQueryUuids",
    ],
    "com.ruoyi.base.service.IOdsSzdnGantryService": ["getGantryRedis"],
    "com.ruoyi.base.service.IOdsSzdnGantryIpService": ["selectOdsSzdnGantryIpMap"],
    "com.ruoyi.base.service.IOdsSzdnTollStationIpService": ["selectStationIpMap"],
    "com.ruoyi.base.service.IOdsSzdnTollService": ["getRedisMap"],
    "com.ruoyi.base.service.IOdsSzdnSectionService": ["getSectionMap", "getSectionList"],
    "com.ruoyi.base.service.IZdataLocationDictService": ["getRedisList"],
    "com.ruoyi.base.service.IOdsSzdnProvinceBorderVehicleWeightNewstructureService": [
        "selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids",
    ],
    "com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService": [
        "selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids",
    ],
    "com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService": [
        "selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids",
    ],
    "com.ruoyi.base.service.IOdsCxztFwqcllsService": ["selectOdsCxztFwqcllsByQueryUuids"],
    "com.ruoyi.base.service.IOdsLwzxsfsjFeeStationEnter01Service": [
        "selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids",
    ],
    "com.ruoyi.base.service.IOdsLwzxsfsjFeeStationExit01Service": [
        "selectOdsLwzxsfsjFeeStationExit01ByQueryUuids",
    ],
}

missing = []
for module, names in FIELDS.items():
    try:
        mod = __import__(module, fromlist=["*"])
    except ImportError as error:
        missing.append("MODULE %s (%s)" % (module, error))
        continue
    clazz = getattr(mod, module.rsplit(".", 1)[-1])
    instance = clazz()
    for name in names:
        cap = name[0].upper() + name[1:]
        if not (hasattr(instance, "get" + cap) or hasattr(instance, "is" + cap)):
            missing.append("FIELD %s.%s" % (clazz.__name__, name))

for module, names in SERVICES.items():
    try:
        mod = __import__(module, fromlist=["*"])
    except ImportError as error:
        missing.append("MODULE %s (%s)" % (module, error))
        continue
    clazz = getattr(mod, module.rsplit(".", 1)[-1])
    for name in names:
        if not hasattr(clazz, name):
            missing.append("METHOD %s.%s" % (clazz.__name__, name))

print("missing:", len(missing))
for item in missing:
    print(" -", item)
