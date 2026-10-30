# -*- coding: utf-8 -*-
"""t08 框架替身自检：fastjson2（JSON/JSONObject/JSONArray）。"""
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.alibaba.fastjson2.JSON import JSON  # noqa: E402
from com.alibaba.fastjson2.JSONArray import JSONArray  # noqa: E402
from com.alibaba.fastjson2.JSONObject import JSONObject  # noqa: E402
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode  # noqa: E402

failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


# 1) 实体 → JSON：snake_case → camelCase，跳过 null，时间格式化
entity = OdsRtSzdnSnapshotFlowAddcode(
    big_id="B1", gantrycode="G01", platenumber="赣A12345",
    snapshottime=datetime(2026, 10, 21, 9, 30, 0), direction=0,
)
text = JSON.toJSONString(entity)
check("camel key", '"bigId":"B1"' in text, True)
check("date text", '"snapshottime":"2026-10-21 09:30:00"' in text, True)
check("skip null", '"roadname"' not in text, True)

# 2) JSON → 实体：camelCase → snake_case + 时间解析
back = JSON.parseObject(text, OdsRtSzdnSnapshotFlowAddcode)
check("roundtrip bigId", back.big_id, "B1")
check("roundtrip date", back.snapshottime, datetime(2026, 10, 21, 9, 30, 0))
check("roundtrip int", back.direction, 0)

# 3) 毫秒时间戳也能解析（fastjson 默认写法的兼容）
ms = int(datetime(2026, 10, 21, 10, 0, 0).timestamp() * 1000)
back2 = JSON.parseObject('{"snapshottime":%d}' % ms, OdsRtSzdnSnapshotFlowAddcode)
check("millis parse", back2.snapshottime, datetime(2026, 10, 21, 10, 0, 0))

# 4) JSONObject 取值与嵌套包装
obj = JSON.parseObject('{"op":"c","after":{"platenumber":"赣B00001","direction":"1"},"nums":[1,2]}')
check("op", obj.getString("op"), "c")
after = obj.getJSONObject("after")
check("nested type", isinstance(after, JSONObject), True)
check("nested getString", after.getString("platenumber"), "赣B00001")
check("getInteger from string", after.getInteger("direction"), 1)
check("missing getString", obj.getString("missing"), None)
check("getJSONArray type", isinstance(obj.getJSONArray("nums"), JSONArray), True)
check("array size", obj.getJSONArray("nums").size(), 2)

# 5) JSONArray → List<实体>
arr = JSON.parseArray('[{"uuid":"1","exitTime":"2026-10-21 08:00:00"},{"uuid":"2"}]',
                      __import__("com.ruoyi.base.domain.ZdataTrailTracks", fromlist=["ZdataTrailTracks"]).ZdataTrailTracks)
check("array to entity", [item.uuid for item in arr], ["1", "2"])
check("array date", arr[0].exit_time, datetime(2026, 10, 21, 8, 0, 0))

# 6) toJavaObject
plain = JSONObject({"bigId": "B9"})
check("toJavaObject", JSON.toJavaObject(plain, OdsRtSzdnSnapshotFlowAddcode).big_id, "B9")

# 7) 集合/嵌套实体序列化
text2 = JSON.toJSONString({"list": [entity], "time": datetime(2026, 1, 2, 3, 4, 5)})
check("nested list", '"bigId":"B1"' in text2, True)
check("dict date", '"time":"2026-01-02 03:04:05"' in text2, True)

print("checks:", total[0] - len(failures), "/", total[0])
for f in failures:
    print("FAIL", f)
print("JSON SMOKE OK" if not failures else "JSON SMOKE FAILED")
