# -*- coding: utf-8 -*-
"""t09d 冒烟测试：task 层 3 个类。

覆盖要点
1) CarTask：Java 源整文件被块注释 → Python 模块**不定义** CarTask 类（与 Java 一致）。
2) TrackTask：
   - 9 个注入字段与 Java 同名；
   - syncCurrentTrack → sysUtilService.syncTrack(new CarParaVO())；
   - syncBaseInfo → 7 个基础信息同步调用，顺序与 Java 一致；
   - syncHistroyTrack → 车牌去重合并（uuid 相同不重复追加）、写回 historyKey、
     写回 timeKey（SimpleDateFormat 格式化时间串）、缓存无同步时间时 flag=bannian。
3) DataFlowTask：
   - processPendingQueue → 调用 dataFlowService.processPendingQueue()；
   - 服务异常被捕获（不向外抛，等价 Java 的空 catch 后 log）；
   - syncGantryCaptureData 的 try 体只有注释（Python 用 pass 占位），无任何服务调用；
   - snapshotFlowService 注入后未使用（原工程如此）。

运行：python refactor/_smoke_t09d.py
"""
from __future__ import annotations

import importlib
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for _path in (
    ROOT,
    os.path.join(ROOT, "pro-base-common", "src", "main", "java"),
    os.path.join(ROOT, "pro-business-api", "src", "main", "java"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

PASS = 0
FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{label} {detail}")
        print(f"  FAIL  {label} {detail}")


def check_eq(label: str, actual, expected) -> None:
    check(label, actual == expected, f"(actual={actual!r}, expected={expected!r})")


class _AnyStub:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __getattr__(self, name: str):
        def _call(*args, **kwargs):
            self.calls.append((name, args))
            return None

        return _call


class _RedisStub:
    """按 key 返回预置值，并记录 setCacheObject。"""

    def __init__(self, mapping: dict | None = None) -> None:
        self.mapping = mapping or {}
        self.sets: list[tuple] = []
        self.gets: list[str] = []

    def getCacheObject(self, key):
        self.gets.append(key)
        return self.mapping.get(key)

    def setCacheObject(self, key, value):
        self.sets.append((key, value))

    def set(self, key):
        return [item for item in self.sets if item[0] == key][-1][1]


def test_car_task() -> None:
    print("[CarTask]")
    module = importlib.import_module("com.ruoyi.base.task.CarTask")
    check_eq("CarTask.__all__ 为空（整文件被注释）", list(module.__all__), [])
    check("CarTask 模块不定义 CarTask 类", not hasattr(module, "CarTask"))


def test_track_task() -> None:
    print("[TrackTask]")
    from com.ruoyi.base.domain.CarParaVO import CarParaVO
    from com.ruoyi.base.domain.CarVO import CarVO
    from com.ruoyi.base.domain.TrailBo import TrailBo
    from com.ruoyi.base.domain.TrailInfo import TrailInfo
    from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
    from com.ruoyi.common.constant.Constants import Constants

    module = importlib.import_module("com.ruoyi.base.task.TrackTask")
    cls = module.TrackTask
    check_eq("TrackTask.__all__", list(module.__all__), ["TrackTask"])

    # ---- 构造器注入字段名与 Java 一致 ----
    stubs = {
        "redisCache": _RedisStub(),
        "odsSzdnGantryIpService": _AnyStub(),
        "odsSzdnTollStationIpService": _AnyStub(),
        "sysUtilService": _AnyStub(),
        "odsSzdnGantryService": _AnyStub(),
        "zdataLocationDictService": _AnyStub(),
        "dwdLcztFwqjcxxService": _AnyStub(),
        "sectionService": _AnyStub(),
        "odsSzdnTollService": _AnyStub(),
    }
    controller = cls(**stubs)
    for name, stub in stubs.items():
        check_eq(f"TrackTask.{name} 注入", getattr(controller, name) is stub, True)

    # ---- syncCurrentTrack ----
    sys_util = stubs["sysUtilService"]
    controller.syncCurrentTrack()
    check_eq("syncCurrentTrack 调用 syncTrack", sys_util.calls[-1][0], "syncTrack")
    check("syncCurrentTrack 传入 CarParaVO",
          isinstance(sys_util.calls[-1][1][0], CarParaVO))

    # ---- syncBaseInfo ----
    controller.syncBaseInfo()
    order = [
        stubs["odsSzdnGantryService"].calls[-1][0],
        stubs["odsSzdnGantryIpService"].calls[-1][0],
        stubs["odsSzdnTollStationIpService"].calls[-1][0],
        stubs["zdataLocationDictService"].calls[-1][0],
        stubs["dwdLcztFwqjcxxService"].calls[-1][0],
        stubs["sectionService"].calls[-1][0],
        stubs["odsSzdnTollService"].calls[-1][0],
    ]
    check_eq("syncBaseInfo 7 个调用顺序", order, [
        "saveGantryRedis", "updateRedis", "updateRedis",
        "updateRedis", "updateRedis", "updateRedis", "updateRedis"])

    # ---- syncHistroyTrack ----
    def _trail(uuid: str) -> TrailInfo:
        tracks = ZdataTrailTracks()
        tracks.setUuid(uuid)
        info = TrailInfo()
        info.setTracks(tracks)
        info.setTrailList([TrailBo()])
        return info

    new_trail = _trail("U1")
    old_dup = _trail("U1")      # 与 newList 的 uuid 相同 → 不应重复追加
    old_new = _trail("U2")      # 新 uuid → 追加

    received: dict = {}

    def _car_track_query(carParaVO):
        received["vo"] = carParaVO
        return [new_trail]

    sys_util.carTrackQuery = _car_track_query
    car_vo = CarVO()
    car_vo.setCarNo("赣A1")
    redis = _RedisStub({
        Constants.car_list_jc: [car_vo],
        Constants.car_sync_time + "赣A1": "",
        Constants.car_history_trail + "赣A1": [old_dup, old_new],
    })
    controller.redisCache = redis

    controller.syncHistroyTrack()

    history = redis.set(Constants.car_history_trail + "赣A1")
    check_eq("syncHistroyTrack 合并后条数（新1 + 旧去重1）", len(history), 2)
    check("syncHistroyTrack 保留新轨迹", history[0] is new_trail)
    # TrailInfo 是 dataclass，== 按字段比较（old_dup 与 new_trail 字段相同），故用 is 判等
    check("syncHistroyTrack 跳过重复 uuid", all(item is not old_dup for item in history))
    check("syncHistroyTrack 追加新 uuid 的旧轨迹", history[1] is old_new)

    formatted = redis.set(Constants.car_sync_time + "赣A1")
    check_eq("syncHistroyTrack 写回时间串格式", len(formatted), len("2026-10-21 10:00:00"))
    check_eq("syncHistroyTrack 时间串分隔符", formatted[10], " ")

    # 缓存里没有同步时间 → flag=bannian（半年）
    check_eq("syncHistroyTrack 调用 carTrackQuery", "vo" in received, True)
    check_eq("syncHistroyTrack 传入车牌", received["vo"].getCarNo(), "赣A1")
    check_eq("syncHistroyTrack 默认查询半年 flag", received["vo"].getFlag(), "bannian")

    # ---- ClassCastException：缓存里不是 List ----
    bad_redis = _RedisStub({Constants.car_list_jc: "not-a-list"})
    controller.redisCache = bad_redis
    try:
        controller.syncHistroyTrack()
        check("syncHistroyTrack 非 List → TypeError", False)
    except TypeError as exc:
        check("syncHistroyTrack 非 List → TypeError", "ClassCastException" in str(exc))


def test_data_flow_task() -> None:
    print("[DataFlowTask]")
    module = importlib.import_module("com.ruoyi.base.task.DataFlowTask")
    cls = module.DataFlowTask
    check_eq("DataFlowTask.__all__", list(module.__all__), ["DataFlowTask"])

    class _DataFlowStub:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.error: Exception | None = None

        def processPendingQueue(self):
            self.calls.append("processPendingQueue")
            if self.error is not None:
                raise self.error

    flow = _DataFlowStub()
    snapshot = _AnyStub()
    task = cls(dataFlowService=flow, snapshotFlowService=snapshot)
    check_eq("DataFlowTask.dataFlowService 注入", task.dataFlowService is flow, True)
    check_eq("DataFlowTask.snapshotFlowService 注入", task.snapshotFlowService is snapshot, True)

    task.processPendingQueue()
    check_eq("processPendingQueue 调用服务", flow.calls, ["processPendingQueue"])

    # 服务抛异常 → 被 try/except 吞掉（与 Java 的 catch 后 log 一致）
    flow.error = RuntimeError("queue broken")
    try:
        task.processPendingQueue()
        check("processPendingQueue 吞掉服务异常", True)
    except Exception as exc:  # noqa: BLE001
        check("processPendingQueue 吞掉服务异常", False, f"(raised={exc!r})")

    # syncGantryCaptureData 的 try 体只有注释：不应对任何服务发起调用
    before = (len(flow.calls), len(snapshot.calls))
    task.syncGantryCaptureData()
    check_eq("syncGantryCaptureData 不调用任何服务", (len(flow.calls), len(snapshot.calls)), before)


def main() -> int:
    test_car_task()
    test_track_task()
    test_data_flow_task()

    print()
    print(f"PASS={PASS} FAIL={FAIL}")
    if FAILURES:
        print("失败项：")
        for item in FAILURES:
            print("  - " + item)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
