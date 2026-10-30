# -*- coding: utf-8 -*-
"""t08 基础设施自检：Environment 占位符解析 + LambdaQueryWrapper 排序/截断。"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from org.springframework.core.env.Environment import Environment  # noqa: E402
from com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper import (  # noqa: E402
    LambdaQueryWrapper,
)

failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


yml = os.path.join(BASE, "pro-business-api", "src", "main", "resources", "application.yml")
env = Environment([yml])

# 1) 读取 application.yml 的 sync 段
check("yml batch-size", env.getProperty("sync.batch-size"), 1000)
check("yml bool", env.getProperty("sync.full-sync-enabled"), True)
check("yml long", env.value("${sync.incremental-sync-interval:60000}", int), 60000)

# 2) 默认值兜底
check("default used", env.value("${sync.not-exists:42}", int), 42)
check("default str", env.value("${sync.not-exists:abc}"), "abc")

# 3) 环境变量优先（Spring 松弛绑定 sync.batch-size -> SYNC_BATCH_SIZE）
os.environ["SYNC_BATCH_SIZE"] = "5000"
check("env override", env.value("${sync.batch-size:1000}", int), 5000)
del os.environ["SYNC_BATCH_SIZE"]

# 4) 无默认值且缺失 -> 抛异常（与 Spring 启动失败一致）
try:
    env.value("${sync.missing}", int)
    check("missing raises", "no-raise", "KeyError")
except KeyError:
    check("missing raises", "KeyError", "KeyError")

# 5) Wrapper：条件 + 排序 + LIMIT（走 BaseMapper.selectList 的 sortRows 分支）
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode  # noqa: E402
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import (  # noqa: E402
    OdsRtSzdnSnapshotFlowAddcodeMapper,
)


class _Row(object):
    def __init__(self, big_id, snapshottime, datauuid):
        self.big_id = big_id
        self.snapshottime = snapshottime
        self.datauuid = datauuid


rows = [
    _Row(5, "2026-10-21 10:00:00", "u5"),
    _Row(3, "2026-10-21 08:00:00", "u3"),
    _Row(9, "2026-10-21 12:00:00", "u9"),
    _Row(1, "2026-10-21 06:00:00", "u1"),
]
wrapper = (
    LambdaQueryWrapper()
    .gt("big_id", 1)
    .le("snapshottime", "2026-10-21 12:00:00")
    .orderByAsc("big_id")
    .last("LIMIT 2")
)
kept = [r for r in rows if wrapper.toPredicate()(r)]
check("where", [r.datauuid for r in kept], ["u5", "u3", "u9"])
check("order+limit", [r.datauuid for r in wrapper.sortRows(kept)], ["u3", "u5"])

# 6) between + 降序
wrapper2 = LambdaQueryWrapper().between("big_id", 3, 9).orderByDesc("big_id")
check(
    "between desc",
    [r.big_id for r in wrapper2.sortRows([r for r in rows if wrapper2.toPredicate()(r)])],
    [9, 5, 3],
)

# 7) 真实 Mapper：实体 + Wrapper（orderByAsc + last）
mv = OdsRtSzdnSnapshotFlowAddcodeMapper()
mv.insert(OdsRtSzdnSnapshotFlowAddcode(datauuid="a", big_id=3))
mv.insert(OdsRtSzdnSnapshotFlowAddcode(datauuid="b", big_id=1))
mv.insert(OdsRtSzdnSnapshotFlowAddcode(datauuid="c", big_id=2))
w3 = LambdaQueryWrapper().gt(lambda r: r.big_id, 0)  # Java: .gt(Entity::getBigId, 0)
w3.orderByAsc(lambda r: r.big_id).last("LIMIT 2")
check("mapper wrapper", [r.datauuid for r in mv.selectList(w3)], ["b", "c"])

print("checks:", total[0] - len(failures), "/", total[0])
for f in failures:
    print("FAIL", f)
print("INFRA SMOKE OK" if not failures else "INFRA SMOKE FAILED")
