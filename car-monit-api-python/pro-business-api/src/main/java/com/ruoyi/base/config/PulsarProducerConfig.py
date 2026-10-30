# -*- coding: utf-8 -*-
"""com.ruoyi.base.config.PulsarProducerConfig

源文件：pro-business-api/src/main/java/com/ruoyi/base/config/PulsarProducerConfig.java

【注意】原 Java 文件**只有一行**：
    package com.ruoyi.base.config;

即——**该文件里没有任何类/接口/枚举**（全文件仅 package 声明 + 换行，共 1 行）。
大概率是遗留的占位文件：Pulsar 生产者的真实配置写在
``PulsarProducerService``（直接读 ``spring.pulsar.*`` 并自建 Producer）。

【Java→Python】处理方式
1) 为保持“目录结构 1:1”和“文件 1:1”，仍然生成同名 .py 文件，但不定义任何类，
   只写本说明 —— 这样 ``refactor/`` 下的文件树与原工程完全一致。
2) 若强行生成一个空类 ``class PulsarProducerConfig: pass``，会凭空多出一个
   Java 里不存在的符号（import 它就会“看起来可用”），反而破坏 1:1 语义，
   因此这里刻意**不定义类**。
3) Java 的 package 声明 → Python 的“所在目录即包”（PEP 420 命名空间包），
   无需任何语句；文件名即模块名，import 路径为
   ``com.ruoyi.base.config.PulsarProducerConfig``。
"""
from __future__ import annotations

__all__: list = []
