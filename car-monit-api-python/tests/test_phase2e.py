# -*- coding: utf-8 -*-
"""Phase 2e: the scheduler (``@EnableScheduling`` equivalent) and its cron engine.

The Java app registers **10** ``@Scheduled`` methods across 6 beans -- ``CarTask``
is commented out in its entirety in the Java source, so javac never sees it and
it registers nothing. These tests cover the four pieces added in this phase:

* ``CronExpression`` / ``CronTrigger``   -- the six-field Spring cron syntax;
* ``ThreadPoolTaskScheduler``            -- repeating schedules survive exceptions;
* ``ScheduledTaskRegistrar``             -- cron registration + idempotent start;
* ``app.scheduler``                      -- bean list, ``plan()``, start/stop.

A source scan keeps the explicit bean list honest: every ``@Scheduled(`` decorator
in the ported tree must appear in ``plan()`` and vice versa.
"""
from __future__ import annotations

import datetime as _dt
import logging
import re
import threading
import time
from typing import Iterator, List, Tuple

import pytest

import bootstrap
from app import scheduler as scheduler_app
from org.springframework.scheduling.annotation.Scheduled import Scheduled
from org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler import ThreadPoolTaskScheduler
from org.springframework.scheduling.config.ScheduledTaskRegistrar import ScheduledTaskRegistrar
from org.springframework.scheduling.support.CronExpression import CronExpression
from org.springframework.scheduling.support.CronTrigger import CronTrigger, TriggerContext

_ANCHOR = _dt.datetime(2026, 10, 22, 10, 0, 0)  # a Thursday


# --------------------------------------------------------------------- cron
@pytest.mark.parametrize("expression, anchor, expected", [
    # the crones actually used by the ported beans
    ("0 0/3 * * * ?", _ANCHOR, _dt.datetime(2026, 10, 22, 10, 3, 0)),
    ("0 */1 * * * ?", _ANCHOR, _dt.datetime(2026, 10, 22, 10, 1, 0)),
    ("0 */5 * * * ?", _ANCHOR, _dt.datetime(2026, 10, 22, 10, 5, 0)),
    ("0 30 2 * * ?", _ANCHOR, _dt.datetime(2026, 10, 23, 2, 30, 0)),
    ("0 0 0 * * ?", _ANCHOR, _dt.datetime(2026, 10, 23, 0, 0, 0)),
    ("0 0 4 * * ?", _ANCHOR, _dt.datetime(2026, 10, 23, 4, 0, 0)),
    # generic syntax: range + step, day-of-month, last day, weekday names
    ("0 0/15 9-17 * * ?", _dt.datetime(2026, 10, 22, 8, 0, 0), _dt.datetime(2026, 10, 22, 9, 0, 0)),
    ("0 0 0 1 * ?", _ANCHOR, _dt.datetime(2026, 11, 1, 0, 0, 0)),
    ("0 0 0 L * ?", _dt.datetime(2026, 2, 10, 0, 0, 0), _dt.datetime(2026, 2, 28, 0, 0, 0)),
    ("0 15 10 ? * MON-FRI", _dt.datetime(2026, 10, 23, 15, 0, 0), _dt.datetime(2026, 10, 26, 10, 15, 0)),
])
def test_cron_expression_next_fire_time(expression: str, anchor: _dt.datetime,
                                        expected: _dt.datetime) -> None:
    assert CronExpression.parse(expression).next_fire_time(anchor) == expected


def test_cron_expression_is_strictly_after_the_anchor() -> None:
    expression = CronExpression.parse("0 0/3 * * * ?")
    assert expression.next_fire_time(_dt.datetime(2026, 10, 22, 10, 3, 0)) \
        == _dt.datetime(2026, 10, 22, 10, 6, 0)


def test_cron_sunday_is_both_zero_and_seven() -> None:
    anchor = _dt.datetime(2026, 10, 22, 10, 0, 0)
    with_zero = CronExpression.parse("0 0 0 ? * 0").next_fire_time(anchor)
    with_seven = CronExpression.parse("0 0 0 ? * 7").next_fire_time(anchor)
    assert with_zero == with_seven == _dt.datetime(2026, 10, 25, 0, 0, 0)


def test_cron_impossible_day_never_fires() -> None:
    # Feb 31 -- Spring's next() returns null after its search window
    assert CronExpression.parse("0 0 0 31 2 ?").next_fire_time(_ANCHOR) is None


@pytest.mark.parametrize("expression, valid", [
    ("0 0 0 * * ?", True),
    ("0 30 2 * * ?", True),
    ("*/5 * * * * *", True),
    ("0 0 0 * *", False),          # five fields -> IllegalArgumentException
    ("0 0 0 * * ? *", False),      # seven fields (Quartz style) is invalid in Spring
    ("0 0 0 * * 8", False),        # day-of-week out of range
    ("0 0 24 * * ?", False),       # hour out of range
    ("0 0 0 * * MON#2", False),    # unsupported Quartz extension
    ("", False),
])
def test_cron_expression_validation(expression: str, valid: bool) -> None:
    assert CronExpression.isValidExpression(expression) is valid


def test_cron_trigger_uses_now_for_the_first_execution() -> None:
    trigger = CronTrigger("0 0/3 * * * ?")
    before = _dt.datetime.now()
    first = trigger.next_execution_time(TriggerContext())
    assert first is not None and first > before
    assert (first.second, first.minute % 3) == (0, 0)


def test_cron_trigger_uses_last_completion_time_afterwards() -> None:
    trigger = CronTrigger(CronExpression.parse("0 0/3 * * * ?"))
    context = TriggerContext()
    context.update(_dt.datetime(2026, 10, 22, 10, 0, 0),
                   _dt.datetime(2026, 10, 22, 10, 0, 0),
                   _dt.datetime(2026, 10, 22, 10, 2, 30))
    assert trigger.next_execution_time(context) == _dt.datetime(2026, 10, 22, 10, 3, 0)


# ------------------------------------------------------------------ registrar
class _RecordingScheduler(object):
    """Minimal ``TaskScheduler`` stand-in that records what was scheduled."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, object]] = []

    def schedule(self, task, start_time=None):
        self.calls.append(("schedule", start_time))
        return None

    def scheduleAtFixedRate(self, task, start_time, period_ms):
        self.calls.append(("fixedRate", period_ms))
        return None

    def scheduleWithFixedDelay(self, task, start_time, delay_ms):
        self.calls.append(("fixedDelay", delay_ms))
        return None


def test_registrar_schedules_cron_tasks_once() -> None:
    registrar = ScheduledTaskRegistrar()
    scheduler = _RecordingScheduler()
    registrar.setTaskScheduler(scheduler)
    registrar.addCronTask(lambda: None, "0 30 2 * * ?")
    registrar.afterPropertiesSet()
    registrar.afterPropertiesSet()  # idempotent: the container refreshes once

    assert [name for name, _ in scheduler.calls] == ["schedule"]
    trigger = scheduler.calls[0][1]
    assert isinstance(trigger, CronTrigger)
    assert trigger.toString() == "0 30 2 * * ?"


def test_registrar_without_scheduler_does_not_run_anything() -> None:
    registrar = ScheduledTaskRegistrar()
    registrar.addCronTask(lambda: None, "0 30 2 * * ?")
    registrar.afterPropertiesSet()  # no TaskScheduler -> nothing happens
    assert registrar.getCronTaskList()


# ------------------------------------------------------------- thread pool
def test_fixed_rate_keeps_running_after_an_exception(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.CRITICAL)
    calls: List[int] = []

    def task() -> None:
        calls.append(1)
        raise RuntimeError("boom")  # Java: LOG_AND_SUPPRESS_ERROR_HANDLER

    pool = ThreadPoolTaskScheduler()
    pool.setThreadNamePrefix("phase2e-rate-")
    pool.initialize()
    pool.scheduleAtFixedRate(task, None, 20)
    time.sleep(0.15)
    pool.shutdown()

    assert len(calls) >= 2


def test_shutdown_stops_the_scheduling_threads() -> None:
    pool = ThreadPoolTaskScheduler()
    pool.setThreadNamePrefix("phase2e-stop-")
    pool.initialize()
    pool.scheduleAtFixedRate(lambda: None, None, 10_000)
    time.sleep(0.05)
    pool.shutdown()

    assert not [t for t in threading.enumerate() if t.name.startswith("phase2e-stop-")]


def test_schedule_with_a_custom_trigger_repeats_and_cancels() -> None:
    calls: List[int] = []

    class _FastTrigger(object):
        def next_execution_time(self, context):
            return _dt.datetime.now() + _dt.timedelta(milliseconds=20)

    pool = ThreadPoolTaskScheduler()
    pool.setThreadNamePrefix("phase2e-trigger-")
    pool.initialize()
    future = pool.schedule(lambda: calls.append(1), _FastTrigger())
    time.sleep(0.15)
    assert len(calls) >= 2
    assert future.cancel() is True
    assert future.cancel() is False       # Java: 已取消再取消返回 false
    settled = len(calls)
    time.sleep(0.1)
    assert len(calls) == settled
    pool.shutdown()


def test_execute_runs_a_one_shot_task() -> None:
    pool = ThreadPoolTaskScheduler()
    pool.setThreadNamePrefix("phase2e-exec-")
    pool.initialize()
    done: List[str] = []
    pool.execute(lambda: done.append("ok"))
    for _ in range(50):
        if done:
            break
        time.sleep(0.01)
    pool.shutdown()
    assert done == ["ok"]


# ------------------------------------------------------------ app.scheduler
class _StubBean(object):
    """A bean that carries both a cron and a fixedRate job (used by start/stop tests)."""

    ticks: List[float] = []

    @Scheduled(fixedRate=40)
    def tick(self) -> None:
        _StubBean.ticks.append(time.monotonic())

    @Scheduled(cron="0 0 3 * * ?")
    def nightly(self) -> None:
        pass


@pytest.fixture()
def clean_scheduler() -> Iterator[None]:
    scheduler_app.shutdown_scheduler()
    yield
    scheduler_app.shutdown_scheduler()


def test_plan_matches_the_java_bean_set() -> None:
    expected = {
        ("TrackTask", "syncBaseInfo"),
        ("TrackTask", "syncCurrentTrack"),
        ("TrackTask", "syncHistroyTrack"),
        ("DataFlowTask", "processPendingQueue"),
        ("DataFlowTask", "syncGantryCaptureData"),
        ("DataLossDetectionService", "scheduledDetection"),
        ("DelayMonitoringService", "generateStatsReport"),
        ("DataReliabilityService", "compensationTask"),
        ("DataReliabilityService", "checkOfflineDevices"),
        ("GaussEsConsistencyService", "scheduledReconcile"),
    }
    actual = {(spec.bean.rsplit(".", 1)[-1], spec.method) for spec in scheduler_app.plan()}
    assert actual == expected
    assert len(scheduler_app.plan()) == 10


def test_plan_keeps_the_original_millisecond_values() -> None:
    """``${detection.interval-minutes:30}000`` is 30 000 ms (= 30 s), not 30 min.

    The Java source has this off-by-a-factor-60 defect; the port must keep it.
    """
    by_method = {spec.method: spec for spec in scheduler_app.plan()}
    assert (by_method["scheduledDetection"].kind, by_method["scheduledDetection"].trigger) \
        == ("fixedRate", "30000")
    assert by_method["scheduledDetection"].java \
        == '@Scheduled(fixedRateString = "${detection.interval-minutes:30}000")'
    assert by_method["compensationTask"].trigger == "60000"
    assert by_method["checkOfflineDevices"].trigger == "300000"
    assert by_method["generateStatsReport"].trigger == "600000"
    assert by_method["scheduledReconcile"].trigger == "0 30 2 * * ?"
    assert by_method["syncCurrentTrack"].trigger == "0 0/3 * * * ?"


def test_car_task_is_absent_because_its_java_source_is_commented_out() -> None:
    assert all("CarTask" not in spec.bean for spec in scheduler_app.plan())


def test_plan_does_not_start_anything(clean_scheduler: None) -> None:
    scheduler_app.plan()
    assert scheduler_app.is_started() is False
    assert scheduler_app.describe()["tasks"] == 0


def test_start_and_shutdown_are_idempotent(clean_scheduler: None) -> None:
    _StubBean.ticks.clear()
    first = scheduler_app.start_scheduler((_StubBean,))
    second = scheduler_app.start_scheduler((_StubBean,))  # second call is a no-op
    assert first == second == 2
    assert scheduler_app.is_started() is True
    assert scheduler_app.describe()["tasks"] == 2

    time.sleep(0.15)
    assert len(_StubBean.ticks) >= 2, "fixedRate job did not run"

    scheduler_app.shutdown_scheduler()
    assert scheduler_app.is_started() is False
    scheduler_app.shutdown_scheduler()  # idempotent
    settled = len(_StubBean.ticks)
    time.sleep(0.1)
    assert len(_StubBean.ticks) == settled, "tasks still running after shutdown"


# ------------------------------------------------------- source consistency
_DECORATOR = re.compile(r"^[ \t]*@Scheduled\(", re.MULTILINE)
_NEXT_DEF = re.compile(r"^[ \t]*def\s+(\w+)", re.MULTILINE)


def _decorated_methods() -> List[Tuple[str, str]]:
    root = bootstrap.ROOT / "pro-business-api" / "src" / "main" / "java"
    found: List[Tuple[str, str]] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _DECORATOR.finditer(text):
            following = _NEXT_DEF.search(text, match.end())
            assert following is not None, "%s: @Scheduled without a following def" % path
            found.append((path.stem, following.group(1)))
    return found


def test_every_decorator_is_registered_and_nothing_else() -> None:
    decorated = sorted(_decorated_methods())
    planned = sorted((spec.bean.rsplit(".", 1)[-1], spec.method)
                     for spec in scheduler_app.plan())
    assert decorated == planned
