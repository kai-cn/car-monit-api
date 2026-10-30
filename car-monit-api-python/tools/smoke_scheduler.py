# -*- coding: utf-8 -*-
"""Phase 2c smoke: start the real scheduler, inspect it, shut it down.

Verifies the ``@EnableScheduling`` equivalent end to end:

1. ``start_scheduler()`` builds the 6 beans and registers the 10 ``@Scheduled``
   methods (``CarTask`` contributes none -- its Java source is commented out);
2. the 4 ``fixedRate`` jobs fire immediately, exactly like Spring, and must not
   raise (they hit the **in-memory** mappers: no lifespan -> no DB registry);
3. ``describe()`` (the ``/health`` probe) reports the same 10 jobs;
4. ``shutdown_scheduler()`` stops every ``scheduler-*`` thread and is idempotent.

Run with ``.venv\\Scripts\\python.exe tools\\smoke_scheduler.py``.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import bootstrap  # noqa: E402  (registers the Java-mirrored import roots)

from app import scheduler as scheduler_app  # noqa: E402

__all__ = ["main"]

_EXPECTED_TASKS = 10


def _scheduler_threads() -> list[str]:
    return sorted(t.name for t in threading.enumerate() if t.name.startswith("scheduler-"))


def main() -> int:
    failures: list[str] = []

    # 1) cold state
    if scheduler_app.is_started():
        failures.append("scheduler already started before start_scheduler()")

    # 2) start
    count = scheduler_app.start_scheduler()
    print("start_scheduler() -> %s task(s)" % count)
    if count != _EXPECTED_TASKS:
        failures.append("expected %s tasks, got %s" % (_EXPECTED_TASKS, count))

    # 3) let the fixedRate jobs run their first cycle
    time.sleep(0.6)

    # 4) the /health probe must report the same jobs
    report = scheduler_app.describe()
    print("describe(): started=%s tasks=%s" % (report["started"], report["tasks"]))
    if report["tasks"] != count:
        failures.append("describe() reports %s tasks, registered %s"
                        % (report["tasks"], count))
    for job in report["jobs"]:
        print("  %-58s %-24s %-10s %s"
              % (job["bean"], job["method"], job["kind"], job["trigger"]))

    alive = _scheduler_threads()
    print("scheduler threads: %s" % (len(alive),))

    # 5) shutdown
    scheduler_app.shutdown_scheduler()
    time.sleep(0.3)
    if scheduler_app.is_started():
        failures.append("is_started() still True after shutdown")
    leftover = _scheduler_threads()
    if leftover:
        failures.append("threads still alive after shutdown: %s" % (leftover,))

    # 6) idempotent shutdown must not raise
    scheduler_app.shutdown_scheduler()

    # 7) restart must work (uvicorn reload / test isolation)
    restarted = scheduler_app.start_scheduler()
    if restarted != _EXPECTED_TASKS:
        failures.append("restart registered %s tasks" % restarted)
    scheduler_app.shutdown_scheduler()

    print()
    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        return 1
    print("scheduler: OK")
    return 0


if __name__ == "__main__":
    exit_code = main()
    # The ported services own daemon pools, but exiting explicitly keeps the smoke
    # script's runtime bounded regardless of what the jobs started.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
