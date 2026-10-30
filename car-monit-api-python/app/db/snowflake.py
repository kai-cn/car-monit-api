# -*- coding: utf-8 -*-
"""MyBatis-Plus ``IdType.ASSIGN_ID`` generator.

Migrated from: com.baomidou.mybatisplus.core.toolkit.Sequence
                (used by ``IdType.ASSIGN_ID`` in ``global-config.db-config``)

The algorithm is the classic Twitter snowflake MP ships:

    sign | 41 bit timestamp | 5 bit datacenter | 5 bit worker | 12 bit sequence
    epoch = 1288834974657 (2010-11-04T01:42:54.657Z)

``ASSIGN_UUID`` is not generated here: it is ``UUID.randomUUID()`` without
dashes (32 hex chars), which the original MyBatis-Plus ``IdentifierGenerator``
also produces.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Optional

__all__ = ["Sequence", "next_id", "assign_uuid"]


class Sequence:
    """``com.baomidou.mybatisplus.core.toolkit.Sequence`` equivalent."""

    TWEPOCH = 1_288_834_974_657
    WORKER_ID_BITS = 5
    DATACENTER_ID_BITS = 5
    SEQUENCE_BITS = 12

    MAX_WORKER_ID = ~(-1 << WORKER_ID_BITS)          # 31
    MAX_DATACENTER_ID = ~(-1 << DATACENTER_ID_BITS)  # 31
    SEQUENCE_MASK = ~(-1 << SEQUENCE_BITS)           # 4095

    WORKER_ID_SHIFT = SEQUENCE_BITS                  # 12
    DATACENTER_ID_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS  # 17
    TIMESTAMP_LEFT_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS + DATACENTER_ID_BITS  # 22

    def __init__(self, worker_id: Optional[int] = None, datacenter_id: Optional[int] = None) -> None:
        self.datacenter_id = (datacenter_id if datacenter_id is not None else _default_datacenter_id()) \
            & self.MAX_DATACENTER_ID
        self.worker_id = (worker_id if worker_id is not None else _default_worker_id(self.datacenter_id)) \
            & self.MAX_WORKER_ID
        self._sequence = 0
        self._last_timestamp = -1
        self._lock = threading.Lock()

    def nextId(self) -> int:  # noqa: N802 - Java method name kept for traceability
        with self._lock:
            timestamp = _current_millis()
            if timestamp < self._last_timestamp:
                # MP: throw new RuntimeException("Clock moved backwards...")
                raise RuntimeError(
                    f"Clock moved backwards. Refusing to generate id for "
                    f"{self._last_timestamp - timestamp} milliseconds"
                )
            if timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & self.SEQUENCE_MASK
                if self._sequence == 0:
                    timestamp = self._til_next_millis(self._last_timestamp)
            else:
                self._sequence = 0
            self._last_timestamp = timestamp
            return (
                ((timestamp - self.TWEPOCH) << self.TIMESTAMP_LEFT_SHIFT)
                | (self.datacenter_id << self.DATACENTER_ID_SHIFT)
                | (self.worker_id << self.WORKER_ID_SHIFT)
                | self._sequence
            )

    def _til_next_millis(self, last_timestamp: int) -> int:
        timestamp = _current_millis()
        while timestamp <= last_timestamp:
            timestamp = _current_millis()
        return timestamp


def _current_millis() -> int:
    return int(time.time() * 1000)


def _default_datacenter_id() -> int:
    """MP derives it from the last MAC bytes; ``uuid.getnode()`` is the same source."""
    node = uuid.getnode()
    value = ((node >> 8) & 0xFF) | (((node >> 16) & 0xFF) << 8)
    return (value >> 6) % 32


def _default_worker_id(datacenter_id: int) -> int:
    """MP: hash(datacenterId + pid) % 32 -- keeps ids unique across processes."""
    seed = f"{datacenter_id}{os.getpid()}"
    return (hash(seed) & 0x7FFFFFFF) % 32


_default_sequence = Sequence()


def next_id() -> int:
    """``IdType.ASSIGN_ID`` -> 64-bit long."""
    return _default_sequence.nextId()


def assign_uuid() -> str:
    """``IdType.ASSIGN_UUID`` -> ``UUID.randomUUID().toString().replace("-", "")``."""
    return uuid.uuid4().hex
