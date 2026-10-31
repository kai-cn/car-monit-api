import io

p = 'tools/gen_models.py'
s = io.open(p, encoding='utf-8').read()

# 1) add schema parsing + nullable-aware type mapping
s = s.replace(
'''def rust_type(go_type: str) -> str:
    if go_type in TYPE_MAP:
        return TYPE_MAP[go_type]
    if go_type.startswith('[]'):
        inner = go_type[2:]
        return f'Vec<{inner}>'
    if go_type.startswith('*'):
        inner = go_type[1:]
        return f'Option<Box<{inner}>>'
    return 'serde_json::Value'
''',
'''SCHEMA = {}


def load_schema(path):
    import csv
    if not path or not os.path.exists(path):
        return
    for row in csv.reader(open(path, encoding='utf-8')):
        if len(row) == 4:
            SCHEMA[(row[0], row[1])] = row[3]


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
''')

# 2) pass table/nullability into gen_file
s = s.replace(
'''def gen_file(name, fields, table, schema, src):''',
'''def gen_file(name, fields, table, schema, src, nullable_cols=None):''')
s = s.replace(
'''        lines.append('    pub %s: %s,' % (rust_name, rust_type(f['go_type'])))''',
'''        nullable = bool(f['column']) and (
            (f['column'] in (nullable_cols or set()))
            or (name == 'DwdLcztFwqjcxx' and f['go_type'].startswith('string'))
        )
        lines.append('    pub %s: %s,' % (rust_name, rust_type(f['go_type'], nullable)))''')

# 3) fix TableName regex + compute nullable set per table
s = s.replace(
'''    for tm in re.finditer(r'func\\s+\\(\\w*\\s*(\\w+)\\)\\s+TableName\\(\\)\\s+string\\s*\\{\\s*return\\s+"([^"]+)"', text):
        tables[tm.group(1)] = tm.group(2)
    schemas = {}
    for tm in re.finditer(r'func\\s+\\(\\w*\\s*(\\w+)\\)\\s+Schema\\(\\)\\s+string\\s*\\{\\s*return\\s+"([^"]+)"', text):
        schemas[tm.group(1)] = tm.group(2)''',
'''    for tm in re.finditer(r'func\\s+\\(\\s*(?:\\w+\\s+)?(\\w+)\\s*\\)\\s+TableName\\(\\)\\s+string\\s*\\{\\s*return\\s+"([^"]+)"', text):
        tables[tm.group(1)] = tm.group(2)
    schemas = {}
    for tm in re.finditer(r'func\\s+\\(\\s*(?:\\w+\\s+)?(\\w+)\\s*\\)\\s+Schema\\(\\)\\s+string\\s*\\{\\s*return\\s+"([^"]+)"', text):
        schemas[tm.group(1)] = tm.group(2)''')

# 4) main: load schema arg and compute nullable columns
s = s.replace(
'''    src_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)''',
'''    src_dir, out_dir = sys.argv[1], sys.argv[2]
    load_schema(sys.argv[3] if len(sys.argv) > 3 else '')
    os.makedirs(out_dir, exist_ok=True)''')
s = s.replace(
'''        for name, fields in structs:
            chunks.append(gen_file(name, fields, tables.get(name), schemas.get(name), fn))''',
'''        for name, fields in structs:
            table = tables.get(name)
            short = table.split('.')[-1] if table else None
            nullable_cols = {c for (t, c), flag in SCHEMA.items() if t == short and flag == 'YES'}
            chunks.append(gen_file(name, fields, table, schemas.get(name), fn, nullable_cols))''')

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('generator patched')
