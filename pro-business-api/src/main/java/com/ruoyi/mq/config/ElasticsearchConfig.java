package com.ruoyi.mq.config;

import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.apache.http.HttpHost;
import org.apache.http.auth.AuthScope;
import org.apache.http.auth.UsernamePasswordCredentials;
import org.apache.http.impl.client.BasicCredentialsProvider;
import org.elasticsearch.client.RestClient;
import org.elasticsearch.client.RestClientBuilder;
import org.elasticsearch.client.RestHighLevelClient;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.StringUtils;

/**
 * Elasticsearch配置类
 * 配置ES客户端连接信息
 */
@Slf4j
@Data
@Configuration
@ConfigurationProperties(prefix = "elasticsearch")
public class ElasticsearchConfig {

    /**
     * ES主机地址
     */
    private String host = "localhost";

    /**
     * ES端口
     */
    private int port = 9200;

    /**
     * 连接协议（http/https）
     */
    private String scheme = "http";

    /**
     * 用户名（可选）
     */
    private String username;

    /**
     * 密码（可选）
     */
    private String password;

    /**
     * 连接超时时间（毫秒）
     */
    private int connectionTimeout = 30000;

    /**
     * Socket超时时间（毫秒）
     */
    private int socketTimeout = 30000;

    /**
     * 创建ES高级客户端Bean
     * 
     * @return RestHighLevelClient实例
     */
    @Bean
    public RestHighLevelClient restHighLevelClient() {
        log.info("[ES配置] 初始化ES客户端, host={}, port={}, scheme={}, auth={}",
                host, port, scheme, StringUtils.hasText(username) ? "basic" : "none");

        RestClientBuilder builder = RestClient.builder(new HttpHost(host, port, scheme))
                .setRequestConfigCallback(requestConfigBuilder ->
                        requestConfigBuilder
                                .setConnectTimeout(connectionTimeout)
                                .setSocketTimeout(socketTimeout));

        // 配置了账号密码时启用 Basic Auth，使 application.yml 中的账号真正生效
        if (StringUtils.hasText(username)) {
            BasicCredentialsProvider credentialsProvider = new BasicCredentialsProvider();
            credentialsProvider.setCredentials(
                    AuthScope.ANY,
                    new UsernamePasswordCredentials(username, password == null ? "" : password));
            builder.setHttpClientConfigCallback(httpClientBuilder ->
                    httpClientBuilder.setDefaultCredentialsProvider(credentialsProvider));
        }

        RestHighLevelClient client = new RestHighLevelClient(builder);

        // 测试连接
        try {
            client.ping(org.elasticsearch.client.RequestOptions.DEFAULT);
            log.info("[ES配置] ES客户端连接成功");
        } catch (Exception e) {
            log.warn("[ES配置] ES连接测试失败, error={}", e.getMessage());
        }

        return client;
    }
}
