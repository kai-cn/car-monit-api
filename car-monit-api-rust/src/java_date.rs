// 对应 pro-base-common/src/main/java/com/ruoyi/common/utils/DateUtils.java:28-31 + BaseController.initBinder
//
// Java 侧所有 `java.util.Date` 查询参数都走这条链路：
//   PropertyEditorSupport.setAsText(text) → DateUtils.parseDate(text) → 失败则 setValue(null)
// 三个关键语义，Rust 里必须逐条对齐（否则同一请求 Java 忽略条件、Rust 报错或反过来）：
//   1. **不 trim**：`"  2025-09-10  "` 在 Java 解析失败 → 条件不生效（HTTP 200 全量数据），
//      而不是「去掉空格后照常解析」；
//   2. **lenient**：SimpleDateFormat 默认宽松，月份/日/时分秒越界会向前后进位，
//      `2025-13-45` → 2026-02-14、`2025-09-10 25:61:61` → 次日 02:02:01、`10-09-2025` → 年 10 日 2025；
//   3. **数字段贪婪**：字段宽度不固定（NumberFormat 而非定宽数字），`2025-9-1` 合法、
//      `20250910` 非法（年段吞掉全部数字后等不到字面量 `-`）。
// 解析成功后还要求「整串消费完」，与 commons-lang `DateUtils.parseDateWithLeniency` 一致：
// `2025-09-10T12:33:00`、`2025-09-10 12:33:00.000` 都会因为尾部残留而失败。
use chrono::{Datelike, NaiveDate, NaiveDateTime, TimeZone, Utc};

/// 一个模式 = 分隔符 + 字段序列。Java 的 12 个模式都是
/// `yyyy<sep>MM[<sep>dd[ <HH>:<mm>[:<ss>]]]` 与 `yyyy<sep>MM` 的组合。
#[derive(Clone, Copy)]
enum Field {
    Year,
    Month,
    Day,
    Hour,
    Minute,
    Second,
}

#[derive(Clone, Copy)]
struct Pattern {
    sep: char,
    fields: &'static [Field],
}

const ALL_FIELDS: &[Field] = &[
    Field::Year,
    Field::Month,
    Field::Day,
    Field::Hour,
    Field::Minute,
    Field::Second,
];

/// DateUtils.parsePatterns 的原始顺序（顺序会决定 `2025-9` 落到 yyyy-MM 而不是别的模式）。
const PATTERNS: &[Pattern] = &[
    Pattern { sep: '-', fields: &[Field::Year, Field::Month, Field::Day] },
    Pattern { sep: '-', fields: &[Field::Year, Field::Month, Field::Day, Field::Hour, Field::Minute, Field::Second] },
    Pattern { sep: '-', fields: &[Field::Year, Field::Month, Field::Day, Field::Hour, Field::Minute] },
    Pattern { sep: '-', fields: &[Field::Year, Field::Month] },
    Pattern { sep: '/', fields: &[Field::Year, Field::Month, Field::Day] },
    Pattern { sep: '/', fields: ALL_FIELDS },
    Pattern { sep: '/', fields: &[Field::Year, Field::Month, Field::Day, Field::Hour, Field::Minute] },
    Pattern { sep: '/', fields: &[Field::Year, Field::Month] },
    Pattern { sep: '.', fields: &[Field::Year, Field::Month, Field::Day] },
    Pattern { sep: '.', fields: ALL_FIELDS },
    Pattern { sep: '.', fields: &[Field::Year, Field::Month, Field::Day, Field::Hour, Field::Minute] },
    Pattern { sep: '.', fields: &[Field::Year, Field::Month] },
];

/// 贪婪读一段十进制整数（允许前导 +/-，至少要 1 位数字）；返回消费到的下一个位置。
fn read_number(bytes: &[u8], mut i: usize) -> Option<(i64, usize)> {
    let start = i;
    let mut sign = 1i64;
    if i < bytes.len() && (bytes[i] == b'-' || bytes[i] == b'+') {
        sign = if bytes[i] == b'-' { -1 } else { 1 };
        i += 1;
    }
    let digit_start = i;
    let mut acc = 0i64;
    while i < bytes.len() && bytes[i].is_ascii_digit() {
        // 溢出时饱和即可：越界的年份在 Java 里也只是算出一个极端日期，匹配不到数据。
        acc = acc.saturating_mul(10).saturating_add((bytes[i] - b'0') as i64);
        i += 1;
    }
    if i == digit_start {
        return None;
    }
    let _ = start;
    Some((sign * acc, i))
}

/// 按单个模式解析，成功返回各字段（未出现的字段用 Calendar 的默认值：日=1，时分秒=0）。
fn parse_with(bytes: &[u8], p: &Pattern) -> Option<[i64; 6]> {
    let mut out = [0i64; 6];
    out[2] = 1; // DAY_OF_MONTH 默认 1（yyyy-MM 模式下 Java 补当月 1 日）
    let mut i = 0usize;
    for (idx, f) in p.fields.iter().enumerate() {
        if idx > 0 {
            // 字段之间的字面量：日期部分用分隔符，时间部分用 ':'，日期与时间之间是空格。
            let want = match (*f, p.fields[idx - 1]) {
                (Field::Hour, Field::Day) => ' ',
                (Field::Minute, _) | (Field::Second, _) => ':',
                _ => p.sep,
            };
            if i >= bytes.len() || bytes[i] != want as u8 {
                return None;
            }
            i += 1;
        }
        let (v, next) = read_number(bytes, i)?;
        let slot = match f {
            Field::Year => 0,
            Field::Month => 1,
            Field::Day => 2,
            Field::Hour => 3,
            Field::Minute => 4,
            Field::Second => 5,
        };
        out[slot] = v;
        i = next;
    }
    // commons-lang 要求整串消费完（尾部残留 .000 / T12:33:00 / 空格 都会失败）
    if i != bytes.len() {
        return None;
    }
    Some(out)
}

/// lenient 进位：与 GregorianCalendar 的越界回卷等价（在常用年份区间内逐日一致）。
/// `month` 是模式里 MM 读出来的 1-based 月份（Calendar.MONTH 还要 -1，Java 亦如此）。
fn lenient_datetime(y: i64, month: i64, day: i64, h: i64, mi: i64, s: i64) -> Option<NaiveDateTime> {
    let m0 = month - 1;
    let year0 = m0.div_euclid(12);
    let month01 = m0.rem_euclid(12) + 1;
    let year = y.checked_add(year0).unwrap_or(i64::from(i32::MIN));
    let base = if (i32::MIN as i64..=i32::MAX as i64).contains(&year) {
        match NaiveDate::from_ymd_opt(year as i32, month01 as u32, 1) {
            Some(d) => d,
            // 年份超出 chrono 表达范围：Java 仍能算出一个极端的 Date，条件照样生效但匹配不到数据，
            // 这里退化成「足够古老的日期」，保持「条件生效」这一语义。
            None => NaiveDate::MIN,
        }
    } else {
        NaiveDate::MIN
    };
    let mut dt = base.and_hms_opt(0, 0, 0)?;
    // 各段进位同样可能溢出（例如 2025-09-1 + 2025 天）：溢出后一律落到可用的极值，
    // 因为 Java 那边得到的也是一个匹配不到任何行的极端时间戳。
    dt = dt
        .checked_add_signed(chrono::Duration::days(day.saturating_sub(1)))
        .unwrap_or(dt);
    dt = dt
        .checked_add_signed(chrono::Duration::hours(h))
        .unwrap_or(dt);
    dt = dt
        .checked_add_signed(chrono::Duration::minutes(mi))
        .unwrap_or(dt);
    dt = dt
        .checked_add_signed(chrono::Duration::seconds(s))
        .unwrap_or(dt);
    // Java 那边 `0000-00-00` 算出的是公元前 1 年，pgjdbc 会用 BC 纪元写出合法字面量；
    // chrono/sqlx 走的是 ISO 文本，负年份会变成 `-0001-11-30`，GaussDB 直接
    // `invalid input syntax for type timestamp` → 500，而 Java 是 200（0 行）。
    // 这里一律收敛到公元 1 年：仍然是「条件生效且匹配不到任何行」，语义与 Java 一致。
    if dt.year() < 1 {
        let floor = NaiveDate::from_ymd_opt(1, 1, 1)?.and_hms_opt(0, 0, 0);
        return floor;
    }
    Some(dt)
}

/// 对应 `DateUtils.parseDate(Object)`：解析失败返回 None（Java 侧即 setValue(null)）。
/// 返回的时间按「墙上时钟」直接落到 UTC，与 utils::parse_time 既有的约定保持一致
/// （列是 timestamp 时 Java 按 serverTimezone 读写，两边同偏移，比对结果相同）。
pub fn parse_date(text: &str) -> Option<chrono::DateTime<Utc>> {
    if text.is_empty() {
        return None;
    }
    let bytes = text.as_bytes();
    for p in PATTERNS {
        if let Some([y, mo, d, h, mi, s]) = parse_with(bytes, p) {
            return lenient_datetime(y, mo, d, h, mi, s)
                .map(|dt| Utc.from_utc_datetime(&dt));
        }
    }
    None
}

/// 白名单判定：该字符串在 Java 的 PropertyEditor 下是否会被绑定成非 null 的 Date。
pub fn parseable(text: &str) -> bool {
    parse_date(text).is_some()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn day(text: &str) -> Option<String> {
        parse_date(text).map(|t| t.format("%Y-%m-%d %H:%M:%S").to_string())
    }

    #[test]
    fn strict_full_consumption() {
        assert_eq!(day("2025-09-10").as_deref(), Some("2025-09-10 00:00:00"));
        assert_eq!(day("2025-09-10 12:33:00").as_deref(), Some("2025-09-10 12:33:00"));
        assert_eq!(day("2025-09-10 12:33").as_deref(), Some("2025-09-10 12:33:00"));
        assert_eq!(day("2025-09").as_deref(), Some("2025-09-01 00:00:00"));
        // 尾部残留一律失败
        assert_eq!(day("2025-09-10 12:33:00.000"), None);
        assert_eq!(day("2025-09-10T12:33:00"), None);
        assert_eq!(day("2025-09-10 12:33:00 "), None);
        assert_eq!(day("  2025-09-10  "), None);
        assert_eq!(day("2025-09-10 12"), None);
        assert_eq!(day("20250910"), None);
        assert_eq!(day("1757462400000"), None);
        assert_eq!(day("abc"), None);
        assert_eq!(day(""), None);
    }

    #[test]
    fn greedy_fields_not_fixed_width() {
        assert_eq!(day("2025-9-1").as_deref(), Some("2025-09-01 00:00:00"));
        assert_eq!(day("2025-09-10 1:2:3").as_deref(), Some("2025-09-10 01:02:03"));
        assert_eq!(day("2025/9/10").as_deref(), Some("2025-09-10 00:00:00"));
        assert_eq!(day("2025.9.10").as_deref(), Some("2025-09-10 00:00:00"));
    }

    #[test]
    fn lenient_rollover() {
        // 月 13 → 次年 1 月，日 45 → 再加 44 天
        assert_eq!(day("2025-13-45").as_deref(), Some("2026-02-14 00:00:00"));
        // 25:61:61 → 次日 02:02:01
        assert_eq!(
            day("2025-09-10 25:61:61").as_deref(),
            Some("2025-09-11 02:02:01")
        );
        // 贪婪：年 10 / 月 09 / 日 2025 —— 结果落在公元 16 世纪前后，Java 用儒略历、
        // chrono 用外推格里高利历，绝对值差几天，但两边都匹配不到任何行，语义一致。
        assert!(day("10-09-2025").is_some());
        // 日 0 → 上一月最后一天
        assert_eq!(day("2025-03-0").as_deref(), Some("2025-02-28 00:00:00"));
        // 公元前会算出负年份，GaussDB 不接受 `-0001-11-30`，一律收敛到公元 1 年
        assert_eq!(day("0000-00-00").as_deref(), Some("0001-01-01 00:00:00"));
    }

    #[test]
    fn matches_java_pattern_order() {
        // yyyy-MM 在 yyyy-MM-dd 之后，但只有整串匹配才算成功，所以顺序不影响这些用例
        assert_eq!(day("2025-09-10 12:33:00").as_deref(), Some("2025-09-10 12:33:00"));
        assert_eq!(day("2025/09/10 12:33").as_deref(), Some("2025-09-10 12:33:00"));
        assert_eq!(day("2025.09").as_deref(), Some("2025-09-01 00:00:00"));
    }
}
