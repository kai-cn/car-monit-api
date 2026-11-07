#pragma once
// Spring @Scheduled cron 表达式匹配器（替换 scheduler.cpp 内原自研解析）。
//
// 语义以 Java 侧实际依赖的 spring-context 5.3.6 CronExpression 为准
// （已用探针程序对本机 .m2 中的 5.3.6 字节码实证）：
//   - 恰好 6 个字段：秒 分 时 日 月 周（第 7 段"年"非法，与 Quartz 不同）；
//   - `?` 等价 `*`；支持 `a`、`a-b`、`a/step`、`a-b/step`、`*/step`、逗号列表；
//   - `a/step` 从 a 递增到字段上限（如分的 "5/15" = 5,20,35,50）；
//   - 周字段 0-7：0 与 7 均为周日、1=周一 … 6=周六（Spring 内部把 0 归一为 7）；
//   - 日与周同时受限时为 AND："0 0 0 1 * 1" 只在"每月 1 号且周一"触发
//     （实证序列 2027-02-01/2027-03-01/2027-11-01 均为 1 号周一）。
// 不支持 L/W/# 修饰符与英文月/周名（本工程 10 个任务表达式均未使用）。
#include <string>

namespace cm::scheduler {

// 与 std::tm 对齐的墙钟。wday: 0=周日 … 6=周六。
struct WallTime {
  int year = 1970, month = 1, day = 1;
  int hour = 0, minute = 0, second = 0;
  int wday = 0;
};

// t 时刻是否命中表达式（字段数或语法非法一律返回 false，不抛异常）。
bool cron_match(const std::string& expr, const WallTime& t);

// 表达式结构是否合法：恰好 6 个字段，各 token 语法与取值范围可解析。
// 调度器注册时用它对配置的 cron 提前告警（非法表达式永不触发）。
bool cron_validate(const std::string& expr);

} // namespace cm::scheduler
