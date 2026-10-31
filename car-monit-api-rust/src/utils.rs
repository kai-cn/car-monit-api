// 来源: pro-base-common/src/main/java/com/ruoyi/common/utils/CommonUtil.java
//       pro-base-common/src/main/java/com/ruoyi/common/utils/DateUtils.java
//       pro-base-common/src/main/java/com/ruoyi/common/utils/StringUtils.java
//       pro-base-common/src/main/java/com/ruoyi/common/utils/SecuritySHA1Utils.java
// 职责: 纯函数工具，与 Java 版本逐函数对应。
// 对应关系:
//   CommonUtil.isNull          ↔ is_null
//   CommonUtil.deleteEnd       ↔ delete_end
//   CommonUtil.repalacePicUrl  ↔ replace_pic_url
//   DateUtils.parseDate        ↔ parse_time
//   DateUtils.parseDateToStr   ↔ format_datetime
//   StringUtils.getUUID        ↔ uuid_simple

use chrono::{DateTime, NaiveDate, NaiveDateTime, TimeZone, Utc};
use uuid::Uuid;

/// 对应 CommonUtil.isNull(Object)：null → ""；否则 trim 后的 toString。
/// DIFF: Rust 没有 null，统一用 Option；None/空串都返回 ""。
pub fn is_null<T: ToString>(v: Option<T>) -> String {
    match v {
        Some(x) => x.to_string().trim().to_string(),
        None => String::new(),
    }
}

pub fn is_blank(s: &str) -> bool {
    s.trim().is_empty()
}

pub fn is_not_blank(s: &str) -> bool {
    !is_blank(s)
}

/// 对应 CommonUtil.deleteEnd：删除结尾的一个逗号。
pub fn delete_end(s: &str) -> String {
    let s = s.trim();
    s.strip_suffix(',').unwrap_or(s).to_string()
}

/// 对应 Arrays.stream(s.split(",")).collect(...)：去空白、丢空段。
pub fn split_csv(s: &str) -> Vec<String> {
    s.split(',')
        .map(|p| p.trim())
        .filter(|p| !p.is_empty())
        .map(|p| p.to_string())
        .collect()
}

/// 对应 CommonUtil.repalacePicUrl：图片域名归一。
pub fn replace_pic_url(s: &str) -> String {
    let s = s.trim();
    if s.contains("http://jxjt.isilon.com/ifs") {
        s.replace("http://jxjt.isilon.com/ifs", "http://36.200.30.144:9080")
    } else {
        s.replace("http://jxjt.isilon.com", "http://36.200.30.144:9080")
    }
}

/// 对应 CommonUtil.repalaceSzdnTollName。
pub fn replace_toll_name(s: &str) -> String {
    s.replace("收费站", "")
        .replace("江西", "")
        .replace("站", "")
}

/// 对应 StringUtils.getUUID()：去掉横线的 32 位 uuid。
pub fn uuid_simple() -> String {
    Uuid::new_v4().simple().to_string()
}

/// 对应 DateUtils.parseDate：多格式容忍解析。
/// DIFF: Java SimpleDateFormat 每次 new 一个 pattern；Rust 用 chrono 的显式格式列表。
pub fn parse_time(s: &str) -> Result<DateTime<Utc>, String> {
    let s = s.trim();
    if s.is_empty() {
        return Ok(Utc.timestamp_opt(0, 0).unwrap());
    }
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S%.3f",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%.fZ",
        "%Y-%m-%dT%H:%M:%S%.f%:z",
    ] {
        if let Ok(dt) = NaiveDateTime::parse_from_str(s, fmt) {
            return Ok(Utc.from_utc_datetime(&dt));
        }
        if let Ok(dt) = DateTime::parse_from_str(s, fmt) {
            return Ok(dt.with_timezone(&Utc));
        }
    }
    for fmt in ["%Y-%m-%d", "%Y/%m/%d"] {
        if let Ok(d) = NaiveDate::parse_from_str(s, fmt) {
            let dt = d.and_hms_opt(0, 0, 0).unwrap();
            return Ok(Utc.from_utc_datetime(&dt));
        }
    }
    // 兼容纯数字时间戳（秒 / 毫秒）
    if let Ok(n) = s.parse::<i64>() {
        if n > 1_000_000_000_000 {
            return Utc
                .timestamp_millis_opt(n)
                .single()
                .ok_or_else(|| format!("非法毫秒时间戳 {}", n));
        }
        return Utc
            .timestamp_opt(n, 0)
            .single()
            .ok_or_else(|| format!("非法秒时间戳 {}", n));
    }
    Err(format!("无法解析时间 {:?}", s))
}

/// 对应 DateUtils.parseDateToStr(YYYY_MM_DD_HH_MM_SS, date)。
pub fn format_datetime(dt: &DateTime<Utc>) -> String {
    dt.format("%Y-%m-%d %H:%M:%S").to_string()
}

/// Java `SimpleDateFormat` 默认使用 JVM 时区（Asia/Shanghai）：用于 snapshottimeStr 等展示字段。
pub fn format_datetime_local(dt: &DateTime<Utc>) -> String {
    (*dt + chrono::Duration::hours(8))
        .format("%Y-%m-%d %H:%M:%S")
        .to_string()
}

/// 对应 @JsonFormat(pattern="yyyy-MM-dd")。
pub fn format_day(dt: &DateTime<Utc>) -> String {
    dt.format("%Y-%m-%d").to_string()
}

/// 对应 DateUtils.differentDaysByMillisecond / Duration 计算。
pub fn days_between(start: &str, end: &str) -> Result<i64, String> {
    let st = parse_time(start)?;
    let et = parse_time(end)?;
    if et < st {
        return Err("endTime 不能早于 startTime".to_string());
    }
    Ok((et - st).num_days())
}

/// 对应 SecuritySHA1Utils.shaEncode（SystemUtil 外部推送签名用）。
pub fn sha1_hex(input: &str) -> String {
    use sha1_smol::Sha1;
    let mut h = Sha1::new();
    h.update(input.as_bytes());
    h.digest().to_string()
}

/// 对应 MD5Example / MD5 工具（仅在自测接口里使用）。
pub fn md5_hex(input: &str) -> String {
    md5_smol::md5(input.as_bytes())
        .to_le_bytes()
        .iter()
        .map(|b| format!("{:02x}", b))
        .collect()
}

/// 极简 MD5 实现，避免额外 crate（与 Java MessageDigest("MD5") 等价）。
mod md5_smol {
    pub fn md5(input: &[u8]) -> u128 {
        // RFC 1321，仅用于兼容 Java 侧演示代码，非安全用途。
        const S: [u32; 64] = [
            7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 5, 9, 14, 20, 5, 9, 14, 20,
            5, 9, 14, 20, 5, 9, 14, 20, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
            6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
        ];
        const K: [u32; 64] = [
            0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee, 0xf57c0faf, 0x4787c62a, 0xa8304613,
            0xfd469501, 0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be, 0x6b901122, 0xfd987193,
            0xa679438e, 0x49b40821, 0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa, 0xd62f105d,
            0x02441453, 0xd8a1e681, 0xe7d3fbc8, 0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed,
            0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a, 0xfffa3942, 0x8771f681, 0x6d9d6122,
            0xfde5380c, 0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70, 0x289b7ec6, 0xeaa127fa,
            0xd4ef3085, 0x04881d05, 0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665, 0xf4292244,
            0x432aff97, 0xab9423a7, 0xfc93a039, 0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
            0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1, 0xf7537e82, 0xbd3af235, 0x2ad7d2bb,
            0xeb86d391,
        ];
        let mut msg = input.to_vec();
        let bit_len = (msg.len() as u64).wrapping_mul(8);
        msg.push(0x80);
        while msg.len() % 64 != 56 {
            msg.push(0);
        }
        msg.extend_from_slice(&bit_len.to_le_bytes());

        let (mut a0, mut b0, mut c0, mut d0): (u32, u32, u32, u32) =
            (0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476);
        for chunk in msg.chunks(64) {
            let mut m = [0u32; 16];
            for (i, w) in chunk.chunks(4).enumerate() {
                m[i] = u32::from_le_bytes([w[0], w[1], w[2], w[3]]);
            }
            let (mut a, mut b, mut c, mut d): (u32, u32, u32, u32) = (a0, b0, c0, d0);
            for i in 0..64 {
                let (f, g) = match i / 16 {
                    0 => ((b & c) | (!b & d), i),
                    1 => ((d & b) | (!d & c), (5 * i + 1) % 16),
                    2 => (b ^ c ^ d, (3 * i + 5) % 16),
                    _ => (c ^ (b | !d), (7 * i) % 16),
                };
                let tmp = d;
                d = c;
                c = b;
                b = b.wrapping_add(
                    a.wrapping_add(f)
                        .wrapping_add(K[i])
                        .wrapping_add(m[g])
                        .rotate_left(S[i]),
                );
                a = tmp;
            }
            a0 = a0.wrapping_add(a);
            b0 = b0.wrapping_add(b);
            c0 = c0.wrapping_add(c);
            d0 = d0.wrapping_add(d);
        }
        let mut out = 0u128;
        for (i, v) in [a0, b0, c0, d0].iter().enumerate() {
            out |= (*v as u128) << (i * 32);
        }
        out
    }
}
