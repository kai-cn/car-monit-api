# -*- coding: utf-8 -*-
"""生成 sysutil / 轨迹相关端点的只读用例（sysutil 阶段）。

不包含任何写端点：saveRedis（写 Redis）、sysutilTest/*（触发外部 HTTP + 写库）、
large|unified 的 export/submit 与 sync/* 都放在 write 阶段，需要显式授权才跑。
"""
import json
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402


def q(d):
    return '?' + urllib.parse.urlencode({k: v for k, v in d.items() if v is not None})


def plate_samples():
    st, h, raw, ms, e = H.http_get(H.side_url('java', '/base/trailtracks/list?pageSize=6'), timeout=60)
    d = H.parse_json(raw) or {}
    out = []
    for r in d.get('rows') or []:
        pk = r.get('plateKey')
        if pk and pk not in out:
            out.append(pk)
    return out


def trail_point_of_plate(plate):
    """取一条真实轨迹点 JSON，用于 changeTrailInfo 的请求体。"""
    st, h, raw, ms, e = H.http_get(
        H.side_url('java', '/base/trailtracks/list?plateKey=' + urllib.parse.quote(plate)),
        timeout=60)
    d = H.parse_json(raw) or {}
    rows = d.get('rows') or []
    for r in rows:
        tp = r.get('trailPoints')
        if isinstance(tp, str) and tp.startswith('['):
            try:
                pts = json.loads(tp)
            except Exception:  # noqa: BLE001
                continue
            if pts:
                return r, pts
    return None, None


def main():
    H.ensure_dirs()
    plates = plate_samples()
    cases = []

    # ---------------- carTrackQueryByCarNo ----------------
    time_sets = [
        {},
        {'startTime': '2025-09-10 00:00:00', 'endTime': '2025-09-11 23:59:59'},
        {'startTime': '2025-09-10', 'endTime': '2025-09-11'},
        {'startTime': '', 'endTime': ''},
        {'startTime': '2025-09-10 00:00:00'},
        {'endTime': '2025-09-11 00:00:00'},
        {'startTime': 'garbage', 'endTime': '2025-09-11'},
    ]
    variants = []
    for p in plates[:2]:
        variants.append({'carNo': p})
        variants.append({'carNo': p[:2]})           # 前缀模糊
    variants += [
        {'carNo': ''},
        {'carNo': '%'},
        {'carNo': '不存在车牌ZZZ'},
        {'carNo': "1' OR '1'='1"},
        {'carNo': plates[0] if plates else '赣A12345', 'flag': 'ybn'},
        {'carNo': plates[0] if plates else '', 'flag': 'bannian'},
        {'carNo': plates[0] if plates else '', 'pageNum': '2', 'pageSize': '3'},
        {'carNo': plates[0] if plates else '', 'pageSize': '0'},
        {'carNo': plates[0] if plates else '', 'pageSize': 'abc'},
        {'carNo': plates[0] if plates else '', 'startNum': '0', 'endNum': '2'},
        {'carNo': plates[0] if plates else '', 'starTime': '0', 'endTime': '1'},
        {'carNo': plates[0] if plates else '', 'lastExitTime': '2025-09-10 04:39:49'},
        {'carNo': plates[0] if plates else '', 'lastExitTime': '2025-09-10'},
        {'carNo': plates[0] if plates else '', 'lastExitTime': 'not-a-date'},
        {'carNo': plates[0] if plates else '', 'carNoList': 'a,b'},
        {'carNo': plates[0] if plates else '', 'carNoList': ''},
    ]
    seen = set()
    for i, v in enumerate(variants):
        key = json.dumps(v, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        cases.append({'id': 'sy:carNo:%02d' % i, 'group': 'sysutil-carno',
                      'path': '/base/sysutil/carTrackQueryByCarNo' + q(v), 'method': 'GET'})
    for i, ts in enumerate(time_sets):
        v = dict(ts)
        if not plates:
            v['carNo'] = '赣A12345'
        cases.append({'id': 'sy:carNoT:%02d' % i, 'group': 'sysutil-carno-time',
                      'path': '/base/sysutil/carTrackQueryByCarNo' + q(v), 'method': 'GET'})

    # ---------------- carTrackQueryByTime（依赖各自 Redis DB） ----------------
    for i, v in enumerate([
        {}, {'pageSize': '3'}, {'pageSize': 'abc'}, {'pageNum': '2', 'pageSize': '2'},
        {'startTime': '2025-09-10 00:00:00', 'endTime': '2025-09-11 23:59:59', 'pageSize': '3'},
        {'flag': 'ybn'}, {'carNoList': 'a,b'},
    ]):
        cases.append({'id': 'sy:byTime:%02d' % i, 'group': 'sysutil-bytime',
                      'path': '/base/sysutil/carTrackQueryByTime' + q(v), 'method': 'GET'})

    # ---------------- getByTrailBo ----------------
    for i, v in enumerate([
        {}, {'platenumber': plates[0] if plates else 'x'},
        {'locationCode': 'G003536012000720010'},
        {'captureTime': '2025-09-10 04:39:49'},
        {'isQuery': '1'}, {'directionIn': 'true'}, {'directionIn': '1'},
        {'directionIn': 'abc'}, {'lon': '116.1'}, {'lon': 'abc'},
        {'countNum': '3'}, {'countNum': 'x'}, {'stateType': '1'},
    ]):
        cases.append({'id': 'sy:trailbo:%02d' % i, 'group': 'sysutil-getByTrailBo',
                      'path': '/base/sysutil/getByTrailBo' + q(v), 'method': 'GET'})

    # ---------------- changeTrailInfo（POST，纯转换，无副作用） ----------------
    tracks, pts = (None, None)
    for p in plates:
        tracks, pts = trail_point_of_plate(p)
        if tracks:
            break
    bodies = [
        ({}, 'empty'),
        ({'tracks': None, 'trailList': None}, 'nulls'),
        ({'trailList': []}, 'empty-list'),
        ({'trailUuid': 'abc'}, 'only-uuid'),
    ]
    if tracks:
        slim = {k: v for k, v in tracks.items() if k in (
            'uuid', 'plateKey', 'type', 'enterTime', 'exitTime', 'pointCount',
            'startLon', 'stratLat', 'endLon', 'endLat', 'trailPoints')}
        bodies.append(({'tracks': slim, 'trailList': (pts or [])[:3]}, 'real'))
        bodies.append(({'tracks': slim}, 'tracks-only'))
        bodies.append(({'trailList': (pts or [])[:2]}, 'list-only'))
        bodies.append(({'tracks': dict(slim, startLon='116.5', stratLat='28.5',
                                       endLon='117.5', endLat='29.5'),
                        'trailList': (pts or [])[:3]}, 'with-dec'),)
        bodies.append(({'tracks': dict(slim, startLon='not-a-number'),
                        'trailList': (pts or [])[:2]}, 'bad-dec'))
    bodies.append(({'tracks': {'plateKey': 'x'}, 'trailList': [{'platenumber': 'x'}]}, 'minimal'))
    bodies.append(([], 'array'))
    bodies.append(('not-json', 'raw'))
    for i, (b, tag) in enumerate(bodies):
        body = b if not isinstance(b, str) else b
        cases.append({'id': 'sy:change:%02d-%s' % (i, tag), 'group': 'sysutil-changeTrailInfo',
                      'path': '/base/sysutil/changeTrailInfo', 'method': 'POST',
                      'body': body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)})

    with open(os.path.join(H.CASE_DIR, 'sysutil.json'), 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=0)
    print('sysutil cases=%d (plates=%d, has_tracks=%s)' % (len(cases), len(plates), bool(tracks)))


if __name__ == '__main__':
    main()
