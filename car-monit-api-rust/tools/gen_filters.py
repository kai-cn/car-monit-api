# -*- coding: utf-8 -*-
"""从 MyBatis XML 的 select...List 条件生成 Rust 过滤器（逐字段、逐操作符）。

生成规则（与 XML 保持一一对应）：
  - `and t.col = #{f}`          -> Cond::Eq / EqI64 / EqF64（按实体字段类型）
  - `and t.col like concat(...)`-> Cond::Like
  - `and t.col >= to_timestamp` -> Cond::Gte / Lte
  - `and <foreach ...> t.col = #{item}</foreach>` -> Cond::In
  - 字面量条件（如 flag == 'JiAnDong'）与 LIMIT/OFFSET 不生成过滤条件

注意：列名严格使用 XML 中写的物理列名（不去 snake_case 化）。某些 XML 条件引用了
数据库里不存在的别名列（例如服务区表的 agent_pk），Java 在这些过滤条件下会 500，
Rust 使用同一列名时也会得到同样的数据库错误，从而保持行为一致。
"""
import glob
import io
import os
import re

JAVA_XML = '../pro-business-api/src/main/java/com/ruoyi/base/mapper/xml'
MODEL_DIR = 'src/models'
SCHEMA_CSV = '.run/schema.csv'
OUT = 'src/repo/filters_gen.rs'

# XML 文件 → (Rust 模型, 生成的过滤器函数名)
MAPPING = {
    'OdsRtSzdnSnapshotFlowAddcodeMapper.xml': ('OdsRtSzdnSnapshotFlowAddcode', 'snapshot_filters'),
    'DwdLcztSfsjcxxMapper.xml': ('DwdLcztSfsjcxx', 'sfsj_filters'),
    'DwdLcztSfzjcxxMapper.xml': ('DwdLcztSfzjcxx', 'sfzj_filters'),
    'DwdLcztFwqjcxxMapper.xml': ('DwdLcztFwqjcxx', 'fwq_filters'),
    'OdsCxztFwqcllsMapper.xml': ('OdsCxztFwqclls', 'fwqclls_filters'),
    'OdsLwzxsfsjFeeGantryFusion01Mapper.xml': ('OdsLwzxsfsjFeeGantryFusion01', 'fee_gantry_filters'),
    'OdsLwzxsfsjFeeStationEnter01Mapper.xml': ('OdsLwzxsfsjFeeStationEnter01', 'fee_enter_filters'),
    'OdsLwzxsfsjFeeStationExit01Mapper.xml': ('OdsLwzxsfsjFeeStationExit01', 'fee_exit_filters'),
    'OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.xml': ('OdsRtSzdnSnapshotFlowProvcaptureAddcode', 'prov_capture_filters'),
    'OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.xml': ('OdsRtSzdnSnapshotFlowStationcaptureAddcode', 'station_capture_filters'),
    'OdsSzdnGantryMapper.xml': ('OdsSzdnGantry', 'gantry_filters'),
    'OdsSzdnGantryIpMapper.xml': ('OdsSzdnGantryIp', 'gantry_ip_filters'),
    'OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.xml': ('OdsSzdnProvinceBorderVehicleWeightNewstructure', 'vehicle_weight_filters'),
    'OdsSzdnSectionMapper.xml': ('OdsSzdnSection', 'section_filters'),
    'OdsSzdnTollMapper.xml': ('OdsSzdnToll', 'toll_filters'),
    'OdsSzdnTollStationIpMapper.xml': ('OdsSzdnTollStationIp', 'toll_station_ip_filters'),
    'OdsYhglVBaseOrgMapper.xml': ('OdsYhglVBaseOrg', 'org_filters'),
    'ZdataLocationDictMapper.xml': ('ZdataLocationDict', 'location_dict_filters'),
    'ZdataTrailTracksMapper.xml': ('ZdataTrailTracks', 'trail_tracks_filters'),
}


def snake(name):
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower()


def norm(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def load_model(model):
    path = os.path.join(MODEL_DIR, snake(model) + '.rs')
    if not os.path.exists(path):
        return {}
    text = io.open(path, encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'pub (r#\w+|\w+): ([^,\n]+),', text):
        name = m.group(1).replace('r#', '')
        out[norm(name)] = (name, m.group(2).strip())
    return out


RUST_KEYWORDS = {'type', 'match', 'move', 'ref', 'self', 'crate', 'super', 'fn', 'let', 'loop', 'async', 'await', 'dyn', 'box'}


def access(name):
    return 'r#' + name if name in RUST_KEYWORDS else name


def value_expr(rust_name, ty):
    """构造传给 Cond 的字符串值：JString 已是 Cond 需要的类型，String 需要 into()。"""
    if ty == 'JString':
        return 'q.%s.clone()' % rust_name
    return 'q.%s.clone().into()' % rust_name


def emit_eq(field, column, model, fields, lines, like=False):
    entry = fields.get(norm(field))
    if not entry:
        lines.append('    // 跳过未在实体中定义的字段: %s' % field)
        return
    rust_name, ty = entry
    rust_name = access(rust_name)
    neg = '!q.%s.is_empty()' % rust_name
    if ty.startswith('JList<'):
        op = 'In'
        lines.append('    if %s {' % neg)
        lines.append('        v.push(Cond::In("%s", q.%s.iter().map(|x| x.to_string()).collect()));' % (column, rust_name))
        lines.append('    }')
        return
    if like:
        if ty in ('JString', 'String'):
            lines.append('    if %s {' % neg)
            lines.append('        v.push(Cond::Like("%s", %s));' % (column, value_expr(rust_name, ty)))
            lines.append('    }')
        else:
            lines.append('    // 非字符串字段不支持 LIKE: %s' % field)
        return
    if ty in ('JString', 'String'):
        lines.append('    if %s {' % neg)
        lines.append('        v.push(Cond::Eq("%s", %s));' % (column, value_expr(rust_name, ty)))
        lines.append('    }')
    elif ty in ('JInt', 'JLong'):
        lines.append('    if let Some(x) = q.%s.get() {' % rust_name)
        # JInt::get() 是 i32（需转 i64），JLong::get() 已是 i64（避免 clippy::unnecessary_cast）
        if ty == 'JInt':
            lines.append('        v.push(Cond::EqI64("%s", x as i64));' % column)
        else:
            lines.append('        v.push(Cond::EqI64("%s", x));' % column)
        lines.append('    }')
    elif ty in ('JFloat',):
        lines.append('    if let Some(x) = q.%s.get() {' % rust_name)
        lines.append('        v.push(Cond::EqF64("%s", x));' % column)
        lines.append('    }')
    elif ty in ('Day', 'JDateTime', 'JIsoDateTime'):
        # 核对 Java 侧：BaseController.initBinder 用 DateUtils.parseDate(text) 绑定所有 Date 字段
        # （@JsonFormat 只影响序列化）。"2026-10-31" 解析为当日 00:00:00，
        # "2026-10-31 12:34:56" 保留时分秒；因此 Day 也必须按实际时刻绑定，不能截断成日期。
        lines.append('    if let Some(t) = q.%s.utc() {' % rust_name)
        lines.append('        v.push(Cond::EqTimestamp("%s", crate::utils::format_datetime(&t).into()));' % column)
        lines.append('    }')
    elif ty in ('JBool',):
        lines.append('    if let Some(x) = q.%s.get() {' % rust_name)
        lines.append('        v.push(Cond::Eq("%s", x.to_string().into()));' % column)
        lines.append('    }')
    else:
        lines.append('    // 未支持的类型 %s: %s' % (ty, rust_name))


def emit_range(field, column, op, model, fields, lines):
    entry = fields.get(norm(field))
    if not entry:
        lines.append('    // 跳过未在实体中定义的字段: %s' % field)
        return
    rust_name, ty = entry
    rust_name = access(rust_name)
    neg = '!q.%s.is_empty()' % rust_name
    if ty in ('JString', 'String'):
        lines.append('    if %s {' % neg)
        lines.append('        v.push(Cond::%s("%s", %s));' % (op, column, value_expr(rust_name, ty)))
        lines.append('    }')
    elif ty in ('Day',):
        lines.append('    if let Some(t) = q.%s.utc() {' % rust_name)
        lines.append('        v.push(Cond::%s("%s", crate::utils::format_day(&t).into()));' % (op, column))
        lines.append('    }')
    elif ty in ('JDateTime', 'JIsoDateTime'):
        lines.append('    if let Some(t) = q.%s.utc() {' % rust_name)
        lines.append('        v.push(Cond::%s("%s", crate::utils::format_datetime(&t).into()));' % (op, column))
        lines.append('    }')
    else:
        lines.append('    // 不支持的时间字段类型 %s: %s' % (ty, field))


LITERAL_IF = re.compile(r"^(\w+)\s*!=\s*null\s+and\s+\1\s*==\s*'([^']+)'$")
LITERAL_THEN = re.compile(r"^\s*and\s+t\.(\w+)\s*=\s*'([^']+)'\s*$")


def parse_block(test, body):
    """返回 ('eq'|'like'|'gte'|'lte'|'in'|'literal'|'broken', ...)。"""
    # 形如 <if test="flag != null and flag == 'JiAnDong'"> and t.orgcode = '030000011'
    # MyBatis 的 OGNL 对多字符单引号串按字符串比较，是生效的（此前误判为未生效）。
    t = re.sub(r'\s+', ' ', test).strip()
    m = LITERAL_IF.match(t)
    if m:
        lit = LITERAL_THEN.match(re.sub(r'\s+', ' ', body))
        if lit:
            return ('literal', m.group(1), m.group(2), lit.group(1), lit.group(2))
    field_m = re.match(r'\s*(\w+)', test)
    if not field_m:
        return None
    field = field_m.group(1)
    if 'startNum' in body or 'endNum' in body:
        return None
    if '<foreach' in body:
        coll = re.search(r'collection="(\w+)"', body)
        col = re.search(r'(?:t\.)?(\w+)\s+in\b', body) or re.search(r't\.(\w+)\s*=', body)
        if coll and col:
            return ('in', coll.group(1), col.group(1))
        return None
    if 'to_timestamp' in body:
        col = re.search(r't\.(\w+)\s*(?:<!\[CDATA\[)?(>=|<=|>|<)', body)
        if col:
            op = 'Gte' if '>' in col.group(2) else 'Lte'
            return (op, field, col.group(1))
        return None
    like = re.search(r't\.(\w+)\s+like\b', body)
    if like:
        return ('like', field, like.group(1))
    eq = re.search(r't\.(\w+)\s*=\s*#\{(\w+)\}', body)
    if eq:
        if norm(eq.group(2)) != norm(field):
            # MyBatis 参数名与属性名不一致（如 sfsjcxx.agentPk -> #{id}）：
            # Java 运行期抛 BindingException -> 500，这里用不存在的列名复现同样的 500。
            return ('broken', field, eq.group(2))
        return ('eq', field, eq.group(1))
    return None


def main():
    result = ['// 由 tools/gen_filters.py 从 Mapper XML 自动生成，勿手改。',
              '// 每个 <if> 对应一条 Cond，操作符（=/LIKE/GTE/LTE/IN）逐字对齐 XML。',
              'use super::Cond;',
              'use crate::models::*;',
              '']
    total_fields = 0
    for fn, (model, func) in MAPPING.items():
        path = os.path.join(JAVA_XML, fn)
        if not os.path.exists(path):
            print('missing', path)
            continue
        xml = io.open(path, encoding='utf-8').read()
        m = re.search(r'<select id="\w*List"[^>]*>(.*?)</select>', xml, re.S)
        if not m:
            print('skip (no selectList)', fn)
            continue
        body = m.group(1)
        fields = load_model(model)
        lines = ['pub fn %s(q: &%s) -> Vec<Cond> {' % (func, model), '    let mut v = vec![];']
        seen = set()
        for tm in re.finditer(r'<if test="([^"]*)">(.*?)</if>', body, re.S):
            test, inner = tm.group(1), tm.group(2)
            parsed = parse_block(test, inner)
            if not parsed:
                continue
            op, field, column = parsed[0], parsed[1], parsed[2]
            key = (op, field, column)
            if key in seen:
                continue
            seen.add(key)
            if op == 'eq':
                emit_eq(field, column, model, fields, lines)
            elif op == 'like':
                emit_eq(field, column, model, fields, lines, like=True)
            elif op in ('Gte', 'Lte'):
                emit_range(field, column, op, model, fields, lines)
            elif op == 'in':
                emit_eq(field, column, model, fields, lines)
            elif op == 'literal':
                _, field, want, column, lit = parsed
                entry = fields.get(norm(field))
                rn = access(entry[0]) if entry else field
                lines.append('    // PARITY: XML 的 flag 字面量条件（OGNL 字符串比较生效）')
                lines.append('    if q.%s.as_str() == "%s" {' % (rn, want))
                lines.append('        v.push(Cond::Eq("%s", "%s".into()));' % (column, lit))
                lines.append('    }')
            elif op == 'broken':
                lines.append('    // PARITY: XML 引用了不存在的属性 #{%s}，Java 抛 BindingException -> 500。' % column)
                rn = access(fields.get(norm(field), (field, ''))[0])
                ty = fields.get(norm(field), (field, ''))[1]
                lines.append('    if !q.%s.is_empty() {' % rn)
                lines.append('        v.push(Cond::Eq("__mybatis_missing_property_%s__", %s));' % (column, value_expr(rn, ty)))
                lines.append('    }')
            total_fields += 1
        lines.append('    v')
        lines.append('}')
        lines.append('')
        result.extend(lines)
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(result))
    print('generated', OUT, 'conditions', total_fields)


if __name__ == '__main__':
    main()
