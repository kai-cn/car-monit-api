import io

p = 'tools/gen_models.py'
s = io.open(p, encoding='utf-8').read()

# --- JString: 兼容数值列（Java String 字段映射数值列） ---
s = s.replace(
'''        matches!(sqlx::TypeInfo::name(ty), "VARCHAR" | "TEXT" | "BPCHAR" | "CHAR" | "NAME")''',
'''        matches!(
            sqlx::TypeInfo::name(ty),
            "VARCHAR" | "TEXT" | "BPCHAR" | "CHAR" | "NAME"
                | "INT2" | "INT4" | "INT8" | "FLOAT4" | "FLOAT8" | "NUMERIC"
        )''')
s = s.replace(
'''        if sqlx::ValueRef::is_null(&v) { return Ok(JString(None)); }
        Ok(JString(Some(<String as sqlx::Decode<sqlx::Postgres>>::decode(v)?)))''',
'''        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JString(None)); }
        let ty = sqlx::ValueRef::type_info(&v);
        let out = match TypeInfo::name(ty.as_ref()) {
            "INT2" => <i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "INT4" => <i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "INT8" => <i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "FLOAT4" => <f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "FLOAT8" => <f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "NUMERIC" => <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            _ => <String as sqlx::Decode<sqlx::Postgres>>::decode(v)?,
        };
        Ok(JString(Some(out)))''')

# --- JInt 支持浮点/数值（Java Integer 截断） ---
s = s.replace(
'''        matches!(sqlx::TypeInfo::name(ty), "INT2" | "INT4" | "INT8")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JInt {''',
'''        matches!(sqlx::TypeInfo::name(ty), "INT2" | "INT4" | "INT8" | "FLOAT4" | "FLOAT8" | "NUMERIC")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JInt {''')
s = s.replace(
'''            "INT8" => Ok(JInt(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
            other => Err(format!("JInt 不支持的类型 {}", other).into()),''',
'''            "INT8" => Ok(JInt(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
            "FLOAT4" => Ok(JInt(Some(<f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
            "FLOAT8" => Ok(JInt(Some(<f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
            "NUMERIC" => {
                use bigdecimal::ToPrimitive;
                let d = <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                Ok(JInt(d.to_i32()))
            }
            other => Err(format!("JInt 不支持的类型 {}", other).into()),''')

# --- JLong 支持浮点/数值 ---
s = s.replace(
'''        matches!(sqlx::TypeInfo::name(ty), "INT2" | "INT4" | "INT8")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JLong {''',
'''        matches!(sqlx::TypeInfo::name(ty), "INT2" | "INT4" | "INT8" | "FLOAT4" | "FLOAT8" | "NUMERIC")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JLong {''')
s = s.replace(
'''            "INT8" => Ok(JLong(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?))),
            other => Err(format!("JLong 不支持的类型 {}", other).into()),''',
'''            "INT8" => Ok(JLong(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?))),
            "FLOAT4" => Ok(JLong(Some(<f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),
            "FLOAT8" => Ok(JLong(Some(<f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),
            "NUMERIC" => {
                use bigdecimal::ToPrimitive;
                let d = <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                Ok(JLong(d.to_i64()))
            }
            other => Err(format!("JLong 不支持的类型 {}", other).into()),''')

# --- Day/JDateTime/JIsoDateTime: TIMESTAMP/DATE 视为 +08 墙钟，转 UTC ---
tz_helper = '''        fn to_utc(ty_name: &str, t: DateTime<Utc>) -> DateTime<Utc> {
            if ty_name == "TIMESTAMPTZ" {
                t
            } else {
                // Java JDBC: serverTimezone=Asia/Shanghai；Jackson 默认按 UTC 输出
                t - chrono::Duration::hours(8)
            }
        }
'''
s = s.replace('''impl<'r> sqlx::Decode<'r, sqlx::Postgres> for Day {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        if sqlx::ValueRef::is_null(&v) { return Ok(Day(None)); }
        Ok(Day(Some(<DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?)))
    }
}''','''impl<'r> sqlx::Decode<'r, sqlx::Postgres> for Day {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(Day(None)); }
        let ty = sqlx::ValueRef::type_info(&v);
        let t = <DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
''' + tz_helper + '''        Ok(Day(Some(to_utc(TypeInfo::name(ty.as_ref()), t))))
    }
}''')
s = s.replace('''impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JDateTime {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        if sqlx::ValueRef::is_null(&v) { return Ok(JDateTime(None)); }
        Ok(JDateTime(Some(<DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?)))
    }
}''','''impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JDateTime {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JDateTime(None)); }
        let ty = sqlx::ValueRef::type_info(&v);
        let t = <DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
''' + tz_helper + '''        Ok(JDateTime(Some(to_utc(TypeInfo::name(ty.as_ref()), t))))
    }
}''')

# --- 新增 JBool / JIsoDateTime（插到 parse_model_time 之前） ---
extra = r'''
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JBool(pub Option<bool>);
impl From<bool> for JBool { fn from(v: bool) -> Self { JBool(Some(v)) } }
impl JBool { pub fn get(&self) -> Option<bool> { self.0 } }
impl Serialize for JBool {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.0 { Some(v) => s.serialize_bool(v), None => s.serialize_none() }
    }
}
impl<'de> Deserialize<'de> for JBool {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> { Ok(JBool(Option::<bool>::deserialize(d)?)) }
}
impl sqlx::Type<sqlx::Postgres> for JBool {
    fn type_info() -> sqlx::postgres::PgTypeInfo { <bool as sqlx::Type<sqlx::Postgres>>::type_info() }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool { sqlx::TypeInfo::name(ty) == "BOOL" }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JBool {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        if sqlx::ValueRef::is_null(&v) { return Ok(JBool(None)); }
        Ok(JBool(Some(<bool as sqlx::Decode<sqlx::Postgres>>::decode(v)?)))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JBool {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<bool> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

// 对应未加 @JsonFormat 的 java.util.Date：Spring Boot 默认 ISO-8601（UTC，毫秒 3 位）
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct JIsoDateTime(pub Option<DateTime<Utc>>);
impl From<DateTime<Utc>> for JIsoDateTime { fn from(v: DateTime<Utc>) -> Self { JIsoDateTime(Some(v)) } }
impl JIsoDateTime {
    pub fn utc(&self) -> Option<DateTime<Utc>> { self.0 }
    pub fn format_iso(&self) -> Option<String> {
        self.0.map(|t| t.format("%Y-%m-%dT%H:%M:%S%.3f+00:00").to_string())
    }
}
impl Serialize for JIsoDateTime {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self.format_iso() { Some(v) => s.serialize_str(&v), None => s.serialize_none() }
    }
}
impl<'de> Deserialize<'de> for JIsoDateTime {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Option::<String>::deserialize(d)?;
        match v {
            None => Ok(JIsoDateTime(None)),
            Some(s) => crate::utils::parse_time(&s).map(|t| JIsoDateTime(Some(t))).map_err(serde::de::Error::custom),
        }
    }
}
impl sqlx::Type<sqlx::Postgres> for JIsoDateTime {
    fn type_info() -> sqlx::postgres::PgTypeInfo { <DateTime<Utc> as sqlx::Type<sqlx::Postgres>>::type_info() }
    fn compatible(ty: &sqlx::postgres::PgTypeInfo) -> bool {
        matches!(sqlx::TypeInfo::name(ty), "TIMESTAMP" | "TIMESTAMPTZ" | "DATE")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JIsoDateTime {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JIsoDateTime(None)); }
        let ty = sqlx::ValueRef::type_info(&v);
        let t = <DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
        let t = if TypeInfo::name(ty.as_ref()) == "TIMESTAMPTZ" { t } else { t - chrono::Duration::hours(8) };
        Ok(JIsoDateTime(Some(t)))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JIsoDateTime {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<DateTime<Utc>> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
    }
}

'''
s = s.replace('''        f.write('/// 对应 Java 的 DateUtils.parseDate：供模型反序列化使用。\\n')''',
              '''        f.write(r"""''' + extra + '''""")
        f.write('/// 对应 Java 的 DateUtils.parseDate：供模型反序列化使用。\\n')''')

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('scalar types patched')
