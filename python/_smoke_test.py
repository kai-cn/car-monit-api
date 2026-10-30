import sys

sys.path.insert(0, "python")

import sys_util_service as m


class FakeSvc:
    def __init__(self, **kw):
        self.__dict__.update(kw)


svc = m.SysUtilServiceImpl(
    is_localhost="local",
    ods_szdn_toll_station_ip_service=FakeSvc(selectStationIpMap=lambda: {}),
    ods_szdn_toll_service=FakeSvc(getRedisMap=lambda: {}),
    ods_szdn_gantry_ip_service=FakeSvc(selectOdsSzdnGantryIpMap=lambda: {}),
    zdata_location_dict_service=FakeSvc(getRedisList=lambda: {}),
    section_service=FakeSvc(getSectionMap=lambda: {}),
)

# changeData：无经纬度时也应有默认设备名
trail = m.TrailBo(
    point_uuid="u1",
    state_type=m.SERVICE_AREA_CAPTURE,
    capture_time="2025-10-14 13:46:42",
    location_code="serviceip:172.16.204.101",
)
tracks = m.ZdataTrailTracks(plate_key="赣A12345", flag="x")
info = svc.change_data(tracks, [trail])
print("devName=", info.trail_list[0].dev_name)

# mapTrailBoList：4 分钟内的同门架抓拍合并图片
a = m.TrailBo(state_type=m.GANTRY_CAPTURE, location_code="ip", capture_time="2025-10-14 10:00:00", images_arry="i1")
b = m.TrailBo(state_type=m.GANTRY_CAPTURE, location_code="ip", capture_time="2025-10-14 10:02:00", images_arry="i2")
print("merged=", [x.images_arry for x in svc.map_trail_bo_list([a, b])])

# getTrailBoList：T 时间格式化 + BigDecimal 转换
raw = ('[{"captureTime":"2025-10-14T13:46:42","stateType":"GantryCapture",'
       '"pointUuid":"p1","sectionCode":"S1","lon":"113.1","lat":"27.2"}]')
lst = svc.get_trail_bo_list(raw)
print("parsed=", lst[0].capture_time, lst[0].lon, lst[0].section_code)

# separateUnfiitingList：无门架交易流水 -> 全程屏蔽
tracks2 = m.ZdataTrailTracks(
    plate_key="赣A12345",
    trail_points=m._trail_bo_list_to_json(
        [m.TrailBo(state_type=m.GANTRY_CAPTURE, point_uuid="p1", location_code="ip")]
    ),
)
svc.separate_unfiiting_list([tracks2], {})
print("escaped=", tracks2.escaped_tfcj, tracks2.escaped_type_remark)
print("redisKeys=", sorted(svc.redis_cache._store.keys()))

# getByTrailBo：卡口流水只清空图片
fee_trail = m.TrailBo(state_type=m.FeeRecord, point_uuid="p9")
print("byTrailBo=", svc.get_by_trail_bo(fee_trail).images_arry)

