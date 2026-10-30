# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.environment.StreamExecutionEnvironment

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.environment.StreamExecutionEnvironment``。
本工程用法（VehicleTrackFlinkJob.main 步骤 1 / 步骤 7）：
    StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
    env.enableCheckpointing(60000, CheckpointingMode.EXACTLY_ONCE);
    env.getCheckpointConfig().setCheckpointTimeout(600000);
    ...
    env.execute("车辆轨迹实时处理 Job");

【Java→Python】关键差异（**最关键的一条：没有集群**）
1) ``getExecutionEnvironment()`` 在 Java 里会按运行上下文返回
   Local / Remote / Yarn 环境，并**自动探测**  ``flink-conf.yaml``；
   Python 替身永远返回一个本地对象（不做任何探测）。
2) ``execute(String jobName)`` 在 Java 里是**阻塞**的：提交 DAG、启动
   Source 线程、直到作业被取消才返回 ``JobExecutionResult``。
   替身**不提交集群、不启动 Source**，只做三件事：
       a) 记录 jobName（供断言）；
       b) 打一条日志说明“替身不真正执行”；
       c) 遍历所有已登记的 ``DataStreamSink``，用 ``DataStream._values()``
          **同步拉取**数据并调用 ``SinkFunction.invoke``。
   由于 source 流没有真实数据（见 DataStream 差异说明第 2 条），
   默认情况下``execute`` 不会产出任何元素，**不会**因为
   ``DictionarySourceFunction`` 的 ``while`` 死循环而挂住。
3) ``execute()`` 的返回值在 Java 是 ``JobExecutionResult``；替身返回
   ``list``（本轮真正流过 Sink 的元素），纯粹为测试方便。
4) 每次 ``execute`` 都幂等：重复调用只是再次拉取一遍数据，
   不会产生“作业重复提交”的概念。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from org.apache.flink.streaming.api.datastream.DataStream import DataStream
from org.apache.flink.streaming.api.environment.CheckpointConfig import (
    CheckpointConfig,
)

__all__ = ["StreamExecutionEnvironment"]

log = logging.getLogger(__name__)


class StreamExecutionEnvironment(object):
    """``StreamExecutionEnvironment`` 的替身（本地惰性流水线）。"""

    def __init__(self) -> None:
        self._checkpoint_interval: int = -1
        self._checkpointing_mode: Optional[str] = None
        self._checkpoint_config = CheckpointConfig()
        #: 已登记的数据源（Java 的 SourceTransformation）
        self._sources: List[Any] = []
        #: 已登记的 Sink 节点（DataStreamSink 构造时自动加入）
        self._sink_streams: List[Any] = []
        self._parallelism = 1
        self._job_name: Optional[str] = None
        self._executed = False

    # ------------------------------------------------------------------ 环境
    @staticmethod
    def getExecutionEnvironment() -> "StreamExecutionEnvironment":
        """对应 ``getExecutionEnvironment()``：每次调用返回新的本地环境。"""
        return StreamExecutionEnvironment()

    # ------------------------------------------------------------------ 数据源
    def addSource(self, source: Any) -> DataStream:
        """对应 ``addSource(SourceFunction<T>)``。"""
        self._sources.append(source)
        stream = DataStream(self)
        # 【Java→Python】标记为 Source 流：_values() 不自动消费（见 DataStream）
        stream._source = source
        return stream

    # ------------------------------------------------------------------ 检查点
    def enableCheckpointing(self, interval: int,
                            mode: Optional[str] = None) -> "StreamExecutionEnvironment":
        """对应 ``enableCheckpointing(long)`` / ``enableCheckpointing(long, CheckpointingMode)``。"""
        self._checkpoint_interval = int(interval)
        if mode is not None:
            self._checkpointing_mode = mode
            self._checkpoint_config._checkpointing_mode = mode
        return self

    def getCheckpointConfig(self) -> CheckpointConfig:
        """对应 ``getCheckpointConfig()``。"""
        return self._checkpoint_config

    # ------------------------------------------------------------------ 并行度
    def setParallelism(self, parallelism: int) -> "StreamExecutionEnvironment":
        self._parallelism = int(parallelism)
        return self

    def getParallelism(self) -> int:
        return self._parallelism

    # ------------------------------------------------------------------ 执行
    def execute(self, job_name: Optional[str] = None) -> List[Any]:
        """对应 ``execute(String jobName)``：替身只跑本地 Sink 流水线。"""
        self._job_name = job_name
        self._executed = True
        log.info("[Flink替身] execute(jobName=%s) 被调用：不提交集群，"
                 "仅按 sink 同步拉取上游数据", job_name)

        emitted: List[Any] = []
        for sink_stream in self._sink_streams:
            emitted.extend(sink_stream.emit())
        return emitted

    def getJobName(self) -> Optional[str]:
        """Java 无公开 getter；替身用于断言 execute 传入的作业名。"""
        return self._job_name

    def isExecuted(self) -> bool:
        """Java 无此方法；替身用于断言 execute 是否被调用。"""
        return self._executed

    def __repr__(self) -> str:
        return ("StreamExecutionEnvironment(checkpointInterval=%d, "
                "sources=%d, sinks=%d, jobName=%r)" %
                (self._checkpoint_interval, len(self._sources),
                 len(self._sink_streams), self._job_name))
