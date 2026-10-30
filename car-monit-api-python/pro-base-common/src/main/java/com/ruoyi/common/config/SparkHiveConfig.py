# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.SparkHiveConfig

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/SparkHiveConfig.java

【Java→Python】重要说明：本文件在 Java 源码中**整体被 /* ... */ 注释掉**，
因此不会参与编译、不会创建任何 Bean。为保证“一比一像素级重构”，
Python 侧同样保持“不生效”：代码全部保留在下面这段注释块中，
模块可被 import（文件存在、路径与包名一致），但不会产生任何副作用。

若要真正启用 Spark Hive 支持，需额外安装 pyspark（Java 侧需引入 spark-sql 依赖），
并把 ``hive.metastore.uris`` 从配置中心/application.yml 注入到构造参数。

--- 原 Java 代码（被注释） -------------------------------------------------
@Configuration
public class SparkHiveConfig {

    @Value("${hive.metastore.uris}")
    private String hiveMetastoreUris;

    @Bean
    public SparkSession sparkSession() {
        return SparkSession.builder()
                .appName("Spark Hive Example")
                .config("hive.metastore.uris", hiveMetastoreUris)
                .enableHiveSupport()
                .getOrCreate();
    }
}

--- 对应的 Python 写法（同样不启用，仅作对照保留） --------------------------
class SparkHiveConfig:
    '''【Java→Python】
    @Configuration            → 普通类（无容器注册）
    @Value("${...}")          → 构造参数 hive_metastore_uris
    @Bean SparkSession        → 工厂方法返回 pyspark.sql.SparkSession
    '''
    def __init__(self, hive_metastore_uris: str) -> None:
        self.hiveMetastoreUris = hive_metastore_uris

    def sparkSession(self):
        from pyspark.sql import SparkSession
        return (SparkSession.builder
                .appName("Spark Hive Example")
                .config("hive.metastore.uris", self.hiveMetastoreUris)
                .enableHiveSupport()
                .getOrCreate())
--------------------------------------------------------------------------
"""
from __future__ import annotations

# 与 Java 一致：类体不落地，仅保留占位符便于 `from ... import SparkHiveConfig` 不报错。
# 【Java→Python】Python 的模块可以只写文档字符串；这里显式给出 None 说明“无实现”。
SparkHiveConfig = None
