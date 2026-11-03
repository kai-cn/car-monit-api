# -*- coding: utf-8 -*-
"""把 Java mapper XML 的 <if> 过滤列 与 Go repo 的 tx.Where 列 做机械对照。

为什么这样做：过滤条件是「接口看起来一样、结果集却不同」的头号来源，
而它无法靠抽查响应发现（要构造出恰好命中差集的参数）。XML 与 Go 源码都能静态解析，
所以直接对齐列名集合，比逐字段实测覆盖面大得多。

用法： python predicates.py            # 全部表
      python predicates.py trailtracks
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

JAVA = r"D:\work\IdeaProjects\car-monit-api\pro-business-api\src\main\java\com\ruoyi\base\mapper\xml"
GO = r"D:\work\IdeaProjects\car-monit-api\car-monit-api-go\internal\repo"

IF_RE = re.compile(r"<if\s+test=\"([^\"]*)\">(.*?)</if>", re.S)
COL_RE = re.compile(r"t\.([a-z_0-9]+)\s*(=|like|&gt;=|&lt;=|>=|<=|IN|is)", re.I)
PROP_RE = re.compile(r"#\{([A-Za-z0-9_.]+)\}")
WHERE_RE = re.compile(r"\.Where\(\s*\"([^\"]+)\"")


def java_filters(xml_name: str):
    """取列表查询用的 <if> 条件：列名 + 属性名。"""
    path = os.path.join(JAVA, xml_name)
    if not os.path.exists(path):
        return None, []
    src = open(path, encoding="utf-8", errors="replace").read()
    # 只看 select id 里带 List 的那个，避免混入 getLatestTrail / 计数语句
    blocks = re.findall(r'<select\s+id="([^"]+)"(.*?)</select>', src, re.S)
    want = [b for n, b in blocks if "List" in n or "list" in n]
    if not want:
        want = [b for _, b in blocks] or [src]
    body = "\n".join(want)
    out = []
    for m in IF_RE.finditer(body):
        test, inner = m.group(1), m.group(2)
        cols = [c[0].lower() for c in COL_RE.findall(inner)]
        props = PROP_RE.findall(inner)
        for p in props:
            if p in ("startNum", "endNum", "params", "flag"):
                continue
            out.append((p, sorted(set(cols)) or ["?"], test.strip()[:60]))
        if not props and cols:
            out.append(("<no-param>", sorted(set(cols)), test.strip()[:60]))
    # 去重
    seen, uniq = set(), []
    for p, c, t in out:
        if (p, tuple(c)) in seen:
            continue
        seen.add((p, tuple(c)))
        uniq.append((p, c, t))
    return blocks, uniq


def go_filters(go_file: str):
    """取 Go 里出现的 WHERE 列名。"""
    path = os.path.join(GO, go_file)
    if not os.path.exists(path):
        return None, []
    src = open(path, encoding="utf-8", errors="replace").read()
    cols = []
    for m in WHERE_RE.finditer(src):
        q = m.group(1)
        for c in re.findall(r"([a-z_][a-z_0-9]*)\s*(=|>=|<=|LIKE|ILIKE|IN|is)", q, re.I):
            cols.append(c[0].lower())
    return src, sorted(set(cols))


# Java XML ↔ Go repo 文件对照（按 Controller 的表）
PAIRS = [
    ("DwdLcztFwqjcxxMapper.xml", "dwd_lczt_fwqjcxx.go", "fwqjcxx"),
    ("DwdLcztSfsjcxxMapper.xml", "dwd_lczt_sfsjcxx.go", "sfsjcxx"),
    ("DwdLcztSfzjcxxMapper.xml", "dwd_lczt_sfzjcxx.go", "sfzjcxx"),
    ("OdsCxztFwqcllsMapper.xml", "ods_cxzt_fwqclls.go", "fwqclls"),
    ("OdsLwzxsfsjFeeGantryFusion01Mapper.xml", "ods_lwzxsfsj_fee_gantry_fusion01.go", "feeGantry"),
    ("OdsLwzxsfsjFeeRecords01Mapper.xml", "ods_lwzxsfsj_fee_records01.go", "feerecords"),
    ("OdsLwzxsfsjFeeStationEnter01Mapper.xml", "ods_lwzxsfsj_fee_station_enter01.go", "feeStationEnter"),
    ("OdsLwzxsfsjFeeStationExit01Mapper.xml", "ods_lwzxsfsj_fee_station_exit01.go", "feestationexit"),
    ("OdsRtSzdnSnapshotFlowAddcodeMapper.xml", "ods_rt_szdn_snapshot_flow_addcode.go", "snapshotflow"),
    ("OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.xml", "ods_rt_szdn_snapshot_flow_provcapture_addcode.go", "provcapture"),
    ("OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.xml", "ods_rt_szdn_snapshot_flow_stationcapture_addcode.go", "stationcapture"),
    ("OdsSzdnGantryMapper.xml", "ods_szdn_gantry.go", "gantry"),
    ("OdsSzdnGantryIpMapper.xml", "ods_szdn_gantry_ip.go", "gantryIp"),
    ("OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.xml", "ods_szdn_province_border_vehicle_weight_newstructure.go", "vehicleweight"),
    ("OdsSzdnSectionMapper.xml", "ods_szdn_section.go", "section"),
    ("OdsSzdnTollMapper.xml", "ods_szdn_toll.go", "toll"),
    ("OdsSzdnTollStationIpMapper.xml", "ods_szdn_toll_station_ip.go", "tollStationIp"),
    ("OdsYhglVBaseOrgMapper.xml", "ods_yhgl_v_base_org.go", "org"),
    ("ZdataTrailTracksMapper.xml", "zdata_trail_tracks.go", "trailtracks"),
]

ORDER_RE = re.compile(r"order\s+by\s+([a-z_0-9.,\s]+)", re.I)


def main(only=None):
    print(f"{'表':16s} {'Java列':44s} {'Go有':6s} {'Go另有':30s}")
    print("-" * 110)
    rows = []
    for xml, gof, tag in PAIRS:
        if only and only.lower() not in (tag + xml + gof).lower():
            continue
        _, jf = java_filters(xml)
        jcols = sorted({c for _, cs, _ in jf for c in cs if c != "?"})
        gsrc, gcols = go_filters(gof)
        if gsrc is None:
            print(f"{tag:16s} {'?':44s} 缺 Go 文件 {gof}")
            continue
        have = [c for c in jcols if c in gcols]
        miss = [c for c in jcols if c not in gcols]
        extra = [c for c in gcols if c not in jcols]
        # Java 侧属性数
        props = [p for p, _, _ in jf]
        # 排序
        src = open(os.path.join(JAVA, xml), encoding="utf-8", errors="replace").read()
        jorder = " | ".join(set(o.strip() for o in ORDER_RE.findall(src)))[:38] or "-"
        gorder = (re.search(r'\.Order\("([^"]+)"\)', gsrc).group(1)
                  if re.search(r'\.Order\("([^"]+)"\)', gsrc) else "-")
        rows.append((tag, jcols, miss, extra, props, jorder, gorder))
        print(f"{tag:16s} {str(len(jcols))+'列/'+str(len(props))+'参':44s} "
              f"缺{len(miss):<2d} 多{len(extra):<2d}  orderJava=[{jorder}] orderGo=[{gorder[:24]}]")
        if miss:
            print(f"{'':16s} Java 有而 Go 未实现: {', '.join(miss)}")
        if extra:
            print(f"{'':16s} Go 自行新增: {', '.join(extra)}")
    return rows


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
