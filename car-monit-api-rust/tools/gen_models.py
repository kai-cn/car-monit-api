#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 car-monit-api-go/internal/model/*.go 的结构体定义转换为 Rust 模型。
Go 侧模型与 Java 实体已逐一核对（README 9.3：30 类 / 901 字段一一相等），
因此这里只做「类型 + tag」的机械转换，不改变字段语义。

用法: python tools/gen_models.py <go_model_dir> <out_dir>
"""
import os
import re
import sys

FIELD_RE = re.compile(r'^\s+([A-Z][A-Za-z0-9_]*)\s+(\S+)\s+`([^`]*)`')

TYPE_MAP = {
    'string': 'String',
    '*int': 'Option<i32>',
    '*int32': 'Option<i32>',
    '*int64': 'Option<i64>',
    '*float64': 'Option<f64>',
    '*float32': 'Option<f32>',
    '*bool': 'Option<bool>',
    '*Day': 'Option<Day>',
    'Day': 'Day',
    '*time.Time': 'Option<DateTime<Utc>>',
    'time.Time': 'Option<DateTime<Utc>>',
    '*Timestamp': 'Option<JDateTime>',
    'Timestamp': 'JDateTime',
    '*DateTime': 'Option<JDateTime>',
    'DateTime': 'JDateTime',
    '[]string': 'Vec<String>',
}


def snake(name: str) -> str:
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower()


def rust_field_name(name: str) -> str:
    n = snake(name)
    if n in {'type', 'ref', 'match', 'move', 'box', 'async', 'await', 'loop', 'return', 'self', 'super', 'crate', 'use', 'fn', 'impl', 'trait', 'dyn', 'in', 'as', 'where', 'for', 'if', 'else', 'enum', 'struct', 'const', 'static', 'let', 'mut', 'pub', 'mod'}:
        return 'r#' + n
    return n


def parse_tags(tag: str):
    json_name = None
    column = None
    transient = False
    primary = False
    m = re.search(r'json:"([^"]*)"', tag)
    if m:
        json_name = m.group(1).split(',')[0]
        if json_name == '-':
            json_name = None
    m = re.search(r'gorm:"([^"]*)"', tag)
    if m:
        g = m.group(1)
        if g.strip() == '-':
            transient = True
        cm = re.search(r'column:([^;"]+)', g)
        if cm:
            column = cm.group(1)
        primary = 'primaryKey' in g
    return json_name, column, transient, primary


JAVA_DIR = '../pro-business-api/src/main/java/com/ruoyi/base/domain'
JAVA_FIELDS = {}


def load_java_fields():
    """解析 Java 实体字段：类型 + @JsonFormat(pattern) —— 这是 JSON 行为的最终依据。"""
    import glob
    pat = re.compile(r'^\s*(?:(?:private|protected|public)\s+)?([\w<>,\. ]+?)\s+(\w+)\s*;')
    for path in glob.glob(os.path.join(JAVA_DIR, '*.java')):
        cls = os.path.basename(path)[:-5]
        pending = []
        for line in open(path, encoding="utf-8"):
            st = line.strip()
            if st.startswith('@'):
                pending.append(st)
                continue
            m = pat.match(line)
            if m:
                jt = re.sub(r'\s+', '', m.group(1))
                JAVA_FIELDS[(cls, m.group(2))] = {'java_type': jt, 'annotations': ' '.join(pending)}
                pending = []
            elif st.endswith(';') or st.endswith('{') or st.endswith('}'):
                pending = []


def choose_type(model, f, db_type, nullable):
    gn = f['go_name']
    jf = JAVA_FIELDS.get((model, gn)) or JAVA_FIELDS.get((model, gn[:1].lower() + gn[1:]))
    if jf:
        t = jf['java_type']
        ann = jf['annotations']
        if t == 'String':
            return 'String' if (f['column'] and not nullable) else 'JString'
        if t in ('Integer', 'int', 'Short', 'short'):
            return 'JInt'
        if t in ('Long', 'long'):
            return 'JLong'
        if t in ('BigDecimal', 'Double', 'double', 'Float', 'float'):
            return 'JFloat'
        if t in ('Boolean', 'boolean'):
            return 'JBool'
        if t in ('Date', 'java.util.Date', 'Timestamp', 'java.sql.Timestamp'):
            m = re.search(r'pattern\s*=\s*"([^"]+)"', ann)
            pattern = m.group(1) if m else ''
            if pattern == 'yyyy-MM-dd':
                return 'Day'
            if pattern and 'HH' in pattern:
                return 'JDateTime'
            return 'JIsoDateTime'
        if t.startswith('List<'):
            inner = t[5:-1]
            if inner in ('String', 'Integer', 'Long'):
                inner = 'String'
            return 'JList<%s>' % inner
        if t.startswith('Map'):
            return 'serde_json::Value'
    # 没有 Java 元数据时按数据库类型/Go 类型退化
    if db_type in DB_NUMERIC:
        return db_numeric_rust(db_type, nullable)
    if db_type is not None:
        if db_type in ('date', 'timestamp without time zone', 'timestamp with time zone'):
            return 'Day' if 'Day' in f['go_type'] else 'JDateTime'
        return 'JString' if nullable or f['go_type'].startswith('string') else 'String'
    if model == 'DwdLcztFwqjcxx' and f['go_type'].startswith('string'):
        return 'JString'
    return rust_type(f['go_type'], False)


SCHEMA = {}


def load_schema(path):
    import csv
    if not path or not os.path.exists(path):
        return
    for row in csv.reader(open(path, encoding='utf-8')):
        if len(row) == 4:
            SCHEMA[(row[0], row[1])] = (row[2], row[3])


DB_NUMERIC = {
    'smallint': 'JInt', 'integer': 'JInt', 'bigint': 'JLong',
    'real': 'JFloat', 'double precision': 'JFloat', 'numeric': 'JFloat',
}


def db_numeric_rust(db_type: str, nullable: bool) -> str:
    return DB_NUMERIC[db_type]


def rust_type(go_type: str, nullable: bool = False) -> str:
    if nullable:
        if go_type == 'string':
            return 'JString'
        if go_type == 'int':
            return 'Option<i32>'
        if go_type == 'int64':
            return 'Option<i64>'
        if go_type == 'float64':
            return 'Option<f64>'
        if go_type == 'bool':
            return 'Option<bool>'
        if go_type == 'Day':
            return 'Option<Day>'
        if go_type in ('Timestamp', 'DateTime'):
            return 'Option<JDateTime>'
    if go_type in TYPE_MAP:
        return TYPE_MAP[go_type]
    if go_type.startswith('[]'):
        inner = go_type[2:]
        return f'Vec<{inner}>'
    if go_type.startswith('*'):
        inner = go_type[1:]
        return f'Option<Box<{inner}>>'
    return 'serde_json::Value'


def parse_structs(path):
    text = open(path, encoding='utf-8').read()
    out = []
    for m in re.finditer(r'type\s+(\w+)\s+struct\s*\{(.*?)\n\}', text, re.S):
        name, body = m.group(1), m.group(2)
        fields = []
        for line in body.splitlines():
            fm = FIELD_RE.match(line)
            if not fm:
                continue
            fname, ftype, tags = fm.group(1), fm.group(2), fm.group(3)
            jn, col, transient, primary = parse_tags(tags)
            fields.append({
                'go_name': fname, 'go_type': ftype, 'json': jn,
                'column': col, 'transient': transient, 'primary': primary,
            })
        if fields:
            out.append((name, fields))
    # 表名 / schema
    tables = {}
    for tm in re.finditer(r'func\s+\(\s*(?:\w+\s+)?(\w+)\s*\)\s+TableName\(\)\s+string\s*\{\s*return\s+"([^"]+)"', text):
        tables[tm.group(1)] = tm.group(2)
    schemas = {}
    for tm in re.finditer(r'func\s+\(\s*(?:\w+\s+)?(\w+)\s*\)\s+Schema\(\)\s+string\s*\{\s*return\s+"([^"]+)"', text):
        schemas[tm.group(1)] = tm.group(2)
    return out, tables, schemas


def gen_file(name, fields, table, schema, src, nullability=None):
    lines = []
    lines.append('// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/%s.java' % name)
    lines.append('// 职责: %s —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。' % name)
    lines.append('// 对应 Go 文件: internal/model/%s.go（已与 Java 逐字段核对）' % snake(name))
    if table:
        lines.append('// 表: %s（schema=%s）' % (table, schema or ''))
    lines.append('// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。')
    lines.append('#![allow(non_snake_case, unused_imports)]')
    lines.append('')
    lines.append('use chrono::{DateTime, Utc};')
    lines.append('use serde::{Deserialize, Serialize};')
    lines.append('')
    lines.append('use super::*;')
    lines.append('')
    lines.append('#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]')
    lines.append('#[serde(default)]')
    lines.append('pub struct %s {' % name)
    for f in fields:
        rust_name = rust_field_name(f['go_name'])
        json_name = f['json'] or snake(f['go_name'])
        attrs = []
        if f['column']:
            if f['column'] != rust_name:
                attrs.append('#[sqlx(rename = "%s")]' % f['column'])
            attrs.append('#[sqlx(default)]')
        else:
            attrs.append('#[sqlx(skip)]')
        if json_name != rust_name:
            attrs.append('#[serde(rename = "%s")]' % json_name)
        if attrs:
            lines.append('    ' + ' '.join(attrs))
        db_type, nullable = (None, False)
        if f['column'] and f['column'] in (nullability or {}):
            db_type, nullable = (nullability or {})[f['column']]
        rust_ty = choose_type(name, f, db_type, nullable)
        lines.append('    pub %s: %s,' % (rust_name, rust_ty))
    lines.append('}')
    lines.append('')
    if table:
        if schema:
            lines.append('impl %s {' % name)
            lines.append('    /// 对应 Java @TableName(value = "%s", schema = "%s")。' % (table.split('.')[-1], schema))
            lines.append('    pub const TABLE: &\'static str = "%s";' % table)
            lines.append('    pub const SCHEMA: &\'static str = "%s";' % schema)
            pk = next((f['column'] for f in fields if f['primary']), None)
            if pk:
                lines.append('    pub const PK: &\'static str = "%s";' % pk)
            lines.append('}')
            lines.append('')
    return '\n'.join(lines)


def main():
    src_dir, out_dir = sys.argv[1], sys.argv[2]
    load_schema(sys.argv[3] if len(sys.argv) > 3 else '')
    load_java_fields()
    os.makedirs(out_dir, exist_ok=True)
    mods = []
    for fn in sorted(os.listdir(src_dir)):
        if not fn.endswith('.go'):
            continue
        structs, tables, schemas = parse_structs(os.path.join(src_dir, fn))
        if not structs:
            continue
        chunks = []
        for name, fields in structs:
            table = tables.get(name)
            short = table.split('.')[-1] if table else None
            nullability = {c: v for (t, c), v in SCHEMA.items() if t == short}
            chunks.append(gen_file(name, fields, table, schemas.get(name), fn, nullability))
            mods.append(snake(name))
        out_name = snake(fn[:-3]) + '.rs'
        with open(os.path.join(out_dir, out_name), 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(chunks))
    with open(os.path.join(out_dir, 'mod.rs'), 'w', encoding='utf-8', newline='\n') as f:
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
        matches!(
            sqlx::TypeInfo::name(ty),
            "VARCHAR" | "TEXT" | "BPCHAR" | "CHAR" | "NAME"
                | "INT2" | "INT4" | "INT8" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" | "FLOAT4" | "FLOAT8" | "NUMERIC"
                | "TIMESTAMP" | "TIMESTAMPTZ" | "DATE"
                | "TEXT[]" | "VARCHAR[]" | "BPCHAR[]"
        )
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JString {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JString(None)); }
        let ty_name = TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()).to_string();
        let out = match ty_name.as_str() {
            "INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => <i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "INT4" => <i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "INT8" => <i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "FLOAT4" => <f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "FLOAT8" => <f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
            "NUMERIC" => <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),
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
                format!("{{{}}}", arr.into_iter().map(|x| x.unwrap_or_default()).collect::<Vec<_>>().join(","))
            }
            _ => <String as sqlx::Decode<sqlx::Postgres>>::decode(v)?,
        };
        Ok(JString(Some(out)))
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
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(Day(None)); }
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
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JDateTime(None)); }
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
        matches!(sqlx::TypeInfo::name(ty), "INT2" | "INT4" | "INT8" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" | "FLOAT4" | "FLOAT8" | "NUMERIC")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JInt {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JInt(None)); }
        match TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()) {
            "INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Ok(JInt(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
            "INT4" => Ok(JInt(Some(<i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)?))),
            "INT8" => Ok(JInt(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
            "FLOAT4" => Ok(JInt(Some(<f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
            "FLOAT8" => Ok(JInt(Some(<f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),
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
        matches!(sqlx::TypeInfo::name(ty), "INT2" | "INT4" | "INT8" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" | "FLOAT4" | "FLOAT8" | "NUMERIC")
    }
}
impl<'r> sqlx::Decode<'r, sqlx::Postgres> for JLong {
    fn decode(v: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync + 'static>> {
        use sqlx::TypeInfo;
        if sqlx::ValueRef::is_null(&v) { return Ok(JLong(None)); }
        match TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()) {
            "INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Ok(JLong(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),
            "INT4" => Ok(JLong(Some(<i32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),
            "INT8" => Ok(JLong(Some(<i64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?))),
            "FLOAT4" => Ok(JLong(Some(<f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),
            "FLOAT8" => Ok(JLong(Some(<f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),
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
        match TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()) {
            "FLOAT4" => Ok(JFloat(Some(<f32 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64))),
            "FLOAT8" => Ok(JFloat(Some(<f64 as sqlx::Decode<sqlx::Postgres>>::decode(v)?))),
            "NUMERIC" => {
                use bigdecimal::ToPrimitive;
                let d = <bigdecimal::BigDecimal as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
                Ok(JFloat(d.to_f64()))
            }
            "INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Ok(JFloat(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64))),
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
        f.write(r"""
// Java List 可为 null：JList 用 present 区分“null”与“显式空数组 []”。
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct JList<T> {
    pub value: Vec<T>,
    pub present: bool,
}

impl<T> std::ops::Deref for JList<T> {
    type Target = Vec<T>;
    fn deref(&self) -> &Vec<T> { &self.value }
}
impl<T> std::ops::DerefMut for JList<T> {
    fn deref_mut(&mut self) -> &mut Vec<T> { &mut self.value }
}
impl<T> Default for JList<T> { fn default() -> Self { JList { value: Vec::new(), present: false } } }
impl<T> From<Vec<T>> for JList<T> { fn from(v: Vec<T>) -> Self { JList { value: v, present: true } } }
impl<T> FromIterator<T> for JList<T> {
    fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self {
        JList { value: iter.into_iter().collect(), present: true }
    }
}
impl<T: Serialize> Serialize for JList<T> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        if self.present { self.value.serialize(s) } else { s.serialize_none() }
    }
}
impl<'de, T: Deserialize<'de>> Deserialize<'de> for JList<T> {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        match Option::<Vec<T>>::deserialize(d)? {
            None => Ok(JList::default()),
            Some(v) => Ok(JList { value: v, present: true }),
        }
    }
}

""")
        f.write(r"""
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
        let ty_name = TypeInfo::name(sqlx::ValueRef::type_info(&v).as_ref()).to_string();
        let t = <DateTime<Utc> as sqlx::Decode<sqlx::Postgres>>::decode(v)?;
        let t = if ty_name.as_str() == "TIMESTAMPTZ" { t } else { t - chrono::Duration::hours(8) };
        Ok(JIsoDateTime(Some(t)))
    }
}
impl<'q> sqlx::Encode<'q, sqlx::Postgres> for JIsoDateTime {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync + 'static>> {
        <Option<DateTime<Utc>> as sqlx::Encode<sqlx::Postgres>>::encode(self.0, buf)
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
    print('generated %d structs into %s' % (len(mods), out_dir))


if __name__ == '__main__':
    main()
