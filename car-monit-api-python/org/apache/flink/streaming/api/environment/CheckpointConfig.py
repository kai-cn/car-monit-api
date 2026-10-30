# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.environment.CheckpointConfig

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.environment.CheckpointConfig``。
本工程用法（VehicleTrackFlinkJob.main 步骤 1）：
    env.getCheckpointConfig().setCheckpointTimeout(600000);
    env.getCheckpointConfig().setMaxConcurrentCheckpoints(1);
    env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30000);

【Java→Python】关键差异
1) Java 的 ``setXxx`` 返回 void；替身**返回 self**，以便链式断言，
   但业务代码仍按 Java 写法逐行调用（返回值被丢弃），行为完全一致。
2) Java 里 CheckpointConfig 由 ``StreamExecutionEnvironment`` 内部创建、
   通过 ``getCheckpointConfig()`` 暴露，不能自行 new 后设置给它；
   替身保持同样的持有关系（env 构造时创建一份）。
3) 只实现本工程用到的 3 个 setter；``setCheckpointingMode`` 由
   ``env.enableCheckpointing(interval, mode)`` 内部写入，这里保留字段。
"""
from __future__ import annotations

from typing import Optional

__all__ = ["CheckpointConfig"]


class CheckpointConfig(object):
    """``CheckpointConfig`` 的替身（仅保存配置，不做真实检查点）。"""

    #: Java 默认值：10 分钟
    DEFAULT_CHECKPOINT_TIMEOUT = 10 * 60 * 1000
    #: Java 默认值：1
    DEFAULT_MAX_CONCURRENT_CHECKPOINTS = 1
    #: Java 默认值：0
    DEFAULT_MIN_PAUSE_BETWEEN_CHECKPOINTS = 0

    def __init__(self) -> None:
        self._checkpoint_timeout = CheckpointConfig.DEFAULT_CHECKPOINT_TIMEOUT
        self._max_concurrent_checkpoints = \
            CheckpointConfig.DEFAULT_MAX_CONCURRENT_CHECKPOINTS
        self._min_pause_between_checkpoints = \
            CheckpointConfig.DEFAULT_MIN_PAUSE_BETWEEN_CHECKPOINTS
        #: 由 env.enableCheckpointing(interval, mode) 写入
        self._checkpointing_mode: Optional[str] = None

    # ------------------------------------------------------------------ setter
    def setCheckpointTimeout(self, checkpoint_timeout: int) -> "CheckpointConfig":
        """对应 ``setCheckpointTimeout(long)``：单位毫秒。"""
        self._checkpoint_timeout = int(checkpoint_timeout)
        return self

    def setMaxConcurrentCheckpoints(self,
                                    max_concurrent_checkpoints: int) -> "CheckpointConfig":
        """对应 ``setMaxConcurrentCheckpoints(int)``。"""
        self._max_concurrent_checkpoints = int(max_concurrent_checkpoints)
        return self

    def setMinPauseBetweenCheckpoints(self,
                                      min_pause_between_checkpoints: int) -> "CheckpointConfig":
        """对应 ``setMinPauseBetweenCheckpoints(long)``：单位毫秒。"""
        self._min_pause_between_checkpoints = int(min_pause_between_checkpoints)
        return self

    # ------------------------------------------------------------------ getter
    def getCheckpointTimeout(self) -> int:
        return self._checkpoint_timeout

    def getMaxConcurrentCheckpoints(self) -> int:
        return self._max_concurrent_checkpoints

    def getMinPauseBetweenCheckpoints(self) -> int:
        return self._min_pause_between_checkpoints

    def getCheckpointingMode(self) -> Optional[str]:
        return self._checkpointing_mode

    def __repr__(self) -> str:
        return ("CheckpointConfig(timeout=%d, maxConcurrent=%d, minPause=%d, "
                "mode=%r)" % (self._checkpoint_timeout,
                              self._max_concurrent_checkpoints,
                              self._min_pause_between_checkpoints,
                              self._checkpointing_mode))
