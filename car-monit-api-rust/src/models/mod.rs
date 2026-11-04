pub mod car_para_vo;
pub mod car_vo;
pub mod dwd_lczt_fwqjcxx;
pub mod dwd_lczt_sfsjcxx;
pub mod dwd_lczt_sfzjcxx;
pub mod java_date_fields;
pub mod java_indexed_fields;
pub mod kafka_message_record;
pub mod ods_cxzt_fwqclls;
pub mod ods_lwzxsfsj_fee_gantry_fusion01;
pub mod ods_lwzxsfsj_fee_records01;
pub mod ods_lwzxsfsj_fee_station_enter01;
pub mod ods_lwzxsfsj_fee_station_exit01;
pub mod ods_rt_szdn_snapshot_flow_addcode;
pub mod ods_rt_szdn_snapshot_flow_provcapture_addcode;
pub mod ods_rt_szdn_snapshot_flow_stationcapture_addcode;
pub mod ods_szdn_gantry;
pub mod ods_szdn_gantry_ip;
pub mod ods_szdn_province_border_vehicle_weight_newstructure;
pub mod ods_szdn_section;
pub mod ods_szdn_toll;
pub mod ods_szdn_toll_station_ip;
pub mod ods_yhgl_v_base_org;
pub mod pulsar_message_record;
pub mod suspicious_car_vo;
pub mod sys_util;
pub mod trail_bo;
pub mod trail_info;
pub mod trail_tracks_vo;
pub mod zdata_location_dict;
pub mod zdata_trail_fitting;
pub mod zdata_trail_tracks;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Deserializer, Serialize, Serializer};

/// 对应 Java `BaseController.initBinder` + `DateUtils.parseDate`：
/// 列出该实体里在 Java 声明为 `java.util.Date` 的查询参数名。Spring 用固定模式白名单
/// 解析这些参数，解析失败返回 null，于是 XML 的 `<if test="x != null">` 条件不会拼进 SQL。
/// 只有 `JavaQuery` 提取器会据此丢弃无法解析的日期参数，行为与 Java 一致。
pub trait JavaDateFields {
    const JAVA_DATE_FIELDS: &'static [&'static str] = &[];
}

/// Java 侧「下标形式」查询参数（`params[beginTime]=...`）的可绑定属性名。
///
/// Spring 的 BeanWrapper 只在根属性存在且类型是 Map/List/数组时才接受 `x[y]=v`；
/// 这几个收费实体的 `params` 是普通标量属性，Java 直接抛 InvalidPropertyException
/// 变成 HTTP 500（实测 `/base/feeGantry/list?params[beginTime]=2025-09-01` → 500），
/// 而其它没有 `params` 属性的实体则是「未知属性」，Spring 会静默忽略 → 200。
pub trait JavaIndexedFields {
    const JAVA_INDEXED_FIELDS: &'static [&'static str] = &[];
}

// ---------------------------------------------------------------------------
// Java 标量 → Rust 类型
//
// Java 的 String/Integer/Long/Double/Date 都可以为 null。SQLx 的 `Option<T>` 在
// 跨类型（VARCHAR↔TEXT、INT2↔INT4↔INT8、TIMESTAMP↔TIMESTAMPTZ）时会被类型兼容性检查拒绝，
// 因此这里用「自带 NULL 语义」的标量类型：内部是 Option，但类型兼容性覆盖同族全部 SQL 类型。
// 序列化行为与 Jackson 一致：null → JSON null，否则按 Java 格式输出。
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Default, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct JString(pub Option<String>);

impl JString {
    pub fn as_str(&self) -> &str {
        self.0.as_deref().unwrap_or("")
    }
    pub fn is_null(&self) -> bool {
        self.0.is_none()
    }
    pub fn clear(&mut self) {
        self.0 = None;
    }
}
impl std::ops::Deref for JString {
    type Target = str;
    fn deref(&self) -> &str {
        self.as_str()
    }
}
impl From<&str> for JString {
    fn from(v: &str) -> Self {
        JString(Some(v.to_string()))
    }
}
impl From<String> for JString {
    fn from(v: String) -> Self {
        JString(Some(v))
    }
}
impl From<Option<String>> for JString {
    fn from(v: Option<String>) -> Self {
        JString(v)
    }
}
impl PartialEq<&str> for JString {
    fn eq(&self, other: &&str) -> bool {
        self.as_str() == *other
    }
}
impl PartialEq<String> for JString {
    fn eq(&self, other: &String) -> bool {
        self.as_str() == other.as_str()
    }
}
impl std::fmt::Display for JString {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}
impl Serialize for JString {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match &self.0 {
            Some(v) => s.serialize_str(v),
            None => s.serialize_none(),
        }
    }
}
impl<'de> Deserialize<'de> for JString {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        Ok(JString(Option::<String>::deserialize(d)?))
    }
}
impl sqlx::Type<sqlx::Postgres> for JString {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <Option<String> as sqlx::Type<sqlx::Postgres>>::type_info()
    }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(
            sqlx::TypeInfo::name(ty),
            "VARCHAR"
                | "TEXT"
                | "BPCHAR"
                | "CHAR"
                | "NAME"
                | "INT2"
                | "INT4"
                | "INT8"
                | "TINYINT"
                | "SMALLINT"
                | "tinyint"
                | "smallint"
                | "FLOAT4"
                | "FLOAT8"
                | "NUMERIC"
                | "TIMESTAMP"
                | "TIMESTAMPTZ"
                | "DATE"
                | "TEXT[]"
                | "VARCHAR[]"
                | "BPCHAR[]"
        )
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JString {
    fn decode(
        v: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) {
            return Ok(JString(None));
        }
        let ty_name = TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()).to_string();
        let out = match ty_name.as_str() {
            "INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => {
                <i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string()
            }
            "INT4" => <i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "INT8" => <i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "FLOAT4" => <f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "FLOAT8" => <f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "NUMERIC" => {
                <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string()
            }
            "TIMESTAMP" | "TIMESTAMPTZ" => {
                // Java String 字段走 JDBC getString：直接返回墙钟时间，不做时区换算。
                let t = <DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                t.format("%Y-%m-%d %H:%M:%S").to_string()
            }
            "DATE" => {
                let t = <DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                t.format("%Y-%m-%d").to_string()
            }
            "TEXT[]" | "VARCHAR[]" | "BPCHAR[]" => {
                let arr = <Vec<Option<String>> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                format!(
                    "{{{}}}",
                    arr.into_iter()
                        .map(|x| x.unwrap_or_default())
                        .collect::<Vec<_>>()
                        .join(",")
                )
            }
            _ => <String as sqlx::Decode<sqlx::Postgres>>::decode(v)?,
        };
        Ok(JString(Some(out)))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JString {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<String> as sqlx::Encode<sqlx::Postgres>>::encode(self.0.clone(), buf)
    }
}

/// 查询参数里的 `java.util.Date`：先走 Java 的 `DateUtils.parseDate`（12 模式 + 宽松进位 +
/// 不 trim + 整串消费），失败再回退 `utils::parse_time`（ISO、epoch 毫秒等 Java 走不到的写法
/// 在 Rust 里此前已能解析，保留以免 regress 其他调用方）。
fn bind_query_date(s: &str) -> Result<DateTime<Utc>, String> {
    if let Some(t) = crate::java_date::parse_date(s) {
        return Ok(t);
    }
    crate::utils::parse_time(s)
}

// 对应 @JsonFormat(pattern = "yyyy-MM-dd")
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct Day(pub Option<DateTime<Utc>>);
impl From<DateTime<Utc>> for Day {
    fn from(v: DateTime<Utc>) -> Self {
        Day(Some(v))
    }
}
impl Day {
    pub fn new(dt: DateTime<Utc>) -> Self {
        Day(Some(dt))
    }
    pub fn utc(&self) -> Option<DateTime<Utc>> {
        self.0
    }
    pub fn format_day(&self) -> Option<String> {
        self.0.map(|t| t.format("%Y-%m-%d").to_string())
    }
}
impl Serialize for Day {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.format_day() {
            Some(v) => s.serialize_str(&v),
            None => s.serialize_none(),
        }
    }
}
impl<'de> Deserialize<'de> for Day {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Option::<String>::deserialize(d)?;
        match v {
            None => Ok(Day(None)),
            Some(s) => bind_query_date(&s)
                .map(|t| Day(Some(t)))
                .map_err(serde::de::Error::custom),
        }
    }
}
impl sqlx::Type<sqlx::Postgres> for Day {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <DateTime<Utc> as sqlx::Type<sqlx::Postgres>>::type_info()
    }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(
            sqlx::TypeInfo::name(ty),
            "TIMESTAMP" | "TIMESTAMPTZ" | "DATE"
        )
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for Day {
    fn decode(
        v: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) {
            return Ok(Day(None));
        }
        let ty_name = TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()).to_string();
        let t = <DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
        fn to_utc(ty_name: &str, t: DateTime<Utc>) -> DateTime<Utc> {
            if ty_name == "TIMESTAMPTZ" {
                t
            } else {
                // Java JDBC: serverTimezone=Asia/Shanghai；Jackson 默认按 UTC 输出
                t - chrono::Duration::hours(8)
            }
        }
        Ok(Day(Some(to_utc(&ty_name, t))))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for Day {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<DateTime<Utc>> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

// 对应 Java Date（@JsonFormat "yyyy-MM-dd HH:mm:ss"）
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JDateTime(pub Option<DateTime<Utc>>);
impl From<DateTime<Utc>> for JDateTime {
    fn from(v: DateTime<Utc>) -> Self {
        JDateTime(Some(v))
    }
}
impl JDateTime {
    pub fn new(dt: DateTime<Utc>) -> Self {
        JDateTime(Some(dt))
    }
    pub fn utc(&self) -> Option<DateTime<Utc>> {
        self.0
    }
    pub fn format_date_time(&self) -> Option<String> {
        self.0.map(|t| t.format("%Y-%m-%d %H:%M:%S").to_string())
    }
}
impl Serialize for JDateTime {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.format_date_time() {
            Some(v) => s.serialize_str(&v),
            None => s.serialize_none(),
        }
    }
}
impl<'de> Deserialize<'de> for JDateTime {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Option::<String>::deserialize(d)?;
        match v {
            None => Ok(JDateTime(None)),
            Some(s) => bind_query_date(&s)
                .map(|t| JDateTime(Some(t)))
                .map_err(serde::de::Error::custom),
        }
    }
}
impl sqlx::Type<sqlx::Postgres> for JDateTime {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <DateTime<Utc> as sqlx::Type<sqlx::Postgres>>::type_info()
    }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(
            sqlx::TypeInfo::name(ty),
            "TIMESTAMP" | "TIMESTAMPTZ" | "DATE"
        )
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JDateTime {
    fn decode(
        v: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) {
            return Ok(JDateTime(None));
        }
        let ty_name = TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()).to_string();
        let t = <DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
        fn to_utc(ty_name: &str, t: DateTime<Utc>) -> DateTime<Utc> {
            if ty_name == "TIMESTAMPTZ" {
                t
            } else {
                // Java JDBC: serverTimezone=Asia/Shanghai；Jackson 默认按 UTC 输出
                t - chrono::Duration::hours(8)
            }
        }
        Ok(JDateTime(Some(to_utc(&ty_name, t))))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JDateTime {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<DateTime<Utc>> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JInt(pub Option<i32>);
impl From<i32> for JInt {
    fn from(v: i32) -> Self {
        JInt(Some(v))
    }
}
impl From<Option<i32>> for JInt {
    fn from(v: Option<i32>) -> Self {
        JInt(v)
    }
}
impl JInt {
    pub fn get(&self) -> Option<i32> {
        self.0
    }
}
impl Serialize for JInt {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.0 {
            Some(v) => s.serialize_i32(v),
            None => s.serialize_none(),
        }
    }
}
impl<'de> Deserialize<'de> for JInt {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> serde::de::Visitor<'de> for V {
            type Value = JInt;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("i32 或数字字符串")
            }
            fn visit_str<E: serde::de::Error>(self, v: &str) -> Result<JInt, E> {
                if empty_to_none(v) {
                    return Ok(JInt(None));
                }
                v.trim()
                    .parse::<i32>()
                    .map(|n| JInt(Some(n)))
                    .map_err(serde::de::Error::custom)
            }
            fn visit_i64<E: serde::de::Error>(self, v: i64) -> Result<JInt, E> {
                Ok(JInt(Some(v as i32)))
            }
            fn visit_u64<E: serde::de::Error>(self, v: u64) -> Result<JInt, E> {
                Ok(JInt(Some(v as i32)))
            }
            fn visit_f64<E: serde::de::Error>(self, v: f64) -> Result<JInt, E> {
                Ok(JInt(Some(v as i32)))
            }
            fn visit_bool<E: serde::de::Error>(self, _v: bool) -> Result<JInt, E> {
                Err(serde::de::Error::custom("布尔值不能绑定到数字字段"))
            }
                        fn visit_map<A: serde::de::MapAccess<'de>>(self, mut map: A) -> Result<JInt, A::Error> {
                // arbitrary_precision 下 JSON 数字是单键 map（见 RAW_NUMBER_KEY 注释），
                // 取出原文后交给同一个 visitor 的字符串分支处理。
                match map.next_key::<String>()? {
                    Some(k) if k == RAW_NUMBER_KEY => {
                        let text: String = map.next_value()?;
                        self.visit_str(&text)
                    }
                    _ => Err(serde::de::Error::invalid_type(serde::de::Unexpected::Map, &self)),
                }
            }
fn visit_none<E: serde::de::Error>(self) -> Result<JInt, E> {
                Ok(JInt(None))
            }
            fn visit_unit<E: serde::de::Error>(self) -> Result<JInt, E> {
                Ok(JInt(None))
            }
        }
        d.deserialize_any(V)
    }
}
impl sqlx::Type<sqlx::Postgres> for JInt {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <i32 as sqlx::Type<sqlx::Postgres>>::type_info()
    }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(
            sqlx::TypeInfo::name(ty),
            "INT2"
                | "INT4"
                | "INT8"
                | "TINYINT"
                | "SMALLINT"
                | "tinyint"
                | "smallint"
                | "FLOAT4"
                | "FLOAT8"
                | "NUMERIC"
        )
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JInt {
    fn decode(
        v: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) {
            return Ok(JInt(None));
        }
        match TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()) {
            "INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Ok(JInt(Some(
                <i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32,
            ))),
            "INT4" => Ok(JInt(Some(<i32 as sqlx::Decode<sqlx::Postgres>>::decode(
                v,
            )?))),
            "INT8" => Ok(JInt(Some(
                <i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32,
            ))),
            "FLOAT4" => Ok(JInt(Some(
                <f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32,
            ))),
            "FLOAT8" => Ok(JInt(Some(
                <f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32,
            ))),
            "NUMERIC" => {
                use bigdecimal::ToPrimitive;
                let d = <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                Ok(JInt(d.to_i32()))
            }
            other => Err(format!("JInt 不支持的类型 {}", other).into()),
        }
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JInt {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<i32> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JLong(pub Option<i64>);
impl From<i64> for JLong {
    fn from(v: i64) -> Self {
        JLong(Some(v))
    }
}
impl From<Option<i64>> for JLong {
    fn from(v: Option<i64>) -> Self {
        JLong(v)
    }
}
impl JLong {
    pub fn get(&self) -> Option<i64> {
        self.0
    }
}
impl Serialize for JLong {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.0 {
            Some(v) => s.serialize_i64(v),
            None => s.serialize_none(),
        }
    }
}
impl<'de> Deserialize<'de> for JLong {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> serde::de::Visitor<'de> for V {
            type Value = JLong;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("i64 或数字字符串")
            }
            fn visit_str<E: serde::de::Error>(self, v: &str) -> Result<JLong, E> {
                if empty_to_none(v) {
                    return Ok(JLong(None));
                }
                v.trim()
                    .parse::<i64>()
                    .map(|n| JLong(Some(n)))
                    .map_err(serde::de::Error::custom)
            }
            fn visit_i64<E: serde::de::Error>(self, v: i64) -> Result<JLong, E> {
                Ok(JLong(Some(v as i64)))
            }
            fn visit_u64<E: serde::de::Error>(self, v: u64) -> Result<JLong, E> {
                Ok(JLong(Some(v as i64)))
            }
            fn visit_f64<E: serde::de::Error>(self, v: f64) -> Result<JLong, E> {
                Ok(JLong(Some(v as i64)))
            }
            fn visit_bool<E: serde::de::Error>(self, _v: bool) -> Result<JLong, E> {
                Err(serde::de::Error::custom("布尔值不能绑定到数字字段"))
            }
                        fn visit_map<A: serde::de::MapAccess<'de>>(self, mut map: A) -> Result<JLong, A::Error> {
                // arbitrary_precision 下 JSON 数字是单键 map（见 RAW_NUMBER_KEY 注释），
                // 取出原文后交给同一个 visitor 的字符串分支处理。
                match map.next_key::<String>()? {
                    Some(k) if k == RAW_NUMBER_KEY => {
                        let text: String = map.next_value()?;
                        self.visit_str(&text)
                    }
                    _ => Err(serde::de::Error::invalid_type(serde::de::Unexpected::Map, &self)),
                }
            }
fn visit_none<E: serde::de::Error>(self) -> Result<JLong, E> {
                Ok(JLong(None))
            }
            fn visit_unit<E: serde::de::Error>(self) -> Result<JLong, E> {
                Ok(JLong(None))
            }
        }
        d.deserialize_any(V)
    }
}
impl sqlx::Type<sqlx::Postgres> for JLong {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <i64 as sqlx::Type<sqlx::Postgres>>::type_info()
    }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(
            sqlx::TypeInfo::name(ty),
            "INT2"
                | "INT4"
                | "INT8"
                | "TINYINT"
                | "SMALLINT"
                | "tinyint"
                | "smallint"
                | "FLOAT4"
                | "FLOAT8"
                | "NUMERIC"
        )
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JLong {
    fn decode(
        v: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) {
            return Ok(JLong(None));
        }
        match TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()) {
            "INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Ok(JLong(Some(
                <i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64,
            ))),
            "INT4" => Ok(JLong(Some(
                <i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64,
            ))),
            "INT8" => Ok(JLong(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(
                v,
            )?))),
            "FLOAT4" => Ok(JLong(Some(
                <f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64,
            ))),
            "FLOAT8" => Ok(JLong(Some(
                <f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64,
            ))),
            "NUMERIC" => {
                use bigdecimal::ToPrimitive;
                let d = <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                Ok(JLong(d.to_i64()))
            }
            other => Err(format!("JLong 不支持的类型 {}", other).into()),
        }
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JLong {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<i64> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, PartialOrd)]
pub struct JFloat(pub Option<f64>);
impl From<f64> for JFloat {
    fn from(v: f64) -> Self {
        JFloat(Some(v))
    }
}
impl From<Option<f64>> for JFloat {
    fn from(v: Option<f64>) -> Self {
        JFloat(v)
    }
}
impl JFloat {
    pub fn get(&self) -> Option<f64> {
        self.0
    }
}
impl Serialize for JFloat {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.0 {
            Some(v) => s.serialize_f64(v),
            None => s.serialize_none(),
        }
    }
}
impl<'de> Deserialize<'de> for JFloat {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> serde::de::Visitor<'de> for V {
            type Value = JFloat;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("f64 或数字字符串")
            }
            fn visit_str<E: serde::de::Error>(self, v: &str) -> Result<JFloat, E> {
                if empty_to_none(v) {
                    return Ok(JFloat(None));
                }
                v.trim()
                    .parse::<f64>()
                    .map(|n| JFloat(Some(n)))
                    .map_err(serde::de::Error::custom)
            }
            fn visit_i64<E: serde::de::Error>(self, v: i64) -> Result<JFloat, E> {
                Ok(JFloat(Some(v as f64)))
            }
            fn visit_u64<E: serde::de::Error>(self, v: u64) -> Result<JFloat, E> {
                Ok(JFloat(Some(v as f64)))
            }
            fn visit_f64<E: serde::de::Error>(self, v: f64) -> Result<JFloat, E> {
                Ok(JFloat(Some(v as f64)))
            }
            fn visit_bool<E: serde::de::Error>(self, _v: bool) -> Result<JFloat, E> {
                Err(serde::de::Error::custom("布尔值不能绑定到数字字段"))
            }
                        fn visit_map<A: serde::de::MapAccess<'de>>(self, mut map: A) -> Result<JFloat, A::Error> {
                // arbitrary_precision 下 JSON 数字是单键 map（见 RAW_NUMBER_KEY 注释），
                // 取出原文后交给同一个 visitor 的字符串分支处理。
                match map.next_key::<String>()? {
                    Some(k) if k == RAW_NUMBER_KEY => {
                        let text: String = map.next_value()?;
                        self.visit_str(&text)
                    }
                    _ => Err(serde::de::Error::invalid_type(serde::de::Unexpected::Map, &self)),
                }
            }
fn visit_none<E: serde::de::Error>(self) -> Result<JFloat, E> {
                Ok(JFloat(None))
            }
            fn visit_unit<E: serde::de::Error>(self) -> Result<JFloat, E> {
                Ok(JFloat(None))
            }
        }
        d.deserialize_any(V)
    }
}
impl sqlx::Type<sqlx::Postgres> for JFloat {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <f64 as sqlx::Type<sqlx::Postgres>>::type_info()
    }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(
            sqlx::TypeInfo::name(ty),
            "FLOAT4" | "FLOAT8" | "NUMERIC" | "INT2" | "INT4" | "INT8"
        )
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JFloat {
    fn decode(
        v: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) {
            return Ok(JFloat(None));
        }
        match TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()) {
            "FLOAT4" => Ok(JFloat(Some(
                <f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64,
            ))),
            "FLOAT8" => Ok(JFloat(Some(<f64 as sqlx::Decode<sqlx::Postgres>>::decode(
                v,
            )?))),
            "NUMERIC" => {
                use bigdecimal::ToPrimitive;
                let d = <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                Ok(JFloat(d.to_f64()))
            }
            "INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Ok(JFloat(Some(
                <i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64,
            ))),
            "INT4" => Ok(JFloat(Some(
                <i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64,
            ))),
            "INT8" => Ok(JFloat(Some(
                <i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64,
            ))),
            other => Err(format!("JFloat 不支持的类型 {}", other).into()),
        }
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JFloat {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<f64> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

/// 直接按 PostgreSQL 的 numeric 二进制格式解码，保留线格式的 `dscale`。
///
/// 不能走 `sqlx::decode::<BigDecimal>`：它按「有效数字」重建数值，会把 numeric(20,2)
/// 的 1500.00 变成 1500（scale 丢失），而 Java 侧 `ResultSet#getBigDecimal` 保留 scale，
/// Jackson 输出的就是 `1500.00`。
///
/// 线格式：`i16 ndigits | i16 weight | u16 sign | i16 dscale | i16[ndigits] digits(base-10000)`
/// 值 = Σ digits[i] * 10000^(weight-i)。
fn decimal_pair(d: bigdecimal::BigDecimal) -> (bigdecimal::BigDecimal, String) {
    let t = d.to_string();
    (d, t)
}

fn decode_pg_numeric(
    v: &sqlx::postgres::PgValueRef<'_>,
) -> Result<(bigdecimal::BigDecimal, String), Box<dyn std::error::Error + Send + Sync + 'static>> {
    use bigdecimal::{BigDecimal, Zero};
    use std::str::FromStr;
    let b = v.as_bytes()?;
    if b.len() < 8 {
        return Err("numeric 二进制长度不足 8 字节".into());
    }
    let ndigits = i16::from_be_bytes([b[0], b[1]]) as usize;
    let weight = i16::from_be_bytes([b[2], b[3]]) as i32;
    let sign = u16::from_be_bytes([b[4], b[5]]);
    let dscale = i16::from_be_bytes([b[6], b[7]]).max(0) as i32;
    let expect = 8 + ndigits * 2;
    if b.len() < expect {
        return Err(format!("numeric 二进制长度不足：期望 {} 实际 {}", expect, b.len()).into());
    }
    let negative = match sign {
        0x0000 => false,
        0x4000 => true,
        other => return Err(format!("numeric 符号位非法 {:#06x}", other).into()),
    };
    let mut digits = String::new();
    for i in 0..ndigits {
        let d = i16::from_be_bytes([b[8 + i * 2], b[9 + i * 2]]) as u32;
        if d > 9999 {
            return Err(format!("numeric 非法数位 {}", d).into());
        }
        if i == 0 {
            digits.push_str(&d.to_string());
        } else {
            digits.push_str(&format!("{:04}", d));
        }
    }
    if digits.is_empty() {
        digits.push('0');
    }
    // 值 = digits * 10^exp
    let exp = 4 * (weight - ndigits as i32 + 1);
    let text = if exp >= 0 {
        format!("{}{}", digits, "0".repeat(exp as usize))
    } else {
        let frac = (-exp) as usize;
        let frac_part = digits.len().saturating_sub(frac);
        let int_part = &digits[..frac_part];
        let frac_bits = &digits[frac_part..];
        let lead = "0".repeat(frac - frac_bits.len());
        if int_part.is_empty() {
            format!("0.{}{}", lead, frac_bits)
        } else {
            format!("{}.{}{}", int_part, lead, frac_bits)
        }
    };
    let text = if negative {
        format!("-{}", text)
    } else {
        text
    };
    let value = BigDecimal::from_str(&text)?.with_scale(dscale as i64);
    // 零值：BigDecimal 会把它归一化成 "0"，但 Java 侧按 dscale 输出 0.00
    let display = if value.is_zero() && dscale > 0 {
        format!(
            "{}0.{}",
            if negative { "-" } else { "" },
            "0".repeat(dscale as usize)
        )
    } else {
        value.to_string()
    };
    Ok((value, display))
}

/// Spring 的 `WebDataBinder` 对 `Integer/Long/Double/Boolean` 属性绑定空字符串时，
/// `CustomNumberEditor`/`StringToEndwardConverter` 会把 "" 视作 null（属性保持不赋值），
/// 因此 `?enweight=` 不会报错、条件也不生效。Rust 侧 serde 默认会因 "" 解析失败返回 400，
/// 这里统一成 Java 的语义：空串→None，其它非法值仍然报错（Java 也是 400）。
fn empty_to_none(raw: &str) -> bool {
    raw.trim().is_empty()
}

/// `serde_json` 开了 `arbitrary_precision` 之后，JSON 数字不再通过 `visit_f64/visit_u64`
/// 交给 visitor，而是包成一个单键 map：key 是这个私有名字，value 是数字原文字符串。
/// 数值型的 JInt/JLong/JFloat/JDecimal 都要接住它，否则 Rust 自己写进 Redis 的字典 blob
/// 会读不回来（实测 `dev_post` 每次都是「反序列化缓存失败，回源重建」，等于白读一遍全表）。
const RAW_NUMBER_KEY: &str = "$serde_json::private::Number";

/// 对应 Java 实体里的 `BigDecimal` 字段。
///
/// 为什么不能复用 JFloat：Jackson 是直接把 `BigDecimal#toString()` 当 JSON 数字写出的，
/// 因此 DB 列的小数位会原样进入响应体（numeric(20,2) 的 1500 → `1500.00`，
/// numeric(10,4) 的 0 → `0.0000`）。JFloat 走 f64 会写成 `1500.0` / `0.0`，
/// 前端按字符串比较金额/重量时不一致。这里保留 BigDecimal 的 scale，并用 RawValue
/// 把原文当数字（不是字符串）写进 JSON。
#[derive(Debug, Clone, Default, PartialEq)]
pub struct JDecimal {
    pub value: Option<bigdecimal::BigDecimal>,
    /// 线格式原文：保留 numeric 的 dscale（Java 侧 numeric(10,2) 的 0 是 `0.00`，
    /// BigDecimal 自己会把零归一化成 `0`，所以这里单独存一份输出文本）。
    pub display: Option<String>,
}

impl JDecimal {
    /// 与 JFloat 保持同样的取数语义：调用方（过滤条件、轨迹算距离等）仍按 f64 使用。
    pub fn get(&self) -> Option<f64> {
        use bigdecimal::ToPrimitive;
        self.value.as_ref().and_then(|d| d.to_f64())
    }

    pub fn dec(&self) -> Option<&bigdecimal::BigDecimal> {
        self.value.as_ref()
    }

    pub fn text(&self) -> Option<&str> {
        self.display.as_deref()
    }
}

impl From<bigdecimal::BigDecimal> for JDecimal {
    fn from(v: bigdecimal::BigDecimal) -> Self {
        let display = v.to_string();
        JDecimal {
            value: Some(v),
            display: Some(display),
        }
    }
}

impl From<Option<f64>> for JDecimal {
    fn from(v: Option<f64>) -> Self {
        JDecimal::from(v.and_then(decimal_from_f64))
    }
}

/// `f64 → BigDecimal` 必须走「最短可回环十进制」，不能用 `BigDecimal::from_f64`：
/// 后者给出二进制精确展开（28.178358147972094 → 28.1783581479720943718…），
/// 而 Java 侧是 Jackson 按 JSON 原文读成 BigDecimal，输出 `28.178358147972094`。
fn decimal_from_f64(v: f64) -> Option<bigdecimal::BigDecimal> {
    use std::str::FromStr;
    if v.is_nan() || v.is_infinite() {
        return None;
    }
    bigdecimal::BigDecimal::from_str(&v.to_string()).ok()
}

impl From<f64> for JDecimal {
    fn from(v: f64) -> Self {
        JDecimal::from(Some(v))
    }
}

impl From<Option<&bigdecimal::BigDecimal>> for JDecimal {
    fn from(v: Option<&bigdecimal::BigDecimal>) -> Self {
        JDecimal::from(v.cloned())
    }
}

impl From<Option<bigdecimal::BigDecimal>> for JDecimal {
    fn from(v: Option<bigdecimal::BigDecimal>) -> Self {
        let display = v.as_ref().map(|d| d.to_string());
        JDecimal { value: v, display }
    }
}

impl Serialize for JDecimal {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let text = match (&self.value, &self.display) {
            (None, _) => return s.serialize_none(),
            (Some(_), Some(t)) => t.clone(),
            (Some(d), None) => d.to_string(),
        };
        let raw = serde_json::value::RawValue::from_string(text)
            .map_err(<S::Error as serde::ser::Error>::custom)?;
        s.serialize_some(&raw)
    }
}

impl<'de> Deserialize<'de> for JDecimal {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> serde::de::Visitor<'de> for V {
            type Value = JDecimal;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("BigDecimal 数字或数字字符串")
            }
            fn visit_str<E: serde::de::Error>(self, v: &str) -> Result<JDecimal, E> {
                if empty_to_none(v) {
                    return Ok(JDecimal::default());
                }
                let v = v.trim();
                // PARITY: Java 的 `new BigDecimal(text)` 只接受有限十进制数，NaN/Infinity 抛
                // NumberFormatException（→ Spring 400）。bigdecimal 会接受它们，这里显式拒绝，
                // 否则后续 numeric 绑定会打到数据库报 500。
                // Java `BigDecimal(String)` 的语法只允许 数字 / 正负号 / 小数点 / e 指数，
                // NaN、Infinity 都会抛 NumberFormatException（→ Spring 400）。
                if !v.chars().all(|c| c.is_ascii_digit() || matches!(c, '+' | '-' | '.' | 'e' | 'E')) {
                    return Err(serde::de::Error::custom(format!("非法 BigDecimal: {}", v)));
                }
                v.parse::<bigdecimal::BigDecimal>()
                    .map(|b| JDecimal::from(Some(b)))
                    .map_err(serde::de::Error::custom)
            }
            fn visit_f64<E: serde::de::Error>(self, v: f64) -> Result<JDecimal, E> {
                Ok(JDecimal::from(Some(v)))
            }
            fn visit_i64<E: serde::de::Error>(self, v: i64) -> Result<JDecimal, E> {
                Ok(JDecimal::from(Some(bigdecimal::BigDecimal::from(v))))
            }
            fn visit_u64<E: serde::de::Error>(self, v: u64) -> Result<JDecimal, E> {
                Ok(JDecimal::from(Some(bigdecimal::BigDecimal::from(v))))
            }
                        fn visit_map<A: serde::de::MapAccess<'de>>(self, mut map: A) -> Result<JDecimal, A::Error> {
                // arbitrary_precision 下 JSON 数字是单键 map（见 RAW_NUMBER_KEY 注释），
                // 取出原文后交给同一个 visitor 的字符串分支处理。
                match map.next_key::<String>()? {
                    Some(k) if k == RAW_NUMBER_KEY => {
                        let text: String = map.next_value()?;
                        self.visit_str(&text)
                    }
                    _ => Err(serde::de::Error::invalid_type(serde::de::Unexpected::Map, &self)),
                }
            }
fn visit_none<E: serde::de::Error>(self) -> Result<JDecimal, E> {
                Ok(JDecimal::default())
            }
            fn visit_unit<E: serde::de::Error>(self) -> Result<JDecimal, E> {
                Ok(JDecimal::default())
            }
        }
        d.deserialize_any(V)
    }
}

impl sqlx::Type<sqlx::Postgres> for JDecimal {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <bigdecimal::BigDecimal as sqlx::Type<sqlx::Postgres>>::type_info()
    }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(
            sqlx::TypeInfo::name(ty),
            "NUMERIC" | "FLOAT4" | "FLOAT8" | "INT2" | "INT4" | "INT8" | "VARCHAR" | "TEXT" | "BPCHAR"
        )
    }
}

impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JDecimal {
    fn decode(
        v: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) {
            return Ok(JDecimal::default());
        }
        let d: Option<(bigdecimal::BigDecimal, String)> =
            match TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()) {
            "NUMERIC" => Some(decode_pg_numeric(&v)?),
            "FLOAT4" => decimal_from_f64(
                <f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64,
            )
            .map(decimal_pair),
            "FLOAT8" => {
                decimal_from_f64(<f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?)
                    .map(decimal_pair)
            }
            "INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Some(decimal_pair(
                bigdecimal::BigDecimal::from(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64),
            )),
            "INT4" => Some(decimal_pair(bigdecimal::BigDecimal::from(
                <i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64,
            ))),
            "INT8" => Some(decimal_pair(bigdecimal::BigDecimal::from(
                <i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?,
            ))),
            "VARCHAR" | "TEXT" | "BPCHAR" => {
                let t = <String as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                if t.trim().is_empty() {
                    return Ok(JDecimal::default());
                }
                Some(decimal_pair(t.trim().parse::<bigdecimal::BigDecimal>()?))
            }
            other => return Err(format!("JDecimal 不支持的类型 {}", other).into()),
        };
        Ok(match d {
            None => JDecimal::default(),
            Some((value, display)) => JDecimal {
                value: Some(value),
                display: Some(display),
            },
        })
    }
}

impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JDecimal {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<bigdecimal::BigDecimal> as sqlx::Encode<sqlx::Postgres>>::encode(
            self.value.clone(),
            buf,
        )
    }
}

// Java List 可为 null：JList 用 present 区分“null”与“显式空数组 []”。
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct JList<T> {
    pub value: Vec<T>,
    pub present: bool,
}

impl<T> Default for JList<T> {
    fn default() -> Self {
        JList {
            value: Vec::new(),
            present: false,
        }
    }
}
impl<T> std::ops::Deref for JList<T> {
    type Target = Vec<T>;
    fn deref(&self) -> &Vec<T> {
        &self.value
    }
}
impl<T> std::ops::DerefMut for JList<T> {
    fn deref_mut(&mut self) -> &mut Vec<T> {
        &mut self.value
    }
}
impl<T> From<Vec<T>> for JList<T> {
    fn from(v: Vec<T>) -> Self {
        JList {
            value: v,
            present: true,
        }
    }
}
impl<T> FromIterator<T> for JList<T> {
    fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self {
        JList {
            value: iter.into_iter().collect(),
            present: true,
        }
    }
}
impl<T: Serialize> Serialize for JList<T> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        if self.present {
            self.value.serialize(s)
        } else {
            s.serialize_none()
        }
    }
}
impl<'de, T: Deserialize<'de>> Deserialize<'de> for JList<T> {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V<U>(std::marker::PhantomData<U>);
        impl<'de, U: Deserialize<'de>> serde::de::Visitor<'de> for V<U> {
            type Value = JList<U>;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("数组或逗号分隔字符串")
            }
            fn visit_seq<A: serde::de::SeqAccess<'de>>(
                self,
                mut seq: A,
            ) -> Result<JList<U>, A::Error> {
                let mut out = Vec::new();
                while let Some(x) = seq.next_element::<U>()? {
                    out.push(x);
                }
                Ok(JList {
                    value: out,
                    present: true,
                })
            }
            /// Java 侧 `?cidList=a,b` 由 Spring 的 `ObjectToObjectConverter.stringToObjectArray`
            /// 调 `StringUtils.commaDelimitedListToStringArray` 切分：只有**空串**得到空数组，
            /// 其余按逗号切且**不 trim、不丢空元素**（`" "` → `[" "]`、`"a,"` → `["a", ""]`）。
            /// 实测 `cidList=%20` 在 Java 走 `IN (' ')` → 0 行；若按 trim 处理会退化成
            /// 「条件不生效」→ 全量数据，正好差一整页。
            fn visit_str<E: serde::de::Error>(self, v: &str) -> Result<JList<U>, E> {
                if v.is_empty() {
                    return Ok(JList::default());
                }
                let mut out = Vec::new();
                for piece in v.split(',') {
                    let de = serde::de::value::StrDeserializer::<E>::new(piece);
                    out.push(U::deserialize(de).map_err(serde::de::Error::custom)?);
                }
                Ok(JList {
                    value: out,
                    present: true,
                })
            }
            fn visit_none<E: serde::de::Error>(self) -> Result<JList<U>, E> {
                Ok(JList::default())
            }
            fn visit_unit<E: serde::de::Error>(self) -> Result<JList<U>, E> {
                Ok(JList::default())
            }
        }
        d.deserialize_any(V(std::marker::PhantomData))
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JBool(pub Option<bool>);
impl From<bool> for JBool {
    fn from(v: bool) -> Self {
        JBool(Some(v))
    }
}
impl JBool {
    pub fn get(&self) -> Option<bool> {
        self.0
    }
}
impl Serialize for JBool {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.0 {
            Some(v) => s.serialize_bool(v),
            None => s.serialize_none(),
        }
    }
}
impl<'de> Deserialize<'de> for JBool {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> serde::de::Visitor<'de> for V {
            type Value = JBool;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("bool")
            }
            fn visit_bool<E: serde::de::Error>(self, v: bool) -> Result<JBool, E> {
                Ok(JBool(Some(v)))
            }
            fn visit_str<E: serde::de::Error>(self, v: &str) -> Result<JBool, E> {
                if empty_to_none(v) {
                    return Ok(JBool(None));
                }
                match v.trim().to_ascii_lowercase().as_str() {
                    "true" | "1" | "on" | "yes" | "y" => Ok(JBool(Some(true))),
                    "false" | "0" | "off" | "no" | "n" => Ok(JBool(Some(false))),
                    other => Err(serde::de::Error::custom(format!("非法布尔值 {}", other))),
                }
            }
            fn visit_none<E: serde::de::Error>(self) -> Result<JBool, E> {
                Ok(JBool(None))
            }
            fn visit_unit<E: serde::de::Error>(self) -> Result<JBool, E> {
                Ok(JBool(None))
            }
        }
        d.deserialize_any(V)
    }
}
impl sqlx::Type<sqlx::Postgres> for JBool {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <bool as sqlx::Type<sqlx::Postgres>>::type_info()
    }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        sqlx::TypeInfo::name(ty) == "BOOL"
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JBool {
    fn decode(
        v: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        if sqlx::ValueRef::is_null(&v) {
            return Ok(JBool(None));
        }
        Ok(JBool(Some(<bool as sqlx::Decode<sqlx::Postgres>>::decode(
            v,
        )?)))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JBool {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<bool> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

// 对应未加 @JsonFormat 的 java.util.Date：Spring Boot 默认 ISO-8601（UTC，毫秒 3 位）
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JIsoDateTime(pub Option<DateTime<Utc>>);
impl From<DateTime<Utc>> for JIsoDateTime {
    fn from(v: DateTime<Utc>) -> Self {
        JIsoDateTime(Some(v))
    }
}
impl JIsoDateTime {
    pub fn utc(&self) -> Option<DateTime<Utc>> {
        self.0
    }
    pub fn format_iso(&self) -> Option<String> {
        self.0
            .map(|t| t.format("%Y-%m-%dT%H:%M:%S%.3f+00:00").to_string())
    }
}
impl Serialize for JIsoDateTime {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.format_iso() {
            Some(v) => s.serialize_str(&v),
            None => s.serialize_none(),
        }
    }
}
impl<'de> Deserialize<'de> for JIsoDateTime {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Option::<String>::deserialize(d)?;
        match v {
            None => Ok(JIsoDateTime(None)),
            Some(s) => bind_query_date(&s)
                .map(|t| JIsoDateTime(Some(t)))
                .map_err(serde::de::Error::custom),
        }
    }
}
impl sqlx::Type<sqlx::Postgres> for JIsoDateTime {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <DateTime<Utc> as sqlx::Type<sqlx::Postgres>>::type_info()
    }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(
            sqlx::TypeInfo::name(ty),
            "TIMESTAMP" | "TIMESTAMPTZ" | "DATE"
        )
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JIsoDateTime {
    fn decode(
        v: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) {
            return Ok(JIsoDateTime(None));
        }
        let ty_name = TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()).to_string();
        let t = <DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
        let t = if ty_name.as_str() == "TIMESTAMPTZ" {
            t
        } else {
            t - chrono::Duration::hours(8)
        };
        Ok(JIsoDateTime(Some(t)))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JIsoDateTime {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<DateTime<Utc>> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

/// 对应 Java 的 DateUtils.parseDate：供模型反序列化使用。
pub fn parse_model_time(s: &str) -> Option<DateTime<Utc>> {
    crate::utils::parse_time(s).ok()
}

/// 对应 DateUtils.YYYY_MM_DD_HH_MM_SS。
pub fn format_datetime(dt: &DateTime<Utc>) -> String {
    dt.format("%Y-%m-%d %H:%M:%S").to_string()
}
pub use car_para_vo::*;
pub use car_vo::*;
pub use dwd_lczt_fwqjcxx::*;
pub use dwd_lczt_sfsjcxx::*;
pub use dwd_lczt_sfzjcxx::*;
pub use kafka_message_record::*;
pub use ods_cxzt_fwqclls::*;
pub use ods_lwzxsfsj_fee_gantry_fusion01::*;
pub use ods_lwzxsfsj_fee_records01::*;
pub use ods_lwzxsfsj_fee_station_enter01::*;
pub use ods_lwzxsfsj_fee_station_exit01::*;
pub use ods_rt_szdn_snapshot_flow_addcode::*;
pub use ods_rt_szdn_snapshot_flow_provcapture_addcode::*;
pub use ods_rt_szdn_snapshot_flow_stationcapture_addcode::*;
pub use ods_szdn_gantry::*;
pub use ods_szdn_gantry_ip::*;
pub use ods_szdn_province_border_vehicle_weight_newstructure::*;
pub use ods_szdn_section::*;
pub use ods_szdn_toll::*;
pub use ods_szdn_toll_station_ip::*;
pub use ods_yhgl_v_base_org::*;
pub use pulsar_message_record::*;
pub use suspicious_car_vo::*;
pub use sys_util::*;
pub use trail_bo::*;
pub use trail_info::*;
pub use trail_tracks_vo::*;
pub use zdata_location_dict::*;
pub use zdata_trail_fitting::*;
pub use zdata_trail_tracks::*;
