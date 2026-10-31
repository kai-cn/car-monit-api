import io

def edit(p, pairs):
    s = io.open(p, encoding='utf-8').read()
    for a, b in pairs:
        if a not in s:
            print('MISS', p, a[:70].replace('\n', ' '))
        s = s.replace(a, b)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

# A. JList null vs empty
jlist_old = '''// Java List 可为 null：JList 保留 null 语义，同时 Deref 到 Vec 便于直接使用。
#[derive(Debug, Clone, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct JList<T>(pub Vec<T>);

impl<T> std::ops::Deref for JList<T> {
    type Target = Vec<T>;
    fn deref(&self) -> &Vec<T> {
        &self.0
    }
}
impl<T> std::ops::DerefMut for JList<T> {
    fn deref_mut(&mut self) -> &mut Vec<T> {
        &mut self.0
    }
}
impl<T> From<Vec<T>> for JList<T> {
    fn from(v: Vec<T>) -> Self {
        JList(v)
    }
}
impl<T> FromIterator<T> for JList<T> {
    fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self {
        JList(iter.into_iter().collect())
    }
}
impl<T: Serialize> Serialize for JList<T> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        if self.0.is_empty() {
            s.serialize_none()
        } else {
            self.0.serialize(s)
        }
    }
}
impl<'de, T: Deserialize<'de>> Deserialize<'de> for JList<T> {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        Ok(JList(Option::<Vec<T>>::deserialize(d)?.unwrap_or_default()))
    }
}'''
jlist_new = '''// Java List 可为 null：JList 用 present 区分“null”与“显式空数组 []”。
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct JList<T> {
    pub value: Vec<T>,
    pub present: bool,
}

impl<T> Default for JList<T> {
    fn default() -> Self {
        JList { value: Vec::new(), present: false }
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
        JList { value: v, present: true }
    }
}
impl<T> FromIterator<T> for JList<T> {
    fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self {
        JList { value: iter.into_iter().collect(), present: true }
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
            Some(v) => Ok(JList { value: v, present: true }),
        }
    }
}'''
edit('src/models/mod.rs', [(jlist_old, jlist_new)])

# generator JList block (raw source without rustfmt expansion)
p = 'tools/gen_models.py'
s = io.open(p, encoding='utf-8').read()
g_old = '''// Java List 可为 null：JList 保留 null 语义，同时 Deref 到 Vec 便于直接使用。
#[derive(Debug, Clone, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct JList<T>(pub Vec<T>);'''
g_new = '''// Java List 可为 null：JList 用 present 区分“null”与“显式空数组 []”。
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct JList<T> {
    pub value: Vec<T>,
    pub present: bool,
}'''
s = s.replace(g_old, g_new)
s = s.replace('fn deref(&self) -> &Vec<T> { &self.0 }', 'fn deref(&self) -> &Vec<T> { &self.value }')
s = s.replace('fn deref_mut(&mut self) -> &mut Vec<T> { &mut self.0 }', 'fn deref_mut(&mut self) -> &mut Vec<T> { &mut self.value }')
s = s.replace('impl<T> From<Vec<T>> for JList<T> { fn from(v: Vec<T>) -> Self { JList(v) } }',
              '''impl<T> Default for JList<T> { fn default() -> Self { JList { value: Vec::new(), present: false } } }
impl<T> From<Vec<T>> for JList<T> { fn from(v: Vec<T>) -> Self { JList { value: v, present: true } } }''')
s = s.replace('impl<T> FromIterator<T> for JList<T> { fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self { JList(iter.into_iter().collect()) } }',
              '''impl<T> FromIterator<T> for JList<T> {
    fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self {
        JList { value: iter.into_iter().collect(), present: true }
    }
}''')
s = s.replace('        if self.0.is_empty() { s.serialize_none() } else { self.0.serialize(s) }',
              '        if self.present { self.value.serialize(s) } else { s.serialize_none() }')
s = s.replace('        Ok(JList(Option::<Vec<T>>::deserialize(d)?.unwrap_or_default()))',
              '''        match Option::<Vec<T>>::deserialize(d)? {
            None => Ok(JList::default()),
            Some(v) => Ok(JList { value: v, present: true }),
        }''')
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

# JList .0 usages
edit('src/services/trail.rs', [
    ('t.trail_list.0.clone()', 't.trail_list.value.clone()'),
])

# B. snapshot order
edit('src/repo/mod.rs', [
    ('    SNAPSHOT_SELECT,\n    "",\n    snapshot_filters', '    SNAPSHOT_SELECT,\n    "ORDER BY snapshottime DESC",\n    snapshot_filters'),
])

# C. fwqclls numeric
s = io.open('src/repo/mod.rs', encoding='utf-8').read()
s = s.replace('entity_repo!(\n    FwqcllsRepo,', 'entity_repo_numeric!(\n    FwqcllsRepo,')
io.open('src/repo/mod.rs', 'w', encoding='utf-8', newline='\n').write(s)

# D. page empty
edit('src/handlers/common.rs', [
    ('''pub struct PageParams {
    pub page_num: i64,
    pub page_size: i64,
}''', '''pub struct PageParams {
    pub page_num: i64,
    pub page_size: i64,
    /// PageHelper 语义：pageSize <= 0 时 rows 为空（total 仍为匹配总数）。
    pub empty: bool,
}'''),
    ('''    let mut page_size = q
        .page_size
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(10);
    if page_size <= 0 {
        page_size = 10;
    }''', '''    let parsed_size = q
        .page_size
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok());
    let empty = matches!(parsed_size, Some(n) if n <= 0);
    let mut page_size = parsed_size.filter(|n| *n > 0).unwrap_or(10);'''),
    ('''    PageParams {
        page_num,
        page_size,
    }
}''', '''    PageParams {
        page_num,
        page_size,
        empty,
    }
}'''),
])

edit('src/handlers/crud.rs', [
    ('''    let p = page_params(page);
    let rows = repo.list(&q, p.page_size, p.offset()).await?;
    let total = repo.count(&q).await?;''', '''    let p = page_params(page);
    let rows = if p.empty {
        Vec::new()
    } else {
        repo.list(&q, p.page_size, p.offset()).await?
    };
    let total = repo.count(&q).await?;'''),
    ('''    let p = page_params(page);
    let rows = repo.list(&q, p.page_size, p.offset()).await?;
    Ok(json_ok(serde_json::to_value(rows)?))''', '''    let p = page_params(page);
    let rows = if p.empty {
        Vec::new()
    } else {
        repo.list(&q, p.page_size, p.offset()).await?
    };
    Ok(json_ok(serde_json::to_value(rows)?))'''),
])

edit('src/handlers/base.rs', [
    ('''    let p = page_params(&page);
    let mut rows = state.snapshot_flow.list(&q, p.page_size, p.offset()).await?;
    decorate_snapshot(&mut rows, true);''', '''    let p = page_params(&page);
    let mut rows = if p.empty {
        Vec::new()
    } else {
        state.snapshot_flow.list(&q, p.page_size, p.offset()).await?
    };
    decorate_snapshot(&mut rows, true);'''),
    ('''    let p = page_params(&page);
    let mut rows = state.snapshot_flow.list(&q, p.page_size, p.offset()).await?;
    // PARITY: listToExport 不做图片域名替换（Java 只做 id + 时间格式化）''', '''    let p = page_params(&page);
    let mut rows = if p.empty {
        Vec::new()
    } else {
        state.snapshot_flow.list(&q, p.page_size, p.offset()).await?
    };
    // PARITY: listToExport 不做图片域名替换（Java 只做 id + 时间格式化）'''),
    ('''    let p = page_params(&page);
    let mut rows = state.fee_gantry.list(&q, p.page_size, p.offset()).await?;''', '''    let p = page_params(&page);
    let mut rows = if p.empty {
        Vec::new()
    } else {
        state.fee_gantry.list(&q, p.page_size, p.offset()).await?
    };'''),
])

edit('src/handlers/sysutil.rs', [
    ('if !vo.car_no.trim().is_empty() {', 'if !p.empty && !vo.car_no.trim().is_empty() {'),
    ('if !carlist.is_empty() {', 'if !p.empty && !carlist.is_empty() {'),
])
print('done')
