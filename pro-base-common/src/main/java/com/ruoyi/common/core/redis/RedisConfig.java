package com.ruoyi.common.core.redis;


import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "rediscluster")
public class RedisConfig  {


    private  String clusterNodes;

}
