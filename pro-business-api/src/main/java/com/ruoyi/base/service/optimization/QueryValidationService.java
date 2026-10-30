package com.ruoyi.base.service.optimization;

import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;

/**
 * ====================================================================
 * 查询参数校验服务
 * ====================================================================
 *
 * 核心职责：
 *   在查询到达数据库/ES之前，对参数进行强制校验，防止以下灾难性场景：
 *
 *   1. 无时间范围的全表扫描 —— 8亿行数据会导致数据库雪崩
 *   2. 深分页 OFFSET > 10000 —— PostgreSQL 需要扫描并丢弃前N行，越深越慢
 *   3. 超大时间范围（>1年） —— 超出业务需求，浪费资源
 *   4. 超大分页大小（>500） —— 单页返回太多数据，内存和序列化压力大
 *
 * 校验规则（可在 application.yml 中配置）：
 *   - 时间范围必填
 *   - 最大时间范围：365 天
 *   - 最大深分页偏移：10000
 *   - 最大每页大小：500
 *
 * @author car-monit-api-optimization
 */
@Slf4j
@Service
public class QueryValidationService {

    /**
     * 允许的最大时间范围（天），默认 365 天（1年）
     * 超过此范围直接拒绝，提示用户缩小查询范围
     */
    @Value("${optimization.query.max-time-range-days:365}")
    private int maxTimeRangeDays;

    /**
     * 允许的最大深分页偏移量，默认 10000
     *
     * 为什么限制深分页：
     *   LIMIT 20 OFFSET 100000 意味着 PostgreSQL 需要：
     *   1. 扫描满足条件的 100020 行
     *   2. 排序后丢弃前 100000 行
     *   3. 返回最后 20 行
     *
     *   在 8 亿行表上，这可能导致分钟级甚至十秒级的查询。
     *   替代方案：游标分页（keyset pagination），见 CursorPaginationHelper
     */
    @Value("${optimization.query.max-offset:10000}")
    private int maxOffset;

    /**
     * 允许的最大每页大小，默认 500
     * 单页返回太多数据会导致：
     *   - 序列化开销大
     *   - 网络传输慢
     *   - 前端渲染卡顿
     */
    @Value("${optimization.query.max-page-size:500}")
    private int maxPageSize;

    /**
     * 时间格式（与前端约定一致）
     */
    private static final DateTimeFormatter TIME_FORMATTER =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    // ====================================================================
    // 校验入口方法
    // ====================================================================

    /**
     * 校验分页查询参数
     *
     * @param startTime 开始时间（yyyy-MM-dd HH:mm:ss）
     * @param endTime   结束时间
     * @param pageNum   页码（从1开始）
     * @param pageSize  每页大小
     * @return 校验结果
     */
    public ValidationResult validatePageQuery(String startTime, String endTime,
                                              int pageNum, int pageSize) {
        ValidationResult result = new ValidationResult();

        // 1. 校验时间范围必填
        if (isBlank(startTime) || isBlank(endTime)) {
            result.setValid(false);
            result.setErrorMessage("时间范围为必填项，请选择查询时间范围");
            return result;
        }

        // 2. 校验时间格式
        LocalDateTime start;
        LocalDateTime end;
        try {
            start = LocalDateTime.parse(startTime.trim(), TIME_FORMATTER);
            end = LocalDateTime.parse(endTime.trim(), TIME_FORMATTER);
        } catch (Exception e) {
            result.setValid(false);
            result.setErrorMessage("时间格式错误，请使用 yyyy-MM-dd HH:mm:ss 格式");
            return result;
        }

        // 3. 校验时间先后顺序
        if (start.isAfter(end)) {
            result.setValid(false);
            result.setErrorMessage("开始时间不能晚于结束时间");
            return result;
        }

        // 4. 校验时间范围不超过最大值（默认1年）
        long days = ChronoUnit.DAYS.between(start, end);
        if (days > maxTimeRangeDays) {
            result.setValid(false);
            result.setErrorMessage(String.format(
                    "查询时间范围不能超过 %d 天（当前 %d 天），请缩小查询范围",
                    maxTimeRangeDays, days));
            return result;
        }

        // 5. 校验分页大小
        if (pageSize > maxPageSize) {
            result.setValid(false);
            result.setErrorMessage(String.format(
                    "每页大小不能超过 %d（当前 %d），请减小每页显示数量",
                    maxPageSize, pageSize));
            return result;
        }

        // 6. 校验深分页
        int offset = (pageNum - 1) * pageSize;
        if (offset > maxOffset) {
            result.setValid(false);
            result.setErrorMessage(String.format(
                    "查询结果过多，当前偏移 %d 超过最大限制 %d。请缩小查询条件或使用游标分页",
                    offset, maxOffset));
            return result;
        }

        // 7. 校验 pageNum 合理性
        if (pageNum < 1) {
            result.setValid(false);
            result.setErrorMessage("页码必须从 1 开始");
            return result;
        }

        // 全部通过
        result.setValid(true);
        result.setTimeRangeDays(days);
        result.setOffset(offset);
        log.debug("[查询校验] 通过: 时间范围={}天, offset={}, pageSize={}", days, offset, pageSize);
        return result;
    }

    /**
     * 校验导出查询参数（导出场景允许更大的时间范围，但仍需时间范围必填）
     *
     * 导出场景的特殊考量：
     *   - 用户可能需要导出一个月的数据做报表
     *   - 导出走异步任务，不阻塞 HTTP 请求
     *   - 但无时间范围的导出仍然要拒绝（防止误操作导出全量数据）
     */
    public ValidationResult validateExportQuery(String startTime, String endTime) {
        ValidationResult result = new ValidationResult();

        // 1. 时间范围必填
        if (isBlank(startTime) || isBlank(endTime)) {
            result.setValid(false);
            result.setErrorMessage("导出必须指定时间范围，请选择起止时间");
            return result;
        }

        // 2. 格式校验
        LocalDateTime start;
        LocalDateTime end;
        try {
            start = LocalDateTime.parse(startTime.trim(), TIME_FORMATTER);
            end = LocalDateTime.parse(endTime.trim(), TIME_FORMATTER);
        } catch (Exception e) {
            result.setValid(false);
            result.setErrorMessage("时间格式错误，请使用 yyyy-MM-dd HH:mm:ss 格式");
            return result;
        }

        // 3. 顺序校验
        if (start.isAfter(end)) {
            result.setValid(false);
            result.setErrorMessage("开始时间不能晚于结束时间");
            return result;
        }

        // 4. 导出允许最大1年时间范围
        long days = ChronoUnit.DAYS.between(start, end);
        if (days > maxTimeRangeDays) {
            result.setValid(false);
            result.setErrorMessage(String.format(
                    "导出时间范围不能超过 %d 天（当前 %d 天），请缩小导出范围",
                    maxTimeRangeDays, days));
            return result;
        }

        result.setValid(true);
        result.setTimeRangeDays(days);

        // 大时间范围导出给出警告（不拒绝，但记录日志）
        if (days > 90) {
            log.warn("[导出校验] 大时间范围导出: {}天, 请确认是否为必要操作", days);
        }

        return result;
    }

    /**
     * 判断查询是否包含模糊查询条件
     *
     * 用途：
     *   模糊查询（LIKE '%xxx%'）在 PostgreSQL 上性能很差，
     *   需要通过此判断来决定路由到 ES 还是 PostgreSQL。
     *
     * 判断逻辑：
     *   - 完整车牌号（7-8位，符合正则） → 精确查询，不是模糊查询
     *   - 部分车牌号（2-6位） → 模糊查询
     *   - 名称类字段（orgname/sectionname/roadname/gantryname/tollname） → 模糊查询
     *
     * @return true=包含模糊查询条件, false=全部为精确查询
     */
    public boolean hasFuzzyCondition(String plateNumber, String orgname,
                                     String sectionname, String roadname,
                                     String gantryname, String tollname) {
        // 车牌号：完整车牌不算模糊，部分算模糊
        if (!isBlank(plateNumber) && !isFullPlateNumber(plateNumber)) {
            return true;
        }

        // 名称类字段：只要有值就算模糊查询（因为这些字段通常是 LIKE '%xxx%' 模式）
        if (!isBlank(orgname) || !isBlank(sectionname) ||
                !isBlank(roadname) || !isBlank(gantryname) || !isBlank(tollname)) {
            return true;
        }

        return false;
    }

    // ====================================================================
    // 内部辅助方法
    // ====================================================================

    /**
     * 判断是否为完整车牌号（7-8位，符合中国车牌格式）
     * 完整车牌可以走 B-tree 索引的精确匹配，不需要走模糊查询
     */
    private boolean isFullPlateNumber(String plateNumber) {
        if (plateNumber == null || plateNumber.isEmpty()) {
            return false;
        }
        // 中国车牌正则：省份简称+字母+5-6位数字/字母
        return plateNumber.matches("^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5,6}$");
    }

    private boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }

    // ====================================================================
    // 校验结果 DTO
    // ====================================================================

    /**
     * 校验结果，包含是否通过和错误信息
     */
    @Data
    public static class ValidationResult {
        /**
         * 是否校验通过
         */
        private boolean valid;

        /**
         * 校验失败原因（仅 valid=false 时有值）
         */
        private String errorMessage;

        /**
         * 时间范围天数（校验通过后回填，供路由策略使用）
         */
        private long timeRangeDays;

        /**
         * 分页偏移量（校验通过后回填，供路由策略使用）
         */
        private int offset;
    }
}
