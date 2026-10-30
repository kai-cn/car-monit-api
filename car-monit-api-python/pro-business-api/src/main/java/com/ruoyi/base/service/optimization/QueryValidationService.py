# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.QueryValidationService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/QueryValidationService.java

====================================================================
查询参数校验服务
====================================================================

核心职责：
  在查询到达数据库/ES之前，对参数进行强制校验，防止以下灾难性场景：

  1. 无时间范围的全表扫描 —— 8亿行数据会导致数据库雪崩
  2. 深分页 OFFSET > 10000 —— PostgreSQL 需要扫描并丢弃前N行，越深越慢
  3. 超大时间范围（>1年） —— 超出业务需求，浪费资源
  4. 超大分页大小（>500） —— 单页返回太多数据，内存和序列化压力大

校验规则（可在 application.yml 中配置）：
  - 时间范围必填
  - 最大时间范围：365 天
  - 最大深分页偏移：10000
  - 最大每页大小：500

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → logger + 普通类；3 个 `@Value` 字段 → 构造器里
   `Environment().value("${...:默认值}", int)` 显式取值。
2) `@Data public static class ValidationResult` → **模块级** `@dataclass` +
   `JavaBean`（动态 getter/setter），末尾挂回 `QueryValidationService.ValidationResult`，
   使 `QueryValidationService.ValidationResult` 的访问路径与 Java 一致。
3) `LocalDateTime.parse(text.trim(), TIME_FORMATTER)` → 同名替身方法；
   解析失败抛 `ValueError`（Java 的 `DateTimeParseException` 是 RuntimeException 子类，
   原代码用 `catch (Exception e)` 统一兜住，Python 侧的 `except Exception` 等价）。
4) `ChronoUnit.DAYS.between(start, end)` → `ChronoUnit.DAYS.between(...)` 替身；
   注意它**不是**简单日期差，而是按“时分秒”向零截断（见替身说明）。
5) `String.format("...%d...%d...", a, b)` → `"%d"` 格式化。
6) `log.warn` → `log.warning`（Python 无 warn 方法，仅此一处差异，语义相同）。
7) `String#trim()` → `strip()`：Java 的 trim 去掉 ≤ U+0020 的字符，
   Python 的 strip 去掉所有 Unicode 空白，对本工程的日期/车牌输入等价。
8) `plateNumber.matches(regex)` → `re.fullmatch(...)`（整串匹配）。
9) `boolean` 原始类型默认 false / `long` 默认 0 / `int` 默认 0 → dataclass 默认值一致。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from java.time.LocalDateTime import LocalDateTime
from java.time.format.DateTimeFormatter import DateTimeFormatter
from java.time.temporal.ChronoUnit import ChronoUnit
from org.springframework.core.env.Environment import Environment

__all__ = ["QueryValidationService", "ValidationResult"]

log = logging.getLogger(__name__)

#: 中国车牌正则：省份简称+字母+5-6位数字/字母（原样保留 Java 方法内字面量）
_PLATE_PATTERN = re.compile(
    "^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领]"
    "[A-Z][A-Z0-9]{5,6}$")


# ====================================================================
# 校验结果 DTO（Java 静态内部类 `@Data ValidationResult`）
# ====================================================================
@dataclass
class ValidationResult(JavaBean):
    """校验结果，包含是否通过和错误信息。"""

    #: 是否校验通过（Java: private boolean valid;）
    valid: bool = False
    #: 校验失败原因（仅 valid=False 时有值）
    error_message: Optional[str] = None
    #: 时间范围天数（校验通过后回填，供路由策略使用）
    time_range_days: int = 0
    #: 分页偏移量（校验通过后回填，供路由策略使用）
    offset: int = 0


class QueryValidationService(object):
    """查询参数校验服务（`@Service`）。"""

    #: 时间格式（与前端约定一致）
    #: 【Java→Python】`private static final DateTimeFormatter TIME_FORMATTER =
    #: DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");` → 类属性（不可变、线程安全）
    TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")

    def __init__(self) -> None:
        # 允许的最大时间范围（天），默认 365 天（1年）
        self.maxTimeRangeDays: int = Environment().value(
            "${optimization.query.max-time-range-days:365}", int)
        # 允许的最大深分页偏移量，默认 10000
        self.maxOffset: int = Environment().value(
            "${optimization.query.max-offset:10000}", int)
        # 允许的最大每页大小，默认 500
        self.maxPageSize: int = Environment().value(
            "${optimization.query.max-page-size:500}", int)

    # ====================================================================
    # 校验入口方法
    # ====================================================================
    def validatePageQuery(self, startTime: str, endTime: str,
                          pageNum: int, pageSize: int) -> ValidationResult:
        """校验分页查询参数

        :param startTime: 开始时间（yyyy-MM-dd HH:mm:ss）
        :param endTime:   结束时间
        :param pageNum:   页码（从1开始）
        :param pageSize:  每页大小
        :return: 校验结果
        """
        result: ValidationResult = ValidationResult()

        # 1. 校验时间范围必填
        if self.isBlank(startTime) or self.isBlank(endTime):
            result.setValid(False)
            result.setErrorMessage("时间范围为必填项，请选择查询时间范围")
            return result

        # 2. 校验时间格式
        try:
            start: LocalDateTime = LocalDateTime.parse(
                startTime.strip(), QueryValidationService.TIME_FORMATTER)
            end: LocalDateTime = LocalDateTime.parse(
                endTime.strip(), QueryValidationService.TIME_FORMATTER)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            result.setValid(False)
            result.setErrorMessage("时间格式错误，请使用 yyyy-MM-dd HH:mm:ss 格式")
            return result

        # 3. 校验时间先后顺序
        if start.isAfter(end):
            result.setValid(False)
            result.setErrorMessage("开始时间不能晚于结束时间")
            return result

        # 4. 校验时间范围不超过最大值（默认1年）
        days: int = ChronoUnit.DAYS.between(start, end)
        if days > self.maxTimeRangeDays:
            result.setValid(False)
            result.setErrorMessage(
                "查询时间范围不能超过 %d 天（当前 %d 天），请缩小查询范围"
                % (self.maxTimeRangeDays, days))
            return result

        # 5. 校验分页大小
        if pageSize > self.maxPageSize:
            result.setValid(False)
            result.setErrorMessage(
                "每页大小不能超过 %d（当前 %d），请减小每页显示数量"
                % (self.maxPageSize, pageSize))
            return result

        # 6. 校验深分页
        offset: int = (pageNum - 1) * pageSize
        if offset > self.maxOffset:
            result.setValid(False)
            result.setErrorMessage(
                "查询结果过多，当前偏移 %d 超过最大限制 %d。请缩小查询条件或使用游标分页"
                % (offset, self.maxOffset))
            return result

        # 7. 校验 pageNum 合理性
        if pageNum < 1:
            result.setValid(False)
            result.setErrorMessage("页码必须从 1 开始")
            return result

        # 全部通过
        result.setValid(True)
        result.setTimeRangeDays(days)
        result.setOffset(offset)
        log.debug("[查询校验] 通过: 时间范围=%s天, offset=%s, pageSize=%s",
                  days, offset, pageSize)
        return result

    def validateExportQuery(self, startTime: str, endTime: str) -> ValidationResult:
        """校验导出查询参数（导出场景允许更大的时间范围，但仍需时间范围必填）

        导出场景的特殊考量：
          - 用户可能需要导出一个月的数据做报表
          - 导出走异步任务，不阻塞 HTTP 请求
          - 但无时间范围的导出仍然要拒绝（防止误操作导出全量数据）
        """
        result: ValidationResult = ValidationResult()

        # 1. 时间范围必填
        if self.isBlank(startTime) or self.isBlank(endTime):
            result.setValid(False)
            result.setErrorMessage("导出必须指定时间范围，请选择起止时间")
            return result

        # 2. 格式校验
        try:
            start: LocalDateTime = LocalDateTime.parse(
                startTime.strip(), QueryValidationService.TIME_FORMATTER)
            end: LocalDateTime = LocalDateTime.parse(
                endTime.strip(), QueryValidationService.TIME_FORMATTER)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            result.setValid(False)
            result.setErrorMessage("时间格式错误，请使用 yyyy-MM-dd HH:mm:ss 格式")
            return result

        # 3. 顺序校验
        if start.isAfter(end):
            result.setValid(False)
            result.setErrorMessage("开始时间不能晚于结束时间")
            return result

        # 4. 导出允许最大1年时间范围
        days: int = ChronoUnit.DAYS.between(start, end)
        if days > self.maxTimeRangeDays:
            result.setValid(False)
            result.setErrorMessage(
                "导出时间范围不能超过 %d 天（当前 %d 天），请缩小导出范围"
                % (self.maxTimeRangeDays, days))
            return result

        result.setValid(True)
        result.setTimeRangeDays(days)

        # 大时间范围导出给出警告（不拒绝，但记录日志）
        if days > 90:
            # 【Java→Python】`log.warn` → `log.warning`
            log.warning("[导出校验] 大时间范围导出: %s天, 请确认是否为必要操作", days)

        return result

    def hasFuzzyCondition(self, plateNumber: str, orgname: str,
                          sectionname: str, roadname: str,
                          gantryname: str, tollname: str) -> bool:
        """判断查询是否包含模糊查询条件

        用途：
          模糊查询（LIKE '%xxx%'）在 PostgreSQL 上性能很差，
          需要通过此判断来决定路由到 ES 还是 PostgreSQL。

        判断逻辑：
          - 完整车牌号（7-8位，符合正则） → 精确查询，不是模糊查询
          - 部分车牌号（2-6位） → 模糊查询
          - 名称类字段（orgname/sectionname/roadname/gantryname/tollname） → 模糊查询

        :return: true=包含模糊查询条件, false=全部为精确查询
        """
        # 车牌号：完整车牌不算模糊，部分算模糊
        if not self.isBlank(plateNumber) and not self.isFullPlateNumber(plateNumber):
            return True

        # 名称类字段：只要有值就算模糊查询（因为这些字段通常是 LIKE '%xxx%' 模式）
        if (not self.isBlank(orgname) or not self.isBlank(sectionname)
                or not self.isBlank(roadname) or not self.isBlank(gantryname)
                or not self.isBlank(tollname)):
            return True

        return False

    # ====================================================================
    # 内部辅助方法
    # ====================================================================
    def isFullPlateNumber(self, plateNumber: str) -> bool:
        """判断是否为完整车牌号（7-8位，符合中国车牌格式）

        完整车牌可以走 B-tree 索引的精确匹配，不需要走模糊查询。
        """
        if plateNumber is None or len(plateNumber) == 0:
            return False
        # 中国车牌正则：省份简称+字母+5-6位数字/字母
        return _PLATE_PATTERN.fullmatch(plateNumber) is not None

    def isBlank(self, s: str) -> bool:
        """等价 `s == null || s.trim().isEmpty()`。"""
        return s is None or len(s.strip()) == 0

    def __repr__(self) -> str:
        return ("QueryValidationService(maxTimeRangeDays=%d, maxOffset=%d, "
                "maxPageSize=%d)" % (self.maxTimeRangeDays, self.maxOffset,
                                     self.maxPageSize))


# 【Java→Python】Java 的静态内部类通过 `QueryValidationService.ValidationResult` 访问；
# 这里挂到类属性上，保持同一访问路径（与 HighPerformanceSyncService 的内部类处理一致）。
QueryValidationService.ValidationResult = ValidationResult
