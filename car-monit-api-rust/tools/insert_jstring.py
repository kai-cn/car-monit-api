import io

p = 'tools/gen_models.py'
lines = io.open(p, encoding='utf-8').read().split('\n')
idx = next(i for i, l in enumerate(lines) if "对应 Java 的 DateUtils.parseDate" in l and l.strip().startswith("f.write"))
rust = r'''        f.write(r"""// Java 的 String 可为 null：JString 保留 null 语义，同时 Deref 到 str 便于直接使用。
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct JString(pub Option<String>);

impl JString {
    pub fn as_str(&self) -> &str { self.0.as_deref().unwrap_or("") }
    pub fn is_null(&self) -> bool { self.0.is_none() }
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
}

impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JString {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        Ok(JString(<Option<String> as sqlx::Decode<sqlx::Postgres>>::decode(v)?))
    }
}

impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JString {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<String> as sqlx::Encode<sqlx::Postgres>>::encode(self.0.clone(), buf)
    }
}

""")
'''
lines.insert(idx, rust.rstrip('\n'))
io.open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
print('inserted')
