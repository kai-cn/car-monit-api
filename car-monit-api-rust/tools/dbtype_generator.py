import io

p = 'tools/gen_models.py'
s = io.open(p, encoding='utf-8').read()

s = s.replace(
'''    for row in csv.reader(open(path, encoding='utf-8')):
        if len(row) == 4:
            SCHEMA[(row[0], row[1])] = row[3]''',
'''    for row in csv.reader(open(path, encoding='utf-8')):
        if len(row) == 4:
            SCHEMA[(row[0], row[1])] = (row[2], row[3])''')

s = s.replace(
'''def rust_type(go_type: str, nullable: bool = False) -> str:
    if nullable:''',
'''DB_NUMERIC = {
    'smallint': 'i32', 'integer': 'i32', 'bigint': 'i64',
    'real': 'f32', 'double precision': 'f64', 'numeric': 'f64',
    'boolean': 'bool',
}


def db_numeric_rust(db_type: str, nullable: bool) -> str:
    base = DB_NUMERIC[db_type]
    return ('Option<%s>' % base) if nullable else base


def rust_type(go_type: str, nullable: bool = False) -> str:
    if nullable:''')

s = s.replace(
'''        nullable = bool(f['column']) and (
            (f['column'] in (nullable_cols or set()))
            or (name == 'DwdLcztFwqjcxx' and f['go_type'].startswith('string'))
        )
        lines.append('    pub %s: %s,' % (rust_name, rust_type(f['go_type'], nullable)))''',
'''        db_type, nullable = (None, False)
        if f['column'] and f['column'] in (nullability or {}):
            db_type, nullable = (nullability or {})[f['column']]
        rust_ty = None
        if db_type in DB_NUMERIC:
            rust_ty = db_numeric_rust(db_type, nullable)
        elif db_type is not None:
            # 文本/时间类型继续沿用 Go 侧语义（JString / Day / JDateTime）
            rust_ty = rust_type(f['go_type'], nullable)
        elif name == 'DwdLcztFwqjcxx' and f['go_type'].startswith('string'):
            rust_ty = 'JString'
        else:
            rust_ty = rust_type(f['go_type'], False)
        lines.append('    pub %s: %s,' % (rust_name, rust_ty))''')

s = s.replace(
'''            nullable_cols = {c for (t, c), flag in SCHEMA.items() if t == short and flag == 'YES'}
            chunks.append(gen_file(name, fields, table, schemas.get(name), fn, nullable_cols))''',
'''            nullability = {c: v for (t, c), v in SCHEMA.items() if t == short}
            chunks.append(gen_file(name, fields, table, schemas.get(name), fn, nullability))''')

s = s.replace(
'''def gen_file(name, fields, table, schema, src, nullable_cols=None):''',
'''def gen_file(name, fields, table, schema, src, nullability=None):''')

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('patched db types')
