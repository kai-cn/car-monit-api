# -*- coding: utf-8 -*-
"""第二轮补测：修正第一轮踩到的契约坑，并把「需实测才能定论」的项一次打完。

第一轮 sysutil 用例失败的原因是用例写错而非服务端错：
CarParaVO 里 endTime 是 Integer、真正的时间区间是 applyTime1/applyTime2，
getByTrailBo 的派发字段是 stateType 而不是 type。本轮按真实契约重发。
样本值全部取自 Java 的真实响应（粤DZW906 / pointUuid=cef80c7c…），不靠猜。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parity import run  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))

C = []


def c(cid, note, path, params=None, method="GET", body=None, cap=30, pk=None, write=False):
    C.append({"id": cid, "group": "probe2", "note": note, "method": method, "path": path,
              "params": params, "body": body, "cap": cap, "pk": pk, "write": write})


PLATE = "粤DZW906"
T1 = "2025-09-30 00:00:00"
T2 = "2025-10-02 23:59:59"

# ── sysutil：真实契约 ──
c("s2-bytime", "carTrackQueryByTime 真实契约（Java 读 car_list_jc，只在 db0）",
  "/base/sysutil/carTrackQueryByTime", {"pageNum": "1", "pageSize": "3"}, cap=3)
c("s2-bycarno-bannian", "carTrackQueryByCarNo：Controller 强制 flag=bannian（extime>=now()-180）",
  "/base/sysutil/carTrackQueryByCarNo", {"carNo": PLATE, "pageNum": "1", "pageSize": "3"}, cap=3)
c("s2-bycarno-range", "carTrackQueryByCarNo 用 applyTime1/2 指定区间",
  "/base/sysutil/carTrackQueryByCarNo",
  {"carNo": PLATE, "applyTime1": T1, "applyTime2": T2, "pageNum": "1", "pageSize": "3"}, cap=3)
c("s2-bytime-farpage", "carTrackQueryByTime 翻页越界（Java reasonable 回夹末页）",
  "/base/sysutil/carTrackQueryByTime", {"pageNum": "999", "pageSize": "2"}, cap=3)
c("s2-endtype-int", "endTime 传时间串（Java Integer 转换 400 vs Go 静默忽略 200）",
  "/base/sysutil/carTrackQueryByCarNo",
  {"carNo": PLATE, "endTime": T2, "pageNum": "1", "pageSize": "3"}, cap=3)

for st, pu in (("FeeRecord", "cef80c7cb8144961aefd13afedc5278b"),
               ("GantryCapture", "189727e7-9392-4ae3-82ce-166864e93ddd"),
               ("StationCapture", "fdbcfa5a-3966-47cf-b3aa-824372ab7eec"),
               ("BorderWeighingCapture", "7379e7aa-e325-449b-9728-b8f6940c77f1"),
               ("FeeStationEnter", "2308"),
               ("FeeStationExit", "11150377"),
               ("TrailFitting", "e0e22490-fb40-4795-947b-68565d864aa7"),
               ("__unknown__", "x")):
    c(f"s2-gbt-{st}", f"getByTrailBo 派发 stateType={st}（真实 pointUuid 回源）",
      "/base/sysutil/getByTrailBo",
      {"stateType": st, "pointUuid": pu, "captureTime": "2025-10-01 00:02:36",
       "plateNumber": PLATE, "devCode": "G601136060000420010"}, cap=0)

# ── changeTrailInfo：BigDecimal 标度 ──
c("s2-change-scale", "startLon=113.100 是否保留尾零（Java BigDecimal vs Go FormatFloat）",
  "/base/sysutil/changeTrailInfo", method="POST", cap=0,
  body={"tracks": {"plateKey": "AB", "flag": "currentTrack", "startLon": "113.100",
                   "stratLat": "28.10", "endLon": "114.000", "endLat": "27.050"},
        "trailList": [{"stateType": "GantryCapture", "pointUuid": "189727e7",
                       "lon": 113.100, "lat": 28.10}]})

# ── 查询族：路由分支与参数契约 ──
c("s2-large-dateonly", "只给日期（Java Timestamp.valueOf 解析失败→走 ES；Go 宽容解析→走库）",
  "/api/v1/large/snapshot", {"startTime": "2025-10-01", "endTime": "2025-10-05",
                             "pageNum": "1", "pageSize": "2"}, cap=2)
c("s2-large-fullfmt", "完整时间串（两端都应走同一条分支）",
  "/api/v1/large/snapshot", {"startTime": "2025-10-01 00:00:00",
                             "endTime": "2025-10-05 00:00:00", "pageNum": "1",
                             "pageSize": "2"}, cap=2)
c("s2-large-slash", "斜杠日期格式",
  "/api/v1/large/snapshot", {"startTime": "2025/10/01", "endTime": "2025/10/05",
                             "pageNum": "1", "pageSize": "2"}, cap=2)
c("s2-large-epoch", "epoch 毫秒",
  "/api/v1/large/snapshot", {"startTime": "1759248000000", "endTime": "1759593600000",
                             "pageNum": "1", "pageSize": "2"}, cap=2)
c("s2-stats-nofield", "stats/group 缺 groupBy（Java 400 vs Go code:500）",
  "/api/v1/large/stats/group", {"type": "snapshot", "startTime": T1, "endTime": T2})
c("s2-stats-countfield", "stats/group 指定 countField（Go 是否真的用它）",
  "/api/v1/large/stats/group", {"type": "snapshot", "startTime": T1, "endTime": T2,
                                "groupBy": "gantrycode", "countField": "platenumber",
                                "topN": "5"}, cap=0)
c("s2-stats-badtopn", "stats/group topN=abc（Java 类型 400 vs Go 默认 100）",
  "/api/v1/large/stats/group", {"type": "snapshot", "startTime": T1, "endTime": T2,
                                "groupBy": "gantrycode", "topN": "abc"}, cap=0)
c("s2-stats-topn0", "stats/group topN=0",
  "/api/v1/large/stats/group", {"type": "snapshot", "startTime": T1, "endTime": T2,
                                "groupBy": "gantrycode", "topN": "0"}, cap=0)
c("s2-large-car-noarg", "large/carTrackQueryByCarNo 缺 carNo（Java 必填 400）",
  "/api/v1/large/carTrackQueryByCarNo", {"startTime": T1, "endTime": T2,
                                          "pageNum": "1", "pageSize": "2"}, cap=2)
c("s2-large-pagesize-str", "large pageSize=abc（Java 400 vs Go 回落默认）",
  "/api/v1/large/snapshot", {"startTime": T1, "endTime": T2, "pageSize": "abc"}, cap=2)
c("s2-unified-export-status", "统一导出：未知 taskId 的状态查询形状",
  "/api/v1/unified/export/status/does-not-exist", cap=0)
c("s2-large-export-status", "large 导出：未知 taskId", "/api/v1/large/export/status/nope", cap=0)
c("s2-scalelevel", "渐进式分档（读 table:count:* —— Java db0 / Go db1）",
  "/progressive/scale-level", cap=0)
c("s2-fuzzy-long", "≥7 位车牌走 term 还是 match（Java 词表含 vehicleplate/envehicleid）",
  "/api/v1/large/fee", {"startTime": T1, "endTime": T2, "platenumber": PLATE,
                        "pageSize": "2"}, cap=2)
c("s2-snapshot-list-scope", "snapshotflow list 在两端 sys_config 状态下的 total 对比",
  "/base/snapshotflow/list", {"pageNum": "1", "pageSize": "3"}, cap=3, pk="id")

# ── 写操作（默认不跑，需 --allow-write）──
c("s2-repair-badtype", "sync/repair 未知 type：Java 静默当 SNAPSHOT，Go 报 500（会写 ES，慎跑）",
  "/api/v1/large/sync/repair", {"type": "__bogus__", "startTime": T1, "endTime": T2},
  method="POST", cap=0, write=True)
c("s2-export-submit", "large 导出提交（写文件，taskId 两端不同需归一）",
  "/api/v1/large/export/submit", {"type": "snapshot", "startTime": T1, "endTime": T2},
  method="POST", cap=0, write=True)

if __name__ == "__main__":
    allow = "--allow-write" in sys.argv
    res = run([x for x in C if allow or not x.get("write")],
              out_prefix="probe2c")
    with open(os.path.join(HERE, "..", "raw", "probe2.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
