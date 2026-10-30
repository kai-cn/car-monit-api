# -*- coding: utf-8 -*-
"""t07 功能级校验：缓存回填、多前缀 Map、关联对象填充、游标与格式化。

运行：python _smoke_service_impl_func.py（工作目录 refactor/）
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from datetime import datetime  # noqa: E402

from com.ruoyi.common.core.redis.RedisCache import RedisCache, _InMemoryRedisTemplate  # noqa: E402

from com.ruoyi.base.domain.DwdLcztFwqjcxx import DwdLcztFwqjcxx  # noqa: E402
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01  # noqa: E402
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnGantryIp import OdsSzdnGantryIp  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnSection import OdsSzdnSection  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnToll import OdsSzdnToll  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnTollStationIp import OdsSzdnTollStationIp  # noqa: E402

from com.ruoyi.base.service.impl.DwdLcztFwqjcxxServiceImpl import DwdLcztFwqjcxxServiceImpl  # noqa: E402
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeRecords01ServiceImpl import OdsLwzxsfsjFeeRecords01ServiceImpl  # noqa: E402
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowAddcodeServiceImpl import OdsRtSzdnSnapshotFlowAddcodeServiceImpl  # noqa: E402
from com.ruoyi.base.service.impl.OdsSzdnGantryIpServiceImpl import OdsSzdnGantryIpServiceImpl  # noqa: E402
from com.ruoyi.base.service.impl.OdsSzdnGantryServiceImpl import OdsSzdnGantryServiceImpl  # noqa: E402
from com.ruoyi.base.service.impl.OdsSzdnSectionServiceImpl import OdsSzdnSectionServiceImpl  # noqa: E402
from com.ruoyi.base.service.impl.OdsSzdnTollServiceImpl import OdsSzdnTollServiceImpl  # noqa: E402
from com.ruoyi.base.service.impl.OdsSzdnTollStationIpServiceImpl import OdsSzdnTollStationIpServiceImpl  # noqa: E402


def fresh_cache():
    """每个用例独立的 Redis，避免用例间互相污染。"""
    return RedisCache(_InMemoryRedisTemplate())


failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


# 1) DwdLcztFwqjcxx：整表缓存 + 名称字典
fwq = DwdLcztFwqjcxx(agent_pk="P1", fwqmc="南昌服务区")
svc = DwdLcztFwqjcxxServiceImpl(redisCache=fresh_cache())
svc.dwdLcztFwqjcxxMapper.insert(fwq)
m = svc.getServiceNameMap()
check("fwq map keys", list(m.keys()), ["南昌服务区"])
check("fwq cache hit", svc.getServiceNameMap()["南昌服务区"].agent_pk, "P1")

# 2) OdsSzdnToll + OdsSzdnTollStationIp：关联回填 + 8 个 key
toll_svc = OdsSzdnTollServiceImpl(redisCache=fresh_cache())
toll_svc.odsSzdnTollMapper.insert(OdsSzdnToll(id="T1", toll_code="A01", state_code_merge="G01"))
ip_svc = OdsSzdnTollStationIpServiceImpl(odsSzdnTollService=toll_svc, redisCache=toll_svc.redisCache)
ip_svc.odsSzdnTollStationIpMapper.insert(
    OdsSzdnTollStationIp(id=1, ip="1.1.1.1", toll_code="A01", toll_name="南昌北收费站"))
ip_map = ip_svc.selectStationIpMap()
check("stationip key", ip_map["stationip:1.1.1.1"].toll_code, "A01")
check("station key", ip_map["station:A01"].ip, "1.1.1.1")
check("bare code key", ip_map["A01"].ip, "1.1.1.1")
check("clean toll name key", ip_map["南昌北"].toll_code, "A01")
backfilled = ip_svc.getRedisList()[0]
check("toll relation filled", backfilled.ods_szdn_toll.toll_code, "A01")
check("toll map dual keys", sorted(toll_svc.getRedisMap().keys()), ["A01", "G01"])

# 3) OdsSzdnGantry + OdsSzdnGantryIp：Long id 的 "" + id 语义
gantry_svc = OdsSzdnGantryServiceImpl(redisCache=fresh_cache())
gantry_svc.odsSzdnGantryMapper.insert(OdsSzdnGantry(id="S1", gantry_code="G1"))
gip_svc = OdsSzdnGantryIpServiceImpl(odsSzdnGantryService=gantry_svc, redisCache=gantry_svc.redisCache)
gip_svc.odsSzdnGantryIpMapper.insert(OdsSzdnGantryIp(id=7, gantry_code="G1", ip="2.2.2.2"))
gip_map = gip_svc.selectOdsSzdnGantryIpMap()
check("gantryip by id", gip_map["gantryip:7"].ip, "2.2.2.2")
check("gantryid by code", gip_map["gantryid:G1"].ip, "2.2.2.2")
check("bwlocation bare", gip_map["7"].gantry_code, "G1")
check("gantry relation filled", gip_svc.getRedisList()[0].ods_szdn_gantry.gantry_code, "G1")
check("ip set", gip_svc.selectIPSet(), {"2.2.2.2"})

# id 为 None 时：Java 的 "" + null == "null"（模拟库中主键为 NULL 的脏数据）
gip2 = OdsSzdnGantryIpServiceImpl(odsSzdnGantryService=gantry_svc, redisCache=fresh_cache())
gip2.odsSzdnGantryIpMapper.insert(OdsSzdnGantryIp(gantry_code="G9", ip="3.3.3.3"))
gip2.odsSzdnGantryIpMapper._rows[0].id = None
check("java null concat key", "gantryip:null" in gip2.selectOdsSzdnGantryIpMap(), True)

# 4) OdsSzdnSection：getSectionMap / getSectionList 共用缓存
sec_svc = OdsSzdnSectionServiceImpl(redisCache=fresh_cache())
sec_svc.odsSzdnSectionMapper.insert(OdsSzdnSection(id="R1", section_code="S6001"))
check("section map", sec_svc.getSectionMap()["S6001"].id, "R1")
check("section list len", len(sec_svc.getSectionList()), 1)

# 5) OdsLwzxsfsjFeeRecords01：COUNT(DISTINCT gantryid)
fee_svc = OdsLwzxsfsjFeeRecords01ServiceImpl(redisCache=fresh_cache())
fee_svc.odsLwzxsfsjFeeRecords01Mapper.insert(OdsLwzxsfsjFeeRecords01(cid="C1", gantryid="G1"))
fee_svc.odsLwzxsfsjFeeRecords01Mapper.insert(OdsLwzxsfsjFeeRecords01(cid="C2", gantryid="G1"))
fee_svc.odsLwzxsfsjFeeRecords01Mapper.insert(OdsLwzxsfsjFeeRecords01(cid="C3", gantryid="G2"))
check("distinct gantry num", fee_svc.selectGantryNum(OdsLwzxsfsjFeeRecords01()), 2)

# 6) OdsRtSzdnSnapshotFlowAddcode：getMaxSnapshotTime 格式化 + 游标分页
snap_svc = OdsRtSzdnSnapshotFlowAddcodeServiceImpl(redisCache=fresh_cache())
snap_svc.odsRtSzdnSnapshotFlowAddcodeMapper.insert(
    OdsRtSzdnSnapshotFlowAddcode(datauuid="u1", snapshottime=datetime(2026, 10, 21, 9, 0, 0)))
snap_svc.odsRtSzdnSnapshotFlowAddcodeMapper.insert(
    OdsRtSzdnSnapshotFlowAddcode(datauuid="u2", snapshottime=datetime(2026, 10, 21, 10, 0, 0)))
check("max snapshot formatted", snap_svc.getMaxSnapshotTime(), "2026-10-21 10:00:00")
page1 = snap_svc.queryByCursor(None, "2026-10-21 10:00:00", 1)
check("cursor page1", [r.datauuid for r in page1], ["u1"])
page2 = snap_svc.queryByCursor("2026-10-21 09:00:00", "2026-10-21 10:00:00", 5)
check("cursor page2", [r.datauuid for r in page2], ["u2"])

print("checks:", total[0] - len(failures), "/", total[0])
for f in failures:
    print("FAIL", f)
print("FUNC SMOKE OK" if not failures else "FUNC SMOKE FAILED")
