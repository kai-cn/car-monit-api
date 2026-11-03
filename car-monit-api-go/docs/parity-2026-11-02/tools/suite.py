# -*- coding: utf-8 -*-
"""用例表：19 张基础表 CRUD + 查询/导出/统计 + sysutil/sysutilTest + 横切探针。

CRUD 的过滤条件不是凭空写的：先用 --gen 打一次 Java，取回真实存在数据的首行，
把它的若干字段值当过滤参数用。这样「查不到」只会是谓词构造不一致，而不是条件本身没数据。
"""
from __future__ import annotations

import json
import os
import sys

from parity import JAVA, GO, http_call, parse, rows_of, pick_pk, dump  # noqa: F401

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
CASES_JSON = os.path.join(HERE, "cases.json")
SAMPLE_JSON = os.path.join(HERE, "samples.json")

# (组名, 路径, id 参数名, 有 listAll, 有 listToExport, id 是否数字, 主键字段)
TABLES = [
    ("fwqjcxx",        "/base/fwqjcxx",         "agentPk",     True,  False, False, "agentPk"),
    ("sfsjcxx",        "/base/sfsjcxx",         "agentPk",     True,  False, False, "agentPk"),
    ("sfzjcxx",        "/base/sfzjcxx",         "agentPk",     True,  False, False, "agentPk"),
    ("fwqclls",        "/manager/fwqclls",      "bigId",       False, False, True,  "bigId"),
    ("feeGantry",      "/base/feeGantry",       "bigId",       False, False, False, "bigId"),
    ("feerecords",     "/base/feerecords",      "bigId",       False, True,  False, "bigId"),
    ("feeStationEnter", "/base/feeStationEnter", "bigId",      False, False, True,  "bigId"),
    ("feestationexit", "/base/feestationexit",  "bigId",       False, False, False, "bigId"),
    ("snapshotflow",   "/base/snapshotflow",    "bigId",       False, True,  False, "datauuid"),
    ("provcapture",    "/base/provcapture",     "bigId",       False, False, True,  "bigId"),
    ("stationcapture", "/base/stationcapture",  "bigId",       False, False, True,  "bigId"),
    ("gantry",         "/base/gantry",          "id",          True,  False, False, "id"),
    ("gantryIp",       "/base/gantryIp",        "id",          False, False, True,  "id"),
    ("vehicleweight",  "/base/vehicleweight",   "dataSource",  False, False, False, "-"),
    ("section",        "/base/section",         "id",          True,  False, False, "id"),
    ("toll",           "/base/toll",            "id",          True,  False, False, "id"),
    ("tollStationIp",  "/base/tollStationIp",   "id",          False, False, True,  "id"),
    ("org",            "/base/org",             "bigId",       True,  False, False, "bigId"),
    ("trailtracks",    "/base/trailtracks",     "uuid",        False, False, False, "uuid"),
]

TIME_FIELDS = ("createTime", "captureTime", "driveTime", "updateTime", "tradeTime",
               "passTime", "weightTime", "exTime", "enTime", "uploadTime", "timestime")

# 服务端每次响应都重新生成 id 的两张表（Java 在 Controller 里 rtn.setId(StringUtils.getUUID())，
# 实测 :9902 两次同一请求返回的 id 不同）。用 datauuid/bigId 对齐行，并把 id 列为豁免字段，
# 否则整表永远被判成"每行都不一致"。
RANDOM_ID_TABLES = {"snapshotflow", "feeGantry"}
SKIP_FILTER = {"id", "bigId", "uuid", "pageNum", "pageSize", "total"}
WRITE_HEAVY = {  # GET 即触发全量同步/写库，只做 405 存在性探针
    "/base/sysutilTest/syncCurrentTrack", "/base/sysutilTest/syncBaseInfo",
    "/base/sysutilTest/syncHistroyTrack", "/base/sysutilTest/syncSuspiciousCar",
    "/base/sysutilTest/syncOdsSzdnGantry", "/base/sysutilTest/separateSnapshotFlowTimeList",
    "/base/sysutil/saveRedis", "/api/v1/large/sync/full",
    "/api/v1/large/sync/incremental", "/api/v1/large/sync/repair",
}


def java_sample(path, params):
    """从 Java 拿一行真实数据，用于派生过滤条件与主键值。"""
    r = http_call(JAVA, "GET", path, params)
    obj, _ = parse(r)
    rows, _ = rows_of(obj)
    if rows:
        return rows[0], len(rows), obj
    return None, 0, obj


def derive_filters(row):
    """挑若干「有值、非主键、可当条件」的字段。"""
    out = []
    for k, v in (row or {}).items():
        if k in SKIP_FILTER or k in TIME_FIELDS:
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)) or (isinstance(v, str) and 0 < len(v) <= 40):
            out.append((k, v))
        if len(out) >= 4:
            break
    return out


def build_crud():
    cases, samples = [], {}
    for name, path, idp, has_all, has_exp, numeric, pk in TABLES:
        base = path + "/list"
        p1 = {"pageNum": "1", "pageSize": "5"}
        obj = None
        r = http_call(JAVA, "GET", base, p1)
        obj, _ = parse(r)
        rows, _ = rows_of(obj)
        row0 = rows[0] if rows else None
        samples[name] = {"path": base, "pk": pk,
                         "pk_value": (row0 or {}).get(pk),
                         "filters": derive_filters(row0),
                         "row_count": len(rows or []),
                         "total": obj.get("total") if isinstance(obj, dict) else None}

        def C(suffix, note, params=None, cap=100, path_=None, method="GET", body=None):
            cases.append({"id": f"{name}-{suffix}", "group": name, "note": note,
                          "method": method, "path": path_ or base,
                          "params": params, "body": body, "cap": cap, "pk": pk,
                          "ignore": ["id"] if name in RANDOM_ID_TABLES else None})

        C("list-default", "分页默认", p1)
        C("list-page2", "第二页", {"pageNum": "2", "pageSize": "5"})
        C("list-noargs", "不传分页参数（Java 默认 10 / Go 默认待测）", None, cap=50)
        C("list-pagesize0", "pageSize=0 边界", {"pageNum": "1", "pageSize": "0"})
        C("list-pagesize-1", "pageSize=-1 边界", {"pageNum": "1", "pageSize": "-1"})
        C("list-bigpagesize", "pageSize=5000（Go 侧是否截到 1000）",
          {"pageNum": "1", "pageSize": "5000"}, cap=6000)
        C("list-farpage", "翻到超出总页数（Java reasonable=true 会回夹到末页）",
          {"pageNum": "99999", "pageSize": "5"})
        C("list-order", "orderByColumn/isAsc（Java 生效、Go 忽略）",
          {"pageNum": "1", "pageSize": "5", "orderByColumn": pk, "isAsc": "desc"})
        for fld, val in samples[name]["filters"]:
            C("filter-" + fld, f"等值过滤 {fld}={val}",
              {"pageNum": "1", "pageSize": "5", fld: val}, cap=5)
        # 全集合比对：绕开「无 ORDER BY → 分页成员不确定」的干扰
        total = samples[name]["total"]
        if isinstance(total, int) and 0 < total <= 3000:
            C("full-set", f"整表集合比对（pageSize={total}，按 {pk} 对齐，忽略顺序）",
              {"pageNum": "1", "pageSize": str(total)}, cap=total)
        # 主键详情
        pkv = samples[name]["pk_value"]
        if pkv not in (None, ""):
            C("info", f"详情 /{{{idp}}} 命中 {idp}={pkv}", {idp: pkv},
              path_=f"{path}/{pkv}", cap=0)
            C("info-miss", "详情 /{" + idp + "} 不存在",
              None, path_=f"{path}/__no_such_id__", cap=0)
            if numeric:
                C("info-badid", "详情 非数字 id（Spring 类型转换 400）",
                  None, path_=f"{path}/not-a-number", cap=0)
        if has_all:
            C("listAll", "全量列表（裸数组，无信封）", None, path_=path + "/listAll", cap=200)
        if has_exp:
            C("listToExport", "导出列表（裸数组）",
              {"pageNum": "1", "pageSize": "5"}, path_=path + "/listToExport", cap=100)
        if name == "vehicleweight":
            C("map", "写死 uuid 的探针接口", None, path_=path + "/map", cap=0)
    return cases, samples


def build_query():
    c = []

    def C(cid, note, path, params=None, method="GET", body=None, cap=50, write=False):
        c.append({"id": cid, "group": "query", "note": note, "method": method,
                  "path": path, "params": params, "body": body, "cap": cap,
                  "write": write})

    W = "2025-10-01 00:00:00"
    W2 = "2025-10-02 00:00:00"
    C("large-snapshot", "大表快照分页（DB 路径）", "/api/v1/large/snapshot",
      {"startTime": W, "endTime": W2, "pageNum": "1", "pageSize": "5"})
    C("large-fee", "大表收费分页", "/api/v1/large/fee",
      {"startTime": W, "endTime": W2, "pageNum": "1", "pageSize": "5"})
    C("large-trail", "大表轨迹分页", "/api/v1/large/trail",
      {"startTime": W, "endTime": W2, "pageNum": "1", "pageSize": "5"})
    C("large-cartrack", "按车牌查轨迹（large 版）", "/api/v1/large/carTrackQueryByCarNo",
      {"carNo": "赣AF12345", "startTime": W, "endTime": W2,
       "pageNum": "1", "pageSize": "5"})
    C("large-stats", "分组统计", "/api/v1/large/stats/group",
      {"type": "snapshot", "startTime": W, "endTime": W2,
       "groupBy": "gantryName", "topN": "10"})
    C("large-stats-badgroup", "分组统计非法列", "/api/v1/large/stats/group",
      {"type": "snapshot", "startTime": W, "endTime": W2, "groupBy": "not_a_col;drop", "topN": "10"})
    C("large-window-huge", "跨 30 天窗口（ES 强制路由阈值）", "/api/v1/large/snapshot",
      {"startTime": "2025-09-01 00:00:00", "endTime": "2025-10-01 00:00:00",
       "pageNum": "1", "pageSize": "5"})
    C("large-badtime", "时间格式非法", "/api/v1/large/snapshot",
      {"startTime": "2025-10-01", "endTime": "abc", "pageNum": "1", "pageSize": "5"})
    # 第五轮新增：Java 的降级路径用 java.sql.Timestamp.valueOf，只认
    # "yyyy-MM-dd HH:mm:ss"；纯日期与带 T 的 ISO 串都会抛 → query() 吞掉 → data=[]。
    # Go 的解析更宽，同样请求能查出数据。原用例只测了完整格式，这条差异一直没被覆盖。
    C("large-plaindate", "纯日期时间（Java Timestamp.valueOf 不接受）", "/api/v1/large/snapshot",
      {"startTime": "2025-10-01", "endTime": "2025-10-02", "pageNum": "1", "pageSize": "5"})
    C("large-tformattime", "ISO 带 T 的时间（同上）", "/api/v1/large/snapshot",
      {"startTime": "2025-10-01T00:00:00", "endTime": "2025-10-02T00:00:00",
       "pageNum": "1", "pageSize": "5"})
    C("unified-plaindate", "统一查询纯日期时间", "/api/v1/unified/snapshot/list",
      {"startTime": "2025-10-01", "endTime": "2025-10-02", "pageNum": "1", "pageSize": "5"})
    C("large-missing-arg", "缺必填 startTime", "/api/v1/large/snapshot",
      {"endTime": W2})
    C("large-fuzzy", "fuzzyFields 复合参数", "/api/v1/large/snapshot",
      {"startTime": W, "endTime": W2, "plateNumber": "赣A", "gantryName": "瑞金",
       "pageNum": "1", "pageSize": "5"})
    C("unified-snapshot", "统一查询 snapshot", "/api/v1/unified/snapshot/list",
      {"startTime": W, "endTime": W2, "pageNum": "1", "pageSize": "5"})
    C("unified-fee", "统一查询 fee", "/api/v1/unified/fee/list",
      {"startTime": W, "endTime": W2, "pageNum": "1", "pageSize": "5"})
    C("unified-trail", "统一查询 trail", "/api/v1/unified/trail/list",
      {"startTime": W, "endTime": W2, "pageNum": "1", "pageSize": "5"})
    C("unified-baddb", "统一查询未知 ds", "/api/v1/unified/__nope__/list",
      {"startTime": W, "endTime": W2})
    C("prog-snapshotflow", "渐进式快照（游标首页）", "/progressive/snapshotflow/list",
      {"startTime": W, "endTime": W2, "pageSize": "5"})
    C("prog-feerecords", "渐进式收费", "/progressive/feerecords/list",
      {"startTime": W, "endTime": W2, "pageSize": "5"})
    C("prog-trailfitting", "渐进式轨迹拟合", "/progressive/trailfitting/list",
      {"startTime": W, "endTime": W2, "pageSize": "5"})
    C("prog-noargs", "渐进式无参（默认窗口）", "/progressive/snapshotflow/list", None)
    C("prog-scalelevel", "当前分档", "/progressive/scale-level", None, cap=0)
    C("prog-filter", "渐进式带车牌过滤", "/progressive/snapshotflow/list",
      {"startTime": W, "endTime": W2, "platenumber": "赣A", "pageSize": "5"})
    C("export-status-unknown", "导出状态：不存在的 taskId", "/api/v1/large/export/status/nope",
      None, cap=0)
    C("unified-export-status-unknown", "统一导出状态：不存在的 taskId",
      "/api/v1/unified/export/status/nope", None, cap=0)
    return c


def build_sysutil():
    c = []

    def C(cid, note, path, params=None, method="GET", body=None, cap=50, write=False):
        c.append({"id": cid, "group": "sysutil", "note": note, "method": method,
                  "path": path, "params": params, "body": body, "cap": cap,
                  "write": write})

    # CarParaVO 的真实契约是 carNo / applyTime1 / applyTime2 / flag。
    # 上一版用例写的是 plateNo/startTime/endTime，其中 endTime 在 VO 里是 Integer，
    # 传时间串会被 Spring 判成类型转换失败 → 400，那是用例错、不是接口错。
    PLATE = "粤DZW906"
    C("cartrack-by-carno", "按车牌查轨迹（Controller 强制 flag=bannian）",
      "/base/sysutil/carTrackQueryByCarNo",
      {"carNo": PLATE, "pageNum": "1", "pageSize": "5"}, cap=30)
    C("cartrack-blank", "车牌为空", "/base/sysutil/carTrackQueryByCarNo",
      {"carNo": "", "pageNum": "1", "pageSize": "5"}, cap=30)
    C("cartrack-range", "按车牌 + applyTime1/2 区间（绕开 bannian 的相对窗口）",
      "/base/sysutil/carTrackQueryByCarNo",
      {"carNo": PLATE, "applyTime1": "2025-09-30 00:00:00",
       "applyTime2": "2025-10-02 23:59:59", "pageNum": "1", "pageSize": "5"}, cap=30)
    C("cartrack-by-time", "按时间查轨迹（读 car_list_jc）",
      "/base/sysutil/carTrackQueryByTime", {"pageNum": "1", "pageSize": "5"}, cap=6)
    C("cartrack-by-time-size0", "pageSize=0 边界（防止 limit=0 退化成「不加 LIMIT」→ 全表扫描）",
      "/base/sysutil/carTrackQueryByTime", {"pageNum": "1", "pageSize": "0"}, cap=4)
    C("cartrack-bycarno-size0", "ByCarNo pageSize=0 边界（同上）",
      "/base/sysutil/carTrackQueryByCarNo", {"carNo": PLATE, "pageNum": "1", "pageSize": "0"}, cap=4)
    C("cartrack-by-time-size-1", "pageSize=-1 边界",
      "/base/sysutil/carTrackQueryByTime", {"pageNum": "1", "pageSize": "-1"}, cap=4)
    C("cartrack-by-time-far", "同接口越界页（Java reasonable 回夹末页）",
      "/base/sysutil/carTrackQueryByTime", {"pageNum": "999", "pageSize": "2"}, cap=4)
    C("cartrack-by-time-order", "同接口 + 排序参数",
      "/base/sysutil/carTrackQueryByTime",
      {"pageNum": "1", "pageSize": "5", "orderByColumn": "carNo", "isAsc": "desc"}, cap=6)
    # getByTrailBo 的派发字段是 stateType（不是 type），样本取自 Java 真实响应
    for st, pu in (("GantryCapture", "189727e7-9392-4ae3-82ce-166864e93ddd"),
                   ("StationCapture", "fdbcfa5a-3966-47cf-b3aa-824372ab7eec"),
                   ("BorderWeighingCapture", "7379e7aa-e325-449b-9728-b8f6940c77f1"),
                   ("ServiceAreaCapture", "18f8e2af-6ebe-4b33-8f37-a688f441de37"),
                   ("FeeRecord", "cef80c7cb8144961aefd13afedc5278b"),
                   ("Bogus", "no-such-uuid")):
        C(f"getbytrailbo-{st}", f"抓拍回源 stateType={st}", "/base/sysutil/getByTrailBo",
          {"stateType": st, "pointUuid": pu, "captureTime": "2025-10-01 00:02:36",
           "plateNumber": PLATE, "devCode": "G601136060000420010"}, cap=0)
    C("change-post", "对象转换（有 tracks+trailList）", "/base/sysutil/changeTrailInfo",
      method="POST", cap=0,
      body={"tracks": {"plateKey": "赣AF12345", "startLon": "116.1", "stratLat": "26.2",
                       "endLon": "115.0", "endLat": "25.0"},
            "trailList": [{"type": "1", "plateNo": "赣AF12345"}]})
    C("change-post-empty", "对象转换（空对象，走 fall-through）",
      "/base/sysutil/changeTrailInfo", method="POST", cap=0, body={})
    C("change-post-notrail", "对象转换（tracks 有、trailList 空）",
      "/base/sysutil/changeTrailInfo", method="POST", cap=0,
      body={"tracks": {"plateKey": "赣A"}, "trailList": []})
    C("synctrack-commented", "Java 已注释掉的 /syncTrack（应 404）",
      "/base/sysutil/syncTrack", method="POST", cap=0, body={})
    C("syncsuspicious-commented", "Java 已注释掉的 /syncSuspiciousCar（应 404）",
      "/base/sysutil/syncSuspiciousCar", method="POST", cap=0, body={})
    return c


def build_crosscut():
    c = []

    def C(cid, note, path, params=None, method="GET", body=None, cap=0):
        c.append({"id": cid, "group": "crosscut", "note": note, "method": method,
                  "path": path, "params": params, "body": body, "cap": cap})

    C("404-path", "不存在的路径（Spring /error vs gin NoRoute）", "/no/such/endpoint")
    C("404-deep", "深路径不存在", "/base/notatable/list")
    C("405-list-post", "/base/gantry/list 用 POST（方法不匹配）",
      "/base/gantry/list", method="POST", body={})
    C("405-info-delete", "/base/gantry/18 用 DELETE", "/base/gantry/18", method="DELETE")
    C("trailing-slash", "结尾斜杠（Spring 与 gin 的重写策略）", "/base/gantry/list/",
      params={"pageSize": "1"})
    C("bad-json-post", "POST 非法 JSON 体", "/base/sysutil/changeTrailInfo",
      method="POST", body="NOT-JSON")
    C("empty-post", "POST 空体", "/base/sysutil/changeTrailInfo", method="POST")
    C("type-mismatch", "pageSize 非数字", "/base/gantry/list",
      params={"pageSize": "abc"})
    C("sql-ish-param", "参数含单引号（过滤参数注入面）", "/base/gantry/list",
      params={"gantryName": "O'Brien", "pageSize": "5"})
    C("unicode-param", "参数含中文与空格", "/base/gantry/list",
      params={"gantryName": "瑞金北 互通", "pageSize": "5"})
    return c


def build_existence_probes():
    """对写操作过重的端点，只用 405 探针确认路由存在（不执行 handler）。"""
    c = []
    for p in sorted(WRITE_HEAVY):
        c.append({"id": "exists" + p.replace("/", "_"), "group": "exists",
                  "note": "405 探针：仅确认路由存在，不触发同步", "method": "POST",
                  "path": p, "cap": 0, "expect": "status-only"})
    for i in range(1, 11):
        p = f"/base/sysutilTest/syncSuspiciousCar{i}"
        c.append({"id": "exists" + p.replace("/", "_"), "group": "exists",
                  "note": "405 探针：Go 侧 501 桩 vs Java 真实现", "method": "POST",
                  "path": p, "cap": 0, "expect": "status-only"})
    return c


ALL_BUILDERS = [build_crud, build_query, build_sysutil, build_crosscut, build_existence_probes]


def gen():
    cases, samples = [], {}
    for b in ALL_BUILDERS:
        if b is build_crud:
            cs, sm = build_crud()
            cases += cs
            samples = sm
        else:
            cases += b()
    with open(CASES_JSON, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=1)
    with open(SAMPLE_JSON, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=1)
    print(f"生成 {len(cases)} 条用例 → cases.json")
    for name, s in samples.items():
        print(f"  {name:16s} pk={s['pk']}={str(s['pk_value'])[:24]:24s} "
              f"rows={s['row_count']} filters={[x[0] for x in s['filters']]}")
    return cases


if __name__ == "__main__":
    gen()
