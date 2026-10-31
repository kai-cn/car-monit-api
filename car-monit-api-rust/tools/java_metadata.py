import io

p = 'tools/gen_models.py'
s = io.open(p, encoding='utf-8').read()

# 1) Java 元数据解析器
insert_at = s.index('SCHEMA = {}')
java_parser = r'''JAVA_DIR = '../pro-business-api/src/main/java/com/ruoyi/base/domain'
JAVA_FIELDS = {}


def load_java_fields():
    """解析 Java 实体字段：类型 + @JsonFormat(pattern) —— 这是 JSON 行为的最终依据。"""
    import glob
    pat = re.compile(r'^\s*(?:private|protected|public)\s+([\w<>,\. ]+?)\s+(\w+)\s*;')
    for path in glob.glob(os.path.join(JAVA_DIR, '*.java')):
        cls = os.path.basename(path)[:-5]
        pending = []
        for line in io.open(path, encoding='utf-8'):
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
    jf = JAVA_FIELDS.get((model, f['go_name']))
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
            return 'Option<Vec<String>>' if 'String' in t else 'Option<Vec<serde_json::Value>>'
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


'''
s = s[:insert_at] + java_parser + s[insert_at:]

# 2) gen_file 使用 choose_type
old = '''        db_type, nullable = (None, False)
        if f['column'] and f['column'] in (nullability or {}):
            db_type, nullable = (nullability or {})[f['column']]
        rust_ty = None
        if db_type in DB_NUMERIC:
            rust_ty = db_numeric_rust(db_type, nullable)
        elif db_type is not None:
            # 文本/时间类型继续沿用 Go 侧语义（JString / Day / JDateTime）
            if db_type in ('date', 'timestamp without time zone', 'timestamp with time zone'):
                rust_ty = 'Day' if 'Day' in f['go_type'] else 'JDateTime'
            else:
                rust_ty = 'JString' if nullable or f['go_type'].startswith('string') else 'String'
        elif name == 'DwdLcztFwqjcxx' and f['go_type'].startswith('string'):
            rust_ty = 'JString'
        else:
            rust_ty = rust_type(f['go_type'], False)
        lines.append('    pub %s: %s,' % (rust_name, rust_ty))'''
new = '''        db_type, nullable = (None, False)
        if f['column'] and f['column'] in (nullability or {}):
            db_type, nullable = (nullability or {})[f['column']]
        rust_ty = choose_type(name, f, db_type, nullable)
        lines.append('    pub %s: %s,' % (rust_name, rust_ty))'''
if old not in s:
    print('MISS gen_file block')
s = s.replace(old, new)

# 3) main 调用 load_java_fields
s = s.replace('''    load_schema(sys.argv[3] if len(sys.argv) > 3 else '')''',
'''    load_schema(sys.argv[3] if len(sys.argv) > 3 else '')
    load_java_fields()''')

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('java metadata patched')
