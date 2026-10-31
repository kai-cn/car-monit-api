import io
import re

def edit(p, pairs, regex=False):
    s = io.open(p, encoding='utf-8').read()
    for item in pairs:
        old, new = item[0], item[1]
        if regex:
            s, n = re.subn(old, new, s)
            if n == 0:
                print('MISS-RE', p, old[:70])
        else:
            if old not in s:
                print('MISS', p, old[:70].replace('\n', ' '))
            s = s.replace(old, new)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

# 1) JList: null vs empty[]
for p in ['src/models/mod.rs', 'tools/gen_models.py']:
    s = io.open(p, encoding='utf-8').read()
    old = '''#[derive(Debug, Clone, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct JList<T>(pub Vec<T>);

impl<T> std::ops::Deref for JList<T> {
    type Target = Vec<T>;
    fn deref(&self) -> &Vec<T> { &self.0 }
}
impl<T> std::ops::DerefMut for JList<T> {
    fn deref_mut(&mut self) -> &mut Vec<T> { &mut self.0 }
}
impl<T> From<Vec<T>> for JList<T> { fn from(v: Vec<T>) -> Self { JList(v) } }
impl<T> FromIterator<T> for JList<T> { fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self { JList(iter.into_iter().collect()) } }
impl<T: Serialize> Serialize for JList<T> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        if self.0.is_empty() { s.serialize_none() } else { self.0.serialize(s) }
    }
}
impl<'de, T: Deserialize<'de>> Deserialize<'de> for JList<T> {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        Ok(JList(Option::<Vec<T>>::deserialize(d)?.unwrap_or_default()))
    }
}'''
    new = '''#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct JList<T> {
    pub value: Vec<T>,
    pub present: bool,
}

impl<T> Default for JList<T> {
    fn default() -> Self { JList { value: Vec::new(), present: false } }
}
impl<T> std::ops::Deref for JList<T> {
    type Target = Vec<T>;
    fn deref(&self) -> &Vec<T> { &self.value }
}
impl<T> std::ops::DerefMut for JList<T> {
    fn deref_mut(&mut self) -> &mut Vec<T> { &mut self.value }
}
impl<T> From<Vec<T>> for JList<T> { fn from(v: Vec<T>) -> Self { JList { value: v, present: true } } }
impl<T> FromIterator<T> for JList<T> {
    fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self {
        JList { value: iter.into_iter().collect(), present: true }
    }
}
impl<T: Serialize> Serialize for JList<T> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        // Java: 未赋值的 List 为 null；显式传入/赋值的空 List 为 []。
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
}'''
    if old not in s:
        print('MISS JList block', p)
    s = s.replace(old, new)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

# JList .0 usages
edit('src/services/trail.rs', [
    ('trails.iter().flat_map(|t| t.trail_list.0.clone()).collect();',
     'trails.iter().flat_map(|t| t.trail_list.value.clone()).collect();'),
])

# 2) snapshot order
edit('src/repo/mod.rs', [
    ('"jl_data01.ods_rt_szdn_snapshot_flow_addcode",\n    "big_id",\n    SNAPSHOT_SELECT,\n    "",',
     '"jl_data01.ods_rt_szdn_snapshot_flow_addcode",\n    "big_id",\n    SNAPSHOT_SELECT,\n    "ORDER BY snapshottime DESC",'),
])

# 3) numeric fwqclls repo
edit('src/repo/mod.rs', [
    ('entity_repo!(FwqcllsRepo, OdsCxztFwqclls, "jl_data01.ods_cxzt_fwqclls", "big_id", "*", "", fwqclls_filters);',
     'entity_repo_numeric!(FwqcllsRepo, OdsCxztFwqclls, "jl_data01.ods_cxzt_fwqclls", "big_id", "*", "", fwqclls_filters);'),
])

# 4) pageSize<=0 semantics
p = 'src/handlers/common.rs'
s = io.open(p, encoding='utf-8').read()
s = s.replace('''pub struct PageParams {
    pub page_num: i64,
    pub page_size: i64,
}''', '''pub struct PageParams {
    pub page_num: i64,
    pub page_size: i64,
    /// PageHelper 语义：pageSize <= 0 时返回空列表（total 仍为匹配总数）。
    pub empty: bool,
}''')
s = s.replace('''    let page_num = q
        .page_num
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(1);
    let mut page_size = q
        .page_size
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(10);
    if page_size <= 0 {
        page_size = 10;
    }''', '''    let page_num = q
        .page_num
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(1);
    let parsed_size = q
        .page_size
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok());
    let empty = matches!(parsed_size, Some(n) if n <= 0);
    let mut page_size = parsed_size.filter(|n| *n > 0).unwrap_or(10);''')
s = s.replace('''    PageParams { page_num, page_size }
}''', '''    PageParams { page_num, page_size, empty }
}''')
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

# list/export impls respect empty
edit('src/handlers/crud.rs', [
    ('''    let p = page_params(page);
    let rows = repo.list(&q, p.page_size, p.offset()).await?;
    let total = repo.count(&q).await?;
    Ok(json_ok(TableDataInfo::new(serde_json::to_value(rows)?, total)))''',
     '''    let p = page_params(page);
    let rows = if p.empty { Vec::new() } else { repo.list(&q, p.page_size, p.offset()).await? };
    let total = repo.count(&q).await?;
    Ok(json_ok(TableDataInfo::new(serde_json::to_value(rows)?, total)))'''),
    ('''    let p = page_params(page);
    let rows = repo.list(&q, p.page_size, p.offset()).await?;
    Ok(json_ok(serde_json::to_value(rows)?))''',
     '''    let p = page_params(page);
    let rows = if p.empty { Vec::new() } else { repo.list(&q, p.page_size, p.offset()).await? };
    Ok(json_ok(serde_json::to_value(rows)?))'''),
])

# custom list handlers empty
edit('src/handlers/base.rs', [
    ('''    let p = page_params(&page);
    let mut rows = state.snapshot_flow.list(&q, p.page_size, p.offset()).await?;
    decorate_snapshot(&mut rows, true);
    let total = state.snapshot_flow.count(&q).await?;''',
     '''    let p = page_params(&page);
    let mut rows = if p.empty {
        Vec::new()
    } else {
        state.snapshot_flow.list(&q, p.page_size, p.offset()).await?
    };
    decorate_snapshot(&mut rows, true);
    let total = state.snapshot_flow.count(&q).await?;'''),
    ('''    let p = page_params(&page);
    let mut rows = state.snapshot_flow.list(&q, p.page_size, p.offset()).await?;
    // PARITY: listToExport 不做图片域名替换（Java 只做 id + 时间格式化）
    decorate_snapshot(&mut rows, false);''',
     '''    let p = page_params(&page);
    let mut rows = if p.empty {
        Vec::new()
    } else {
        state.snapshot_flow.list(&q, p.page_size, p.offset()).await?
    };
    // PARITY: listToExport 不做图片域名替换（Java 只做 id + 时间格式化）
    decorate_snapshot(&mut rows, false);'''),
    ('''    let p = page_params(&page);
    let mut rows = state.fee_gantry.list(&q, p.page_size, p.offset()).await?;''',
     '''    let p = page_params(&page);
    let mut rows = if p.empty {
        Vec::new()
    } else {
        state.fee_gantry.list(&q, p.page_size, p.offset()).await?
    };'''),
])

# sysutil carTrack page empty
edit('src/handlers/sysutil.rs', [
    ('''    if !vo.car_no.trim().is_empty() {
        vo.flag = "bannian".into();''',
     '''    if !p.empty && !vo.car_no.trim().is_empty() {
        vo.flag = "bannian".into();'''),
    ('''    if !carlist.is_empty() {
        vo.carlist = carlist.into();''',
     '''    if !p.empty && !carlist.is_empty() {
        vo.carlist = carlist.into();'''),
])

print('round2 fixes done')
