package com.ruoyi.common.utils;

import com.github.pagehelper.PageHelper;
import com.ruoyi.common.core.page.PageDomain;
import com.ruoyi.common.core.page.TableSupport;
import com.ruoyi.common.utils.sql.SqlUtil;

/**
 * 分页工具类
 * 
 * @author ruoyi
 */
public class PageUtils extends PageHelper
{
    /**
     * 设置请求分页数据
     */
    public static void startPage()
    {
        PageDomain pageDomain = TableSupport.buildPageRequest();
        Integer pageNum = pageDomain.getPageNum();
        Integer pageSize = pageDomain.getPageSize();
        String orderBy = SqlUtil.escapeOrderBySql(pageDomain.getOrderBy());
        Boolean reasonable = pageDomain.getReasonable();
        PageHelper.startPage(pageNum, pageSize, orderBy).setReasonable(reasonable);
    }

    /**
     * 清理分页的线程变量
     */
    public static void clearPage()
    {
        PageHelper.clearPage();
    }

    /**
     * 计算分页偏移量。
     *
     * 使用 long 运算，避免 (pageNum - 1) * pageSize 在 int 下溢出为负数；
     * 结果小于 0 时按 0 处理。
     *
     * @param pageNum 页码（从 1 开始）
     * @param pageSize 每页大小
     * @return 偏移量
     */
    public static long safeFrom(int pageNum, int pageSize)
    {
        long from = ((long) pageNum - 1L) * (long) pageSize;
        return Math.max(0L, from);
    }
}
