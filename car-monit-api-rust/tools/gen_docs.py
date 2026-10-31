# -*- coding: utf-8 -*-
"""从 Java controller 抽取 85 个端点并生成迁移文档（阶段一/二/四）。"""
import glob
import io
import os
import re

JAVA_ROOT = '../pro-business-api/src/main/java/com/ruoyi/base/controller'


def extract_endpoints():
    rows = []
    for path in sorted(glob.glob(os.path.join(JAVA_ROOT, '*.java'))):
        src = io.open(path, encoding='utf-8').read()
        src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
        src = re.sub(r'//.*', '', src)
        cm = re.search(r'@RequestMapping\((?:value\s*=\s*)?"([^"]+)"', src)
        base = cm.group(1) if cm else ''
        cls = os.path.basename(path)[:-5]
        for m in re.finditer(r'@(Get|Post|Put|Delete)Mapping\((?:value\s*=\s*)?"?([^"\)]*)"?\)\s*(?:public\s+)?[^\(]*?\s+(\w+)\s*\(', src):
            method = m.group(1).upper()
            sub = m.group(2).strip()
            jmethod = m.group(3)
            rows.append((method, base + sub, cls, jmethod))
    return rows


def rust_handler(method, path, cls):
    if path.startswith('/base/sysutilTest/'):
        if path.endswith('syncBaseInfo'):
            return 'selftest::sync_base_info'
        if path.endswith('syncCurrentTrack'):
            return 'selftest::sync_current_track'
        if path.endswith('syncHistroyTrack'):
            return 'selftest::sync_histroy_track'
        if 'syncSuspiciousCar' in path:
            return 'router::blocked_sync_suspicious'
        if path.endswith('syncOdsSzdnGantry'):
            return 'router::blocked_gantry'
        return 'router::blocked_separate'
    if path.startswith('/base/sysutil/'):
        return {
            '/base/sysutil/saveRedis': 'sysutil::save_redis',
            '/base/sysutil/carTrackQueryByCarNo': 'sysutil::car_track_by_car_no',
            '/base/sysutil/carTrackQueryByTime': 'sysutil::car_track_by_time',
            '/base/sysutil/changeTrailInfo': 'sysutil::change_trail_info',
            '/base/sysutil/getByTrailBo': 'sysutil::get_by_trail_bo',
        }.get(path, '?')
    if path.startswith('/api/v1/large/'):
        return {
            '/api/v1/large/snapshot': 'query::large_query (DsSnapshot)',
            '/api/v1/large/fee': 'query::large_query (DsFee)',
            '/api/v1/large/trail': 'query::large_query (DsTrail)',
            '/api/v1/large/carTrackQueryByCarNo': 'query::car_track_by_car_no',
            '/api/v1/large/stats/group': 'query::group_stats',
            '/api/v1/large/export/submit': 'query::large_export_submit',
            '/api/v1/large/export/status/{taskId}': 'query::large_export_status',
            '/api/v1/large/sync/full': 'query::sync_full',
            '/api/v1/large/sync/incremental': 'query::sync_incremental',
            '/api/v1/large/sync/repair': 'query::sync_repair',
        }.get(path, '?')
    if path.startswith('/api/v1/unified/'):
        return {
            '/api/v1/unified/{ds}/list': 'query::unified_list',
            '/api/v1/unified/{ds}/export/submit': 'query::unified_export_submit',
            '/api/v1/unified/export/status/{taskId}': 'query::unified_export_status',
        }.get(path, '?')
    if path.startswith('/progressive/'):
        return {
            '/progressive/snapshotflow/list': 'query::progressive_list (snapshotflow)',
            '/progressive/feerecords/list': 'query::progressive_list (feerecords)',
            '/progressive/trailfitting/list': 'query::progressive_list (trailfitting)',
            '/progressive/scale-level': 'query::scale_level',
        }.get(path, '?')

    table = {
        'DwdLcztFwqjcxxController': ('fwqjcxx', '/base/fwqjcxx'),
        'DwdLcztSfsjcxxController': ('sfsjcxx', '/base/sfsjcxx'),
        'DwdLcztSfzjcxxController': ('sfzjcxx', '/base/sfzjcxx'),
        'OdsCxztFwqcllsController': ('fwqclls', '/manager/fwqclls'),
        'OdsLwzxsfsjFeeGantryFusion01Controller': ('fee_gantry', '/base/feeGantry'),
        'OdsLwzxsfsjFeeRecords01Controller': ('fee_records', '/base/feerecords'),
        'OdsLwzxsfsjFeeStationEnter01Controller': ('fee_enter', '/base/feeStationEnter'),
        'OdsLwzxsfsjFeeStationExit01Controller': ('fee_exit', '/base/feestationexit'),
        'OdsRtSzdnSnapshotFlowAddcodeController': ('snapshot_flow', '/base/snapshotflow'),
        'OdsRtSzdnSnapshotFlowProvcaptureAddcodeController': ('prov_capture', '/base/provcapture'),
        'OdsRtSzdnSnapshotFlowStationcaptureAddcodeController': ('station_capture', '/base/stationcapture'),
        'OdsSzdnGantryController': ('gantry', '/base/gantry'),
        'OdsSzdnGantryIpController': ('gantry_ip', '/base/gantryIp'),
        'OdsSzdnProvinceBorderVehicleWeightNewstructureController': ('vehicle_weight', '/base/vehicleweight'),
        'OdsSzdnSectionController': ('section', '/base/section'),
        'OdsSzdnTollController': ('toll', '/base/toll'),
        'OdsSzdnTollStationIpController': ('toll_station_ip', '/base/tollStationIp'),
        'OdsYhglVBaseOrgController': ('org', '/base/org'),
        'ZdataTrailTracksController': ('trail_tracks', '/base/trailtracks'),
    }[cls]
    field = table[0]
    if path.endswith('/listAll'):
        return 'crud::%s_all' % field
    if path.endswith('/listToExport'):
        return 'base::%s_export' % ('fee_records' if field == 'fee_records' else 'snapshot_flow')
    if path.endswith('/list'):
        if field in ('fee_records', 'snapshot_flow'):
            return 'base::%s_list' % field
        return 'crud::%s_list' % field
    if path.endswith('/map'):
        return 'crud::vehicle_weight_map'
    if field in ('fee_gantry', 'fee_records', 'snapshot_flow'):
        return 'crud::%s_flat' % field
    return 'crud::%s_ajax' % field


def endpoint_table():
    rows = extract_endpoints()
    out = []
    out.append('| # | Method | Path | Java Controller#method | Rust handler | 鉴权 |')
    out.append('|---|---|---|---|---|---|')
    for i, (method, path, cls, jmethod) in enumerate(rows, 1):
        out.append('| %d | %s | `%s` | `%s#%s` | `%s` | 无（SecurityInterceptor 整文件被注释） |' % (
            i, method, path, cls, jmethod, rust_handler(method, path, cls)))
    return '\n'.join(out), rows


def main():
    table, rows = endpoint_table()
    io.open('docs/_endpoint_table.md', 'w', encoding='utf-8').write(table)
    io.open('docs/_endpoint_count.txt', 'w', encoding='utf-8').write(str(len(rows)))
    print('endpoints', len(rows))


if __name__ == '__main__':
    main()
