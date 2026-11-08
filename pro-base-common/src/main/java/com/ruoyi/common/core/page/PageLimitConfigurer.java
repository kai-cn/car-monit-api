package com.ruoyi.common.core.page;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import javax.annotation.PostConstruct;

/**
 * 分页上限配置注入：把 page.max-size 写入静态的 TableSupport，
 * 供静态分页方法使用（默认 2000，属于较大的安全值）。
 */
@Configuration
public class PageLimitConfigurer {

    @Value("${page.max-size:2000}")
    private int maxPageSize;

    @PostConstruct
    public void init() {
        TableSupport.setMaxPageSize(maxPageSize);
    }
}
