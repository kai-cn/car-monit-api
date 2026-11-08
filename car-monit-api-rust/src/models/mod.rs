pub mod car_para_vo;
pub mod car_vo;
pub mod dwd_lczt_fwqjcxx;
pub mod dwd_lczt_sfsjcxx;
pub mod dwd_lczt_sfzjcxx;
pub mod java_date_fields;
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
            Some(s) => crate::utils::parse_time(&s)
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
            Some(s) => crate::utils::parse_time(&s)
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
        Ok(JInt(Option::<i32>::deserialize(d)?))
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
        Ok(JLong(Option::<i64>::deserialize(d)?))
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
        Ok(JFloat(Option::<f64>::deserialize(d)?))
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
        match Option::<Vec<T>>::deserialize(d)? {
            None => Ok(JList::default()),
            Some(v) => Ok(JList {
                value: v,
                present: true,
            }),
        }
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
        Ok(JBool(Option::<bool>::deserialize(d)?))
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
            Some(s) => crate::utils::parse_time(&s)
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
