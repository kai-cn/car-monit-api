import io

# middleware scope
p = 'src/middleware.rs'
s = io.open(p, encoding='utf-8').read()
s = s.replace('    let mut resp = next.run(req).await;',
              '''    let mut resp = CURRENT_PATH
        .scope(path.clone(), async move { next.run(req).await })
        .await;''')
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

# utils local formatter
p = 'src/utils.rs'
s = io.open(p, encoding='utf-8').read()
s = s.replace('''/// 对应 @JsonFormat(pattern="yyyy-MM-dd")。
pub fn format_day''', '''/// Java `SimpleDateFormat` 默认使用 JVM 时区（Asia/Shanghai）：用于 snapshottimeStr 等展示字段。
pub fn format_datetime_local(dt: &DateTime<Utc>) -> String {
    (dt + chrono::Duration::hours(8))
        .format("%Y-%m-%d %H:%M:%S")
        .to_string()
}

/// 对应 @JsonFormat(pattern="yyyy-MM-dd")。
pub fn format_day''')
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

# base snapshot str local
p = 'src/handlers/base.rs'
s = io.open(p, encoding='utf-8').read()
s = s.replace('r.snapshottime_str = utils::format_datetime(&t).into();',
              'r.snapshottime_str = utils::format_datetime_local(&t).into();')
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

# Cond EqF64
p = 'src/repo/mod.rs'
s = io.open(p, encoding='utf-8').read()
s = s.replace("    EqI64(&'static str, i64),", "    EqI64(&'static str, i64),\n    EqF64(&'static str, f64),")
s = s.replace('''            Cond::Like(col, v) => {''', '''            Cond::EqF64(col, v) => {
                qb.push(*col).push(" = ").push_bind(*v);
            }
            Cond::Like(col, v) => {''')

start = s.index('pub fn snapshot_filters(q: &OdsRtSzdnSnapshotFlowAddcode) -> Vec<Cond> {')
end = s.index('\nfn prov_capture_filters', start)
new = '''pub fn snapshot_filters(q: &OdsRtSzdnSnapshotFlowAddcode) -> Vec<Cond> {
    // 逐条对应 OdsRtSzdnSnapshotFlowAddcodeMapper.xml:68-142 的 <if>。
    let mut v = vec![];
    if !q.apply_time1.is_empty() {
        v.push(Cond::Gte("snapshottime", q.apply_time1.clone().into()));
    }
    if !q.apply_time2.is_empty() {
        v.push(Cond::Lte("snapshottime", q.apply_time2.clone().into()));
    }
    if !q.big_id.is_empty() {
        v.push(Cond::Eq("big_id", q.big_id.clone().into()));
    }
    if !q.datasource.is_empty() {
        v.push(Cond::Eq("datasource", q.datasource.clone().into()));
    }
    if !q.cameratype.is_empty() {
        v.push(Cond::Eq("cameratype", q.cameratype.clone().into()));
    }
    if !q.deviceid.is_empty() {
        v.push(Cond::Eq("deviceid", q.deviceid.clone().into()));
    }
    if !q.gantrycode.is_empty() {
        v.push(Cond::Eq("gantrycode", q.gantrycode.clone().into()));
    }
    if !q.gantryname.is_empty() {
        v.push(Cond::Like("gantryname", q.gantryname.clone().into()));
    }
    if !q.roadcode.is_empty() {
        v.push(Cond::Eq("roadcode", q.roadcode.clone().into()));
    }
    if !q.roadname.is_empty() {
        v.push(Cond::Like("roadname", q.roadname.clone().into()));
    }
    if !q.sectioncode.is_empty() {
        v.push(Cond::Eq("sectioncode", q.sectioncode.clone().into()));
    }
    if !q.sectionname.is_empty() {
        v.push(Cond::Like("sectionname", q.sectionname.clone().into()));
    }
    if !q.tollcode.is_empty() {
        v.push(Cond::Eq("tollcode", q.tollcode.clone().into()));
    }
    if !q.tollname.is_empty() {
        v.push(Cond::Like("tollname", q.tollname.clone().into()));
    }
    if !q.orgcode.is_empty() {
        v.push(Cond::Eq("orgcode", q.orgcode.clone().into()));
    }
    // PARITY: 实测 Java 的 flag 条件未生效，不追加 orgcode 条件。
    if !q.orgname.is_empty() {
        v.push(Cond::Like("orgname", q.orgname.clone().into()));
    }
    if let Some(x) = q.direction.get() {
        v.push(Cond::EqI64("direction", x as i64));
    }
    if !q.hexcode.is_empty() {
        v.push(Cond::Eq("hexcode", q.hexcode.clone().into()));
    }
    if !q.pileno.is_empty() {
        v.push(Cond::Eq("pileno", q.pileno.clone().into()));
    }
    if let Some(x) = q.lon.get() {
        v.push(Cond::EqF64("lon", x));
    }
    if let Some(x) = q.lat.get() {
        v.push(Cond::EqF64("lat", x));
    }
    if !q.deviceip.is_empty() {
        v.push(Cond::Eq("deviceip", q.deviceip.clone().into()));
    }
    if let Some(x) = q.siteid.get() {
        v.push(Cond::EqI64("siteid", x));
    }
    if let Some(x) = q.laneid.get() {
        v.push(Cond::EqI64("laneid", x as i64));
    }
    if let Some(x) = q.snapshottimeunix.get() {
        v.push(Cond::EqI64("snapshottimeunix", x));
    }
    if let Some(t) = q.snapshottime.utc() {
        v.push(Cond::Eq(
            "snapshottime",
            crate::utils::format_datetime(&t).into(),
        ));
    }
    if let Some(x) = q.receivedtimeunix.get() {
        v.push(Cond::EqI64("receivedtimeunix", x));
    }
    if let Some(t) = q.receivedtime.utc() {
        v.push(Cond::Eq(
            "receivedtime",
            crate::utils::format_datetime(&t).into(),
        ));
    }
    if !q.platenumber.is_empty() {
        v.push(Cond::Like("platenumber", q.platenumber.clone().into()));
    }
    if !q.platecolor.is_empty() {
        v.push(Cond::Like("platecolor", q.platecolor.clone().into()));
    }
    if let Some(x) = q.platecolorcode.get() {
        v.push(Cond::EqI64("platecolorcode", x as i64));
    }
    if !q.platetype.is_empty() {
        v.push(Cond::Eq("platetype", q.platetype.clone().into()));
    }
    if let Some(x) = q.platetypecode.get() {
        v.push(Cond::EqI64("platetypecode", x as i64));
    }
    if let Some(x) = q.plateconfidence.get() {
        v.push(Cond::EqI64("plateconfidence", x as i64));
    }
    if !q.carbrand.is_empty() {
        v.push(Cond::Eq("carbrand", q.carbrand.clone().into()));
    }
    if !q.carcolor.is_empty() {
        v.push(Cond::Eq("carcolor", q.carcolor.clone().into()));
    }
    if let Some(x) = q.carcolorcode.get() {
        v.push(Cond::EqI64("carcolorcode", x as i64));
    }
    if !q.cartype.is_empty() {
        v.push(Cond::Eq("cartype", q.cartype.clone().into()));
    }
    if let Some(x) = q.cartypecode.get() {
        v.push(Cond::EqI64("cartypecode", x as i64));
    }
    if !q.cardirection.is_empty() {
        v.push(Cond::Eq("cardirection", q.cardirection.clone().into()));
    }
    if !q.snappicturepath.is_empty() {
        v.push(Cond::Eq("snappicturepath", q.snappicturepath.clone().into()));
    }
    if let Some(t) = q.loadtime.utc() {
        v.push(Cond::Eq(
            "loadtime",
            crate::utils::format_day(&t).into(),
        ));
    }
    if let Some(x) = q.gradelevel.get() {
        v.push(Cond::EqI64("gradelevel", x as i64));
    }
    if !q.datauuid.is_empty() {
        v.push(Cond::Eq("datauuid", q.datauuid.clone().into()));
    }
    if !q.reserve3.is_empty() {
        v.push(Cond::Eq("reserve3", q.reserve3.clone().into()));
    }
    if !q.code_list.is_empty() {
        v.push(Cond::In(
            "gantrycode",
            q.code_list.iter().map(|x| x.to_string()).collect(),
        ));
    }
    if !q.section_list.is_empty() {
        v.push(Cond::In(
            "sectioncode",
            q.section_list.iter().map(|x| x.to_string()).collect(),
        ));
    }
    v
}
'''
s = s[:start] + new + s[end:]
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('done')
