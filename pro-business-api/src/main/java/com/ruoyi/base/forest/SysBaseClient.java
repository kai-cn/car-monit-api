package com.ruoyi.base.forest;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.domain.SuspiciousCarVO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * 可疑车辆同步客户端（V3 native 适配）。
 *
 * <p>原实现使用 Forest 的 {@code HttpSysUtilApiService}。Forest 1.8 依赖运行期
 * 注解扫描 + 动态代理，未提供 GraalVM reachability metadata，在 native image
 * 下无法创建客户端 bean（启动报 {@code required a bean of type
 * 'com.ruoyi.base.forest.HttpSysUtilApiService' that could not be found}）。
 *
 * <p>此处用 Spring Framework 自带的 {@link RestClient} 复刻同一请求：
 * {@code POST {sysbaseUrl}/manager/suspicious/syncSuspiciousCarTask}，JSON 报文，
 * 返回值仍用 fastjson2 解析，保持与原实现的报文格式和返回类型一致。
 */
@Component
public class SysBaseClient {

    private static final Logger log = LoggerFactory.getLogger(SysBaseClient.class);

    private static final String SYNC_PATH = "/manager/suspicious/syncSuspiciousCarTask";

    private final RestClient restClient;

    public SysBaseClient(@Value("${sysbaseUrl:}") String sysbaseUrl) {
        String base = sysbaseUrl == null ? "" : sysbaseUrl.trim();
        if (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        // 不强依赖 RestClientAutoConfiguration 提供的 Builder（native/AOT 下不一定存在），
        // 直接构建实例，行为一致且零额外 bean 依赖。
        this.restClient = RestClient.builder().baseUrl(base).build();
        log.info("[sysbase] RestClient 初始化，baseUrl={}", base);
    }

    /**
     * 同步可疑车辆任务，语义与 Forest 版本一致：JSON 出参、失败抛出异常由调用方处理。
     */
    public JSONObject syncSuspiciousCarTask(SuspiciousCarVO suspiciousCarVO) {
        String payload = JSON.toJSONString(suspiciousCarVO);
        String response = restClient.post()
                .uri(SYNC_PATH)
                .contentType(MediaType.APPLICATION_JSON)
                .body(payload)
                .retrieve()
                .body(String.class);
        return response == null || response.isEmpty() ? new JSONObject() : JSONObject.parseObject(response);
    }
}
