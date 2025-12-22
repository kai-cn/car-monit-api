/*
package com.ruoyi.common.config;

import org.apache.spark.sql.SparkSession;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

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
*/
