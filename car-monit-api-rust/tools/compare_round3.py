# -*- coding: utf-8 -*-
"""第三轮复核：以真实数据逐字段打列表过滤条件，比较 Java(9902)/Rust(9911)。

方法：先用无过滤列表取一行样本，再把该行每个非空标量字段作为查询参数分别请求两端，
比较状态码与 total。值中含 'T' 的 ISO 时间串跳过（Java 的 DateUtils.parseDate 白名单
不接受该格式，会静默忽略条件；见 README-MIGRATION 第 7 节第 13 条）。

前置：把 Redis DB0 的 car_list_jc 备份后临时清空，跑完恢复，否则 Java 侧
syncCurrentTrack / carTrackQueryByTime 会因缓存反序列化强转而 500。
"""
import json
import urllib.error
import urllib.parse
import urllib.request

JAVA = 'http://127.0.0.1:9902'
RUST = 'http://127.0.0.1:9911'

# (路径, 名称)
TARGETS = [
    ('/base/fwqjcxx/list', 'fwqjcxx'),
    ('/base/sfsjcxx/list', 'sfsjcxx'),
    ('/base/sfzjcxx/list', 'sfzjcxx'),
    ('/manager/fwqclls/list', 'fwqclls'),
    ('/base/feeGantry/list', 'feeGantry'),
    ('/base/feeStationEnter/list', 'feeStationEnter'),
    ('/base/feestationexit/list', 'feestationexit'),
    ('/base/snapshotflow/list', 'snapshotflow'),
    ('/base/provcapture/list', 'provcapture'),
    ('/base/stationcapture/list', 'stationcapture'),
    ('/base/gantry/list', 'gantry'),
    ('/base/gantryIp/list', 'gantryIp'),
    ('/base/vehicleweight/list', 'vehicleweight'),
    ('/base/section/list', 'section'),
    ('/base/toll/list', 'toll'),
    ('/base/tollStationIp/list', 'tollStationIp'),
    ('/base/org/list', 'org'),
    ('/base/trailtracks/list', 'trailtracks'),
]

# 快照表必须有时间范围才有样本行（与 Java/Go 一致的实测经验）；
# platenumber=%25（LIKE 通配）用来避开 Java 的数据权限分支（没有车牌时会追加 orgcode='030000011'）
SEED = {
    'snapshotflow': 'applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00'
                    '&platenumber=%25',
}
SKIP_KEYS = {
    'id', 'pageNum', 'pageSize', 'searchValue', 'createBy', 'createTime',
    'updateBy', 'updateTime', 'remark', 'params', 'beginTime', 'endTime',
    'trailPoints', 'trailpoints', 'imagesArry', 'snappicturepath',
}
MAX_FIELDS = 12


def fetch(base, path, timeout=120):
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001
        return -1, str(e).encode()


def total(raw):
    try:
        obj = json.loads(raw.decode('utf-8'))
    except Exception:  # noqa: BLE001
        return None
    if isinstance(obj, dict):
        return obj.get('total')
    if isinstance(obj, list):
        return len(obj)
    return None


def sample_row(path, name):
    seed = SEED.get(name, '')
    q = '?pageNum=1&pageSize=1' + ('&' + seed if seed else '')
    st, raw = fetch(JAVA, path + q)
    if st != 200:
        return None
    try:
        return json.loads(raw.decode('utf-8'))['rows'][0]
    except Exception:  # noqa: BLE001
        return None


def main():
    bad = 0
    checked = 0
    for path, name in TARGETS:
        row = sample_row(path, name)
        if not row:
            print('SKIP %s（无样本行）' % name)
            continue
        seed = SEED.get(name, '')
        base_q = '?pageNum=1&pageSize=1' + ('&' + seed if seed else '')
        keys = [
            k for k, v in row.items()
            if k not in SKIP_KEYS
            and isinstance(v, (str, int, float))
            and str(v).strip() != ''
        ][:MAX_FIELDS]
        for k in keys:
            # 探针字段与种子参数同名时去掉种子里的那一份：重复键会让 Java 取首值、
            # 而 HTTP 层默认可能报 400，测的就不再是同一个语义
            q = base_q
            if ('&%s=' % k) in q:
                q = '&'.join(p for p in q.split('&') if not p.startswith('%s=' % k))
            url = '%s%s&%s=%s' % (path, q, k, urllib.parse.quote(str(row[k])))
            ja = fetch(JAVA, url)
            ru = fetch(RUST, url)
            checked += 1
            if ja[0] != ru[0] or total(ja[1]) != total(ru[1]):
                bad += 1
                print('DIFF %-16s %-22s %-18s java=%s/%s rust=%s/%s' % (
                    name, k, str(row[k])[:18], ja[0], total(ja[1]), ru[0], total(ru[1])))
    print('SUMMARY checked=%d bad=%d' % (checked, bad))


if __name__ == '__main__':
    main()
