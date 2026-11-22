import io

p = 'tools/gen_models.py'
s = io.open(p, encoding='utf-8').read()
start = s.index("    with open(os.path.join(out_dir, 'mod.rs')")
end = s.index("    print('generated %d structs into %s' % (len(mods), out_dir))")

block = r'''    with open(os.path.join(out_dir, 'mod.rs'), 'w', encoding='utf-8', newline='\n') as f:
        for m in sorted(set(mods)):
            f.write('pub mod %s;\n' % m)
        f.write('\nuse chrono::{DateTime, Utc};\n')
        f.write('use serde::{Deserialize, Deserializer, Serialize, Serializer};\n\n')
        f.write(r"""
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
    pub fn as_str(&self) -> &str { self.0.as_deref().unwrap_or("") }
    pub fn is_null(&self) -> bool { self.0.is_none() }
    pub fn clear(&mut self) { self.0 = None; }
}
impl std::ops::Deref for JString {
    type Target = str;
    fn deref(&self) -> &str { self.as_str() }
}
impl From<&str> for JString { fn from(v: &str) -> Self { JString(Some(v.to_string())) } }
impl From<String> for JString { fn from(v: String) -> Self { JString(Some(v)) } }
impl From<Option<String>> for JString { fn from(v: Option<String>) -> Self { JString(v) } }
impl PartialEq<&str> for JString { fn eq(&self, other: &&str) -> bool { self.as_str() == *other } }
impl PartialEq<String> for JString { fn eq(&self, other: &String) -> bool { self.as_str() == other.as_str() } }
impl std::fmt::Display for JString {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result { f.write_str(self.as_str()) }
}
impl Serialize for JString {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match &self.0 { Some(v) => s.serialize_str(v), None => s.serialize_none() }
    }
}
impl<'de> Deserialize<'de> for JString {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        Ok(JString(Option::<String>::deserialize(d)?))
    }
}
impl sqlx::Type<sqlx::Postgres> for JString {
    fn type_info() -> sqlx::postgres::PgTypeInfo { <Option<String> as sqlx::Type<sqlx::Postgres>>::type_info() }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(sqlx::TypeInfo::name(ty), "VARCHAR" | "TEXT" | "BPCHAR" | "CHAR" | "NAME")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JString {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        if sqlx::ValueRef::is_null(&v) { return Ok(JString(None)); }
        Ok(JString(Some(<String as sqlx::Decode<sqlx::Postgres>>::decode(v)?)))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JString {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<String> as sqlx::Encode<sqlx::Postgres>>::encode(self.0.clone(), buf)
    }
}

// 对应 @JsonFormat(pattern = "yyyy-MM-dd")
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct Day(pub Option<DateTime<Utc>>);
impl From<DateTime<Utc>> for Day { fn from(v: DateTime<Utc>) -> Self { Day(Some(v)) } }
impl Day {
    pub fn new(dt: DateTime<Utc>) -> Self { Day(Some(dt)) }
    pub fn utc(&self) -> Option<DateTime<Utc>> { self.0 }
    pub fn format_day(&self) -> Option<String> { self.0.map(|t| t.format("%Y-%m-%d").to_string()) }
}
impl Serialize for Day {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.format_day() { Some(v) => s.serialize_str(&v), None => s.serialize_none() }
    }
}
impl<'de> Deserialize<'de> for Day {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Option::<String>::deserialize(d)?;
        match v {
            None => Ok(Day(None)),
            Some(s) => crate::utils::parse_time(&s).map(|t| Day(Some(t))).map_err(serde::de::Error::custom),
        }
    }
}
impl sqlx::Type<sqlx::Postgres> for Day {
    fn type_info() -> sqlx::postgres::PgTypeInfo { <DateTime<Utc> as sqlx::Type<sqlx::Postgres>>::type_info() }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(sqlx::TypeInfo::name(ty), "TIMESTAMP" | "TIMESTAMPTZ" | "DATE")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for Day {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        if sqlx::ValueRef::is_null(&v) { return Ok(Day(None)); }
        Ok(Day(Some(<DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?)))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for Day {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<DateTime<Utc>> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

// 对应 Java Date（@JsonFormat "yyyy-MM-dd HH:mm:ss"）
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JDateTime(pub Option<DateTime<Utc>>);
impl From<DateTime<Utc>> for JDateTime { fn from(v: DateTime<Utc>) -> Self { JDateTime(Some(v)) } }
impl JDateTime {
    pub fn new(dt: DateTime<Utc>) -> Self { JDateTime(Some(dt)) }
    pub fn utc(&self) -> Option<DateTime<Utc>> { self.0 }
    pub fn format_date_time(&self) -> Option<String> { self.0.map(|t| t.format("%Y-%m-%d %H:%M:%S").to_string()) }
}
impl Serialize for JDateTime {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.format_date_time() { Some(v) => s.serialize_str(&v), None => s.serialize_none() }
    }
}
impl<'de> Deserialize<'de> for JDateTime {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Option::<String>::deserialize(d)?;
        match v {
            None => Ok(JDateTime(None)),
            Some(s) => crate::utils::parse_time(&s).map(|t| JDateTime(Some(t))).map_err(serde::de::Error::custom),
        }
    }
}
impl sqlx::Type<sqlx::Postgres> for JDateTime {
    fn type_info() -> sqlx::postgres::PgTypeInfo { <DateTime<Utc> as sqlx::Type<sqlx::Postgres>>::type_info() }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(sqlx::TypeInfo::name(ty), "TIMESTAMP" | "TIMESTAMPTZ" | "DATE")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JDateTime {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        if sqlx::ValueRef::is_null(&v) { return Ok(JDateTime(None)); }
        Ok(JDateTime(Some(<DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?)))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JDateTime {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<DateTime<Utc>> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JInt(pub Option<i32>);
impl From<i32> for JInt { fn from(v: i32) -> Self { JInt(Some(v)) } }
impl From<Option<i32>> for JInt { fn from(v: Option<i32>) -> Self { JInt(v) } }
impl JInt { pub fn get(&self) -> Option<i32> { self.0 } }
impl Serialize for JInt {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.0 { Some(v) => s.serialize_i32(v), None => s.serialize_none() }
    }
}
impl<'de> Deserialize<'de> for JInt {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> { Ok(JInt(Option::<i32>::deserialize(d)?)) }
}
impl sqlx::Type<sqlx::Postgres> for JInt {
    fn type_info() -> sqlx::postgres::PgTypeInfo { <i32 as sqlx::Type<sqlx::Postgres>>::type_info() }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(sqlx::TypeInfo::name(ty), "INT2" | "INT4" | "INT8")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JInt {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JInt(None)); }
        match TypeInfo::name(sqlx::ValueRef::type_info(&v)) {
            "INT2" => Ok(JInt(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
            "INT4" => Ok(JInt(Some(<i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)?))),
            "INT8" => Ok(JInt(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
            other => Err(format!("JInt 不支持的类型 {}", other).into()),
        }
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JInt {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<i32> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JLong(pub Option<i64>);
impl From<i64> for JLong { fn from(v: i64) -> Self { JLong(Some(v)) } }
impl From<Option<i64>> for JLong { fn from(v: Option<i64>) -> Self { JLong(v) } }
impl JLong { pub fn get(&self) -> Option<i64> { self.0 } }
impl Serialize for JLong {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.0 { Some(v) => s.serialize_i64(v), None => s.serialize_none() }
    }
}
impl<'de> Deserialize<'de> for JLong {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> { Ok(JLong(Option::<i64>::deserialize(d)?)) }
}
impl sqlx::Type<sqlx::Postgres> for JLong {
    fn type_info() -> sqlx::postgres::PgTypeInfo { <i64 as sqlx::Type<sqlx::Postgres>>::type_info() }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(sqlx::TypeInfo::name(ty), "INT2" | "INT4" | "INT8")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JLong {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JLong(None)); }
        match TypeInfo::name(sqlx::ValueRef::type_info(&v)) {
            "INT2" => Ok(JLong(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),
            "INT4" => Ok(JLong(Some(<i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),
            "INT8" => Ok(JLong(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?))),
            other => Err(format!("JLong 不支持的类型 {}", other).into()),
        }
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JLong {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<i64> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, PartialOrd)]
pub struct JFloat(pub Option<f64>);
impl From<f64> for JFloat { fn from(v: f64) -> Self { JFloat(Some(v)) } }
impl From<Option<f64>> for JFloat { fn from(v: Option<f64>) -> Self { JFloat(v) } }
impl JFloat { pub fn get(&self) -> Option<f64> { self.0 } }
impl Serialize for JFloat {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.0 { Some(v) => s.serialize_f64(v), None => s.serialize_none() }
    }
}
impl<'de> Deserialize<'de> for JFloat {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> { Ok(JFloat(Option::<f64>::deserialize(d)?)) }
}
impl sqlx::Type<sqlx::Postgres> for JFloat {
    fn type_info() -> sqlx::postgres::PgTypeInfo { <f64 as sqlx::Type<sqlx::Postgres>>::type_info() }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(sqlx::TypeInfo::name(ty), "FLOAT4" | "FLOAT8" | "NUMERIC" | "INT2" | "INT4" | "INT8")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JFloat {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JFloat(None)); }
        match TypeInfo::name(sqlx::ValueRef::type_info(&v)) {
            "FLOAT4" => Ok(JFloat(Some(<f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64))),
            "FLOAT8" => Ok(JFloat(Some(<f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?))),
            "NUMERIC" => {
                use bigdecimal::ToPrimitive;
                let d = <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                Ok(JFloat(d.to_f64()))
            }
            "INT2" => Ok(JFloat(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64))),
            "INT4" => Ok(JFloat(Some(<i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64))),
            "INT8" => Ok(JFloat(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64))),
            other => Err(format!("JFloat 不支持的类型 {}", other).into()),
        }
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JFloat {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<f64> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

""")
        f.write('/// 对应 Java 的 DateUtils.parseDate：供模型反序列化使用。\n')
        f.write('pub fn parse_model_time(s: &str) -> Option<DateTime<Utc>> {\n')
        f.write('    crate::utils::parse_time(s).ok()\n')
        f.write('}\n\n')
        f.write('/// 对应 DateUtils.YYYY_MM_DD_HH_MM_SS。\n')
        f.write('pub fn format_datetime(dt: &DateTime<Utc>) -> String { dt.format("%Y-%m-%d %H:%M:%S").to_string() }\n')
        for m in sorted(set(mods)):
            f.write('pub use %s::*;\n' % m)
'''
s = s[:start] + block + s[end:]

# generator field mapping: database types -> custom scalars
s = s.replace(
'''DB_NUMERIC = {
    'smallint': 'i32', 'integer': 'i32', 'bigint': 'i64',
    'real': 'f32', 'double precision': 'f64', 'numeric': 'f64',
    'boolean': 'bool',
}


def db_numeric_rust(db_type: str, nullable: bool) -> str:
    base = DB_NUMERIC[db_type]
    return ('Option<%s>' % base) if nullable else base
''',
'''DB_NUMERIC = {
    'smallint': 'JInt', 'integer': 'JInt', 'bigint': 'JLong',
    'real': 'JFloat', 'double precision': 'JFloat', 'numeric': 'JFloat',
}


def db_numeric_rust(db_type: str, nullable: bool) -> str:
    return DB_NUMERIC[db_type]
''')
s = s.replace(
'''        elif db_type is not None:
            # 文本/时间类型继续沿用 Go 侧语义（JString / Day / JDateTime）
            rust_ty = rust_type(f['go_type'], nullable)''',
'''        elif db_type is not None:
            # 文本/时间类型继续沿用 Go 侧语义（JString / Day / JDateTime）
            if db_type in ('date', 'timestamp without time zone', 'timestamp with time zone'):
                rust_ty = 'Day' if 'Day' in f['go_type'] else 'JDateTime'
            else:
                rust_ty = 'JString' if nullable or f['go_type'].startswith('string') else 'String\'''')

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('rewritten mod block 2')
