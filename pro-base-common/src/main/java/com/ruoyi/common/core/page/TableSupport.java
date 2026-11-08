package com.ruoyi.common.core.page;

import com.ruoyi.common.core.text.Convert;
import com.ruoyi.common.utils.ServletUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 表格数据处理
 * 
 * @author ruoyi
 */
public class TableSupport
{
    private static final Logger log = LoggerFactory.getLogger(TableSupport.class);

    /**
     * 每页最大记录数，默认 2000（可通过 page.max-size 配置，由 PageLimitConfigurer 注入）
     */
    private static volatile int maxPageSize = 2000;

    /**
     * 默认每页记录数
     */
    private static final int DEFAULT_PAGE_SIZE = 10;

    public static void setMaxPageSize(int maxPageSize)
    {
        if (maxPageSize > 0)
        {
            TableSupport.maxPageSize = maxPageSize;
        }
    }

    public static int getMaxPageSize()
    {
        return maxPageSize;
    }

    /**
     * 当前记录起始索引
     */
    public static final String PAGE_NUM = "pageNum";

    /**
     * 每页显示记录数
     */
    public static final String PAGE_SIZE = "pageSize";

    /**
     * 排序列
     */
    public static final String ORDER_BY_COLUMN = "orderByColumn";

    /**
     * 排序的方向 "desc" 或者 "asc".
     */
    public static final String IS_ASC = "isAsc";

    /**
     * 分页参数合理化
     */
    public static final String REASONABLE = "reasonable";

    /**
     * 封装分页对象
     */
    public static PageDomain getPageDomain()
    {
        PageDomain pageDomain = new PageDomain();
        pageDomain.setPageNum(Convert.toInt(ServletUtils.getParameter(PAGE_NUM), 1));
        int pageSize = Convert.toInt(ServletUtils.getParameter(PAGE_SIZE), DEFAULT_PAGE_SIZE);
        if (pageSize > maxPageSize)
        {
            log.warn("请求 pageSize={} 超过上限 {}，已截断；uri={}", pageSize, maxPageSize,
                    ServletUtils.getRequest() == null ? "" : ServletUtils.getRequest().getRequestURI());
            pageSize = maxPageSize;
        }
        if (pageSize <= 0)
        {
            pageSize = DEFAULT_PAGE_SIZE;
        }
        pageDomain.setPageSize(pageSize);
        pageDomain.setOrderByColumn(ServletUtils.getParameter(ORDER_BY_COLUMN));
        pageDomain.setIsAsc(ServletUtils.getParameter(IS_ASC));
        pageDomain.setReasonable(ServletUtils.getParameterToBool(REASONABLE));
        return pageDomain;
    }

    public static PageDomain buildPageRequest()
    {
        return getPageDomain();
    }
}
