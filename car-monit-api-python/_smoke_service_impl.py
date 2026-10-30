# -*- coding: utf-8 -*-
"""t07 校验脚本：导入并实例化全部 CRUD ServiceImpl，检查 ABC 抽象方法是否实现完毕。

运行：python _smoke_service_impl.py（工作目录 refactor/）
"""
import os
import sys
import traceback

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

IMPLS = [
    "DwdLcztFwqjcxxServiceImpl",
    "DwdLcztSfsjcxxServiceImpl",
    "DwdLcztSfzjcxxServiceImpl",
    "OdsCxztFwqcllsServiceImpl",
    "OdsLwzxsfsjFeeGantryFusion01ServiceImpl",
    "OdsLwzxsfsjFeeRecords01ServiceImpl",
    "OdsLwzxsfsjFeeStationEnter01ServiceImpl",
    "OdsLwzxsfsjFeeStationExit01ServiceImpl",
    "OdsRtSzdnSnapshotFlowAddcodeServiceImpl",
    "OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl",
    "OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl",
    "OdsSzdnGantryIpServiceImpl",
    "OdsSzdnGantryServiceImpl",
    "OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl",
    "OdsSzdnSectionServiceImpl",
    "OdsSzdnTollServiceImpl",
    "OdsSzdnTollStationIpServiceImpl",
    "OdsYhglVBaseOrgServiceImpl",
    "ZdataLocationDictServiceImpl",
    "ZdataTrailFittingServiceImpl",
    "ZdataTrailTracksServiceImpl",
]

PKG = "com.ruoyi.base.service.impl."
ok, bad = 0, []
for name in IMPLS:
    try:
        module = __import__(PKG + name, fromlist=[name])
        cls = getattr(module, name)
        cls()                     # ABC 抽象方法未实现会在此抛 TypeError
        ok += 1
    except Exception as exc:      # noqa: BLE001
        bad.append((name, exc))
        traceback.print_exc()

print("instantiated:", ok, "/", len(IMPLS))
for name, exc in bad:
    print("FAIL", name, "->", type(exc).__name__, exc)
print("ALL SERVICE IMPL SMOKE OK" if not bad else "SOME FAILED")
