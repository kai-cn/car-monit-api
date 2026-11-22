// 由 tools/gen_filters.py 从 Mapper XML 自动生成，勿手改。
// 每个 <if> 对应一条 Cond，操作符（=/LIKE/GTE/LTE/IN）逐字对齐 XML。
use super::Cond;
use crate::models::*;

pub fn snapshot_filters(q: &OdsRtSzdnSnapshotFlowAddcode) -> Vec<Cond> {
    let mut v = vec![];
    if !q.apply_time1.is_empty() {
        v.push(Cond::Gte("snapshottime", q.apply_time1.clone()));
    }
    if !q.apply_time2.is_empty() {
        v.push(Cond::Lte("snapshottime", q.apply_time2.clone()));
    }
    if !q.big_id.is_empty() {
        v.push(Cond::Eq("big_id", q.big_id.clone()));
    }
    if !q.datasource.is_empty() {
        v.push(Cond::Eq("datasource", q.datasource.clone()));
    }
    if !q.cameratype.is_empty() {
        v.push(Cond::Eq("cameratype", q.cameratype.clone()));
    }
    if !q.deviceid.is_empty() {
        v.push(Cond::Eq("deviceid", q.deviceid.clone()));
    }
    if !q.gantrycode.is_empty() {
        v.push(Cond::Eq("gantrycode", q.gantrycode.clone()));
    }
    if !q.gantryname.is_empty() {
        v.push(Cond::Like("gantryname", q.gantryname.clone()));
    }
    if !q.roadcode.is_empty() {
        v.push(Cond::Eq("roadcode", q.roadcode.clone()));
    }
    if !q.roadname.is_empty() {
        v.push(Cond::Like("roadname", q.roadname.clone()));
    }
    if !q.sectioncode.is_empty() {
        v.push(Cond::Eq("sectioncode", q.sectioncode.clone()));
    }
    if !q.sectionname.is_empty() {
        v.push(Cond::Like("sectionname", q.sectionname.clone()));
    }
    if !q.tollcode.is_empty() {
        v.push(Cond::Eq("tollcode", q.tollcode.clone()));
    }
    if !q.tollname.is_empty() {
        v.push(Cond::Like("tollname", q.tollname.clone()));
    }
    if !q.orgcode.is_empty() {
        v.push(Cond::Eq("orgcode", q.orgcode.clone()));
    }
    // PARITY: XML 的 flag 字面量条件（OGNL 字符串比较生效）
    if q.flag.as_str() == "JiAnDong" {
        v.push(Cond::Eq("orgcode", "030000011".into()));
    }
    if !q.orgname.is_empty() {
        v.push(Cond::Like("orgname", q.orgname.clone()));
    }
    if let Some(x) = q.direction.get() {
        v.push(Cond::EqI64("direction", x as i64));
    }
    if !q.hexcode.is_empty() {
        v.push(Cond::Eq("hexcode", q.hexcode.clone()));
    }
    if !q.pileno.is_empty() {
        v.push(Cond::Eq("pileno", q.pileno.clone()));
    }
    if let Some(x) = q.lon.get() {
        v.push(Cond::EqF64("lon", x));
    }
    if let Some(x) = q.lat.get() {
        v.push(Cond::EqF64("lat", x));
    }
    if !q.deviceip.is_empty() {
        v.push(Cond::Eq("deviceip", q.deviceip.clone()));
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
        v.push(Cond::EqTimestamp("snapshottime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.receivedtimeunix.get() {
        v.push(Cond::EqI64("receivedtimeunix", x));
    }
    if let Some(t) = q.receivedtime.utc() {
        v.push(Cond::EqTimestamp("receivedtime", crate::utils::format_datetime(&t).into()));
    }
    if !q.platenumber.is_empty() {
        v.push(Cond::Like("platenumber", q.platenumber.clone()));
    }
    if !q.platecolor.is_empty() {
        v.push(Cond::Like("platecolor", q.platecolor.clone()));
    }
    if let Some(x) = q.platecolorcode.get() {
        v.push(Cond::EqI64("platecolorcode", x as i64));
    }
    if !q.platetype.is_empty() {
        v.push(Cond::Eq("platetype", q.platetype.clone()));
    }
    if let Some(x) = q.platetypecode.get() {
        v.push(Cond::EqI64("platetypecode", x as i64));
    }
    if let Some(x) = q.plateconfidence.get() {
        v.push(Cond::EqI64("plateconfidence", x as i64));
    }
    if !q.carbrand.is_empty() {
        v.push(Cond::Eq("carbrand", q.carbrand.clone()));
    }
    if !q.carcolor.is_empty() {
        v.push(Cond::Eq("carcolor", q.carcolor.clone()));
    }
    if let Some(x) = q.carcolorcode.get() {
        v.push(Cond::EqI64("carcolorcode", x as i64));
    }
    if !q.cartype.is_empty() {
        v.push(Cond::Eq("cartype", q.cartype.clone()));
    }
    if let Some(x) = q.cartypecode.get() {
        v.push(Cond::EqI64("cartypecode", x as i64));
    }
    if !q.cardirection.is_empty() {
        v.push(Cond::Eq("cardirection", q.cardirection.clone()));
    }
    if !q.snappicturepath.is_empty() {
        v.push(Cond::Eq("snappicturepath", q.snappicturepath.clone()));
    }
    if let Some(t) = q.loadtime.utc() {
        v.push(Cond::EqTimestamp("loadtime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.gradelevel.get() {
        v.push(Cond::EqI64("gradelevel", x as i64));
    }
    if !q.datauuid.is_empty() {
        v.push(Cond::Eq("datauuid", q.datauuid.clone()));
    }
    if !q.reserve3.is_empty() {
        v.push(Cond::Eq("reserve3", q.reserve3.clone()));
    }
    if !q.code_list.is_empty() {
        v.push(Cond::In("gantrycode", q.code_list.iter().map(|x| x.to_string()).collect()));
    }
    if !q.section_list.is_empty() {
        v.push(Cond::In("sectioncode", q.section_list.iter().map(|x| x.to_string()).collect()));
    }
    v
}

pub fn sfsj_filters(q: &DwdLcztSfsjcxx) -> Vec<Cond> {
    let mut v = vec![];
    // PARITY: XML 引用了不存在的属性 #{id}，Java 抛 BindingException -> 500。
    if !q.agent_pk.is_empty() {
        v.push(Cond::Eq("__mybatis_missing_property_id__", q.agent_pk.clone()));
    }
    if !q.yxtzj.is_empty() {
        v.push(Cond::Eq("yxtzj", q.yxtzj.clone()));
    }
    if !q.sfsbm.is_empty() {
        v.push(Cond::Eq("sfsbm", q.sfsbm.clone()));
    }
    if !q.sfsmc.is_empty() {
        v.push(Cond::Eq("sfsmc", q.sfsmc.clone()));
    }
    if !q.jd.is_empty() {
        v.push(Cond::Eq("jd", q.jd.clone()));
    }
    if !q.wd.is_empty() {
        v.push(Cond::Eq("wd", q.wd.clone()));
    }
    if !q.sslxbh.is_empty() {
        v.push(Cond::Eq("sslxbh", q.sslxbh.clone()));
    }
    if !q.sslxmc.is_empty() {
        v.push(Cond::Eq("sslxmc", q.sslxmc.clone()));
    }
    if !q.ssldbh.is_empty() {
        v.push(Cond::Eq("ssldbh", q.ssldbh.clone()));
    }
    if !q.ssldmc.is_empty() {
        v.push(Cond::Eq("ssldmc", q.ssldmc.clone()));
    }
    if !q.sczh_k.is_empty() {
        v.push(Cond::Eq("sczh_k", q.sczh_k.clone()));
    }
    if !q.sczh_n.is_empty() {
        v.push(Cond::Eq("sczh_n", q.sczh_n.clone()));
    }
    if !q.ssglzxbm.is_empty() {
        v.push(Cond::Eq("ssglzxbm", q.ssglzxbm.clone()));
    }
    if !q.ssglzxmc.is_empty() {
        v.push(Cond::Eq("ssglzxmc", q.ssglzxmc.clone()));
    }
    if !q.lyxt.is_empty() {
        v.push(Cond::Eq("lyxt", q.lyxt.clone()));
    }
    if !q.load_time.is_empty() {
        v.push(Cond::Eq("load_time", q.load_time.clone()));
    }
    if !q.all_col_pk.is_empty() {
        v.push(Cond::Eq("all_col_pk", q.all_col_pk.clone()));
    }
    v
}

pub fn sfzj_filters(q: &DwdLcztSfzjcxx) -> Vec<Cond> {
    let mut v = vec![];
    if !q.agent_pk.is_empty() {
        v.push(Cond::Eq("agent_pk", q.agent_pk.clone()));
    }
    if !q.yxtzj.is_empty() {
        v.push(Cond::Eq("yxtzj", q.yxtzj.clone()));
    }
    if !q.sfzdm.is_empty() {
        v.push(Cond::Eq("sfzdm", q.sfzdm.clone()));
    }
    if !q.sfzmc.is_empty() {
        v.push(Cond::Eq("sfzmc", q.sfzmc.clone()));
    }
    if !q.jd.is_empty() {
        v.push(Cond::Eq("jd", q.jd.clone()));
    }
    if !q.wd.is_empty() {
        v.push(Cond::Eq("wd", q.wd.clone()));
    }
    if !q.sslxbh.is_empty() {
        v.push(Cond::Eq("sslxbh", q.sslxbh.clone()));
    }
    if !q.sslxmc.is_empty() {
        v.push(Cond::Eq("sslxmc", q.sslxmc.clone()));
    }
    if !q.ssldbh.is_empty() {
        v.push(Cond::Eq("ssldbh", q.ssldbh.clone()));
    }
    if !q.ssldmc.is_empty() {
        v.push(Cond::Eq("ssldmc", q.ssldmc.clone()));
    }
    if !q.sczh_k.is_empty() {
        v.push(Cond::Eq("sczh_k", q.sczh_k.clone()));
    }
    if !q.sczh_n.is_empty() {
        v.push(Cond::Eq("sczh_n", q.sczh_n.clone()));
    }
    if !q.ssglzxbm.is_empty() {
        v.push(Cond::Eq("ssglzxbm", q.ssglzxbm.clone()));
    }
    if !q.ssglzxmc.is_empty() {
        v.push(Cond::Eq("ssglzxmc", q.ssglzxmc.clone()));
    }
    if !q.lyxt.is_empty() {
        v.push(Cond::Eq("lyxt", q.lyxt.clone()));
    }
    if !q.load_time.is_empty() {
        v.push(Cond::Eq("load_time", q.load_time.clone()));
    }
    if !q.all_col_pk.is_empty() {
        v.push(Cond::Eq("all_col_pk", q.all_col_pk.clone()));
    }
    v
}

pub fn fwq_filters(q: &DwdLcztFwqjcxx) -> Vec<Cond> {
    let mut v = vec![];
    if !q.agent_pk.is_empty() {
        v.push(Cond::Eq("agent_pk", q.agent_pk.clone()));
    }
    if !q.yxtzj.is_empty() {
        v.push(Cond::Eq("yxtzj", q.yxtzj.clone()));
    }
    if !q.fwqbm.is_empty() {
        v.push(Cond::Eq("service_code", q.fwqbm.clone()));
    }
    if !q.fwqmc.is_empty() {
        v.push(Cond::Eq("service_name", q.fwqmc.clone()));
    }
    if !q.wd.is_empty() {
        v.push(Cond::Eq("wd", q.wd.clone()));
    }
    if !q.fxmc.is_empty() {
        v.push(Cond::Eq("fxmc", q.fxmc.clone()));
    }
    if !q.fxdm.is_empty() {
        v.push(Cond::Eq("fxdm", q.fxdm.clone()));
    }
    if !q.jd.is_empty() {
        v.push(Cond::Eq("jd", q.jd.clone()));
    }
    if !q.sslxbh.is_empty() {
        v.push(Cond::Eq("road_code", q.sslxbh.clone()));
    }
    if !q.sslxmc.is_empty() {
        v.push(Cond::Eq("sslxmc", q.sslxmc.clone()));
    }
    if !q.ssldbh.is_empty() {
        v.push(Cond::Eq("section_code", q.ssldbh.clone()));
    }
    if !q.ssldmc.is_empty() {
        v.push(Cond::Eq("section_name", q.ssldmc.clone()));
    }
    if !q.sczhkgs.is_empty() {
        v.push(Cond::Eq("sczhkgs", q.sczhkgs.clone()));
    }
    if !q.sczhszgs.is_empty() {
        v.push(Cond::Eq("sczhszgs", q.sczhszgs.clone()));
    }
    if !q.ssglzxbm.is_empty() {
        v.push(Cond::Eq("ssglzxbm", q.ssglzxbm.clone()));
    }
    if !q.ssglzxmc.is_empty() {
        v.push(Cond::Eq("ssglzxmc", q.ssglzxmc.clone()));
    }
    if !q.xzqhmc.is_empty() {
        v.push(Cond::Eq("xzqhmc", q.xzqhmc.clone()));
    }
    if !q.yyrq.is_empty() {
        v.push(Cond::Eq("yyrq", q.yyrq.clone()));
    }
    if !q.cws.is_empty() {
        v.push(Cond::Eq("cws", q.cws.clone()));
    }
    if !q.sfszlkk.is_empty() {
        v.push(Cond::Eq("sfszlkk", q.sfszlkk.clone()));
    }
    if !q.cdzs.is_empty() {
        v.push(Cond::Eq("cdzs", q.cdzs.clone()));
    }
    if !q.sfcyfw.is_empty() {
        v.push(Cond::Eq("sfcyfw", q.sfcyfw.clone()));
    }
    if !q.sftgzsfw.is_empty() {
        v.push(Cond::Eq("sftgzsfw", q.sftgzsfw.clone()));
    }
    if !q.sftgqxfw.is_empty() {
        v.push(Cond::Eq("sftgqxfw", q.sftgqxfw.clone()));
    }
    if !q.sftgcsfw.is_empty() {
        v.push(Cond::Eq("sftgcsfw", q.sftgcsfw.clone()));
    }
    if !q.sftgjyfw.is_empty() {
        v.push(Cond::Eq("sftgjyfw", q.sftgjyfw.clone()));
    }
    if !q.mj.is_empty() {
        v.push(Cond::Eq("mj", q.mj.clone()));
    }
    if !q.sftgcshfw.is_empty() {
        v.push(Cond::Eq("sftgcshfw", q.sftgcshfw.clone()));
    }
    if !q.xzqhdm.is_empty() {
        v.push(Cond::Eq("xzqhdm", q.xzqhdm.clone()));
    }
    if !q.synx.is_empty() {
        v.push(Cond::Eq("synx", q.synx.clone()));
    }
    if !q.lyxt.is_empty() {
        v.push(Cond::Eq("lyxt", q.lyxt.clone()));
    }
    if !q.load_time.is_empty() {
        v.push(Cond::Eq("load_time", q.load_time.clone()));
    }
    if !q.all_col_pk.is_empty() {
        v.push(Cond::Eq("all_col_pk", q.all_col_pk.clone()));
    }
    v
}

pub fn fwqclls_filters(q: &OdsCxztFwqclls) -> Vec<Cond> {
    let mut v = vec![];
    if let Some(x) = q.big_id.get() {
        v.push(Cond::EqI64("big_id", x));
    }
    if !q.datauuid.is_empty() {
        v.push(Cond::Eq("datauuid", q.datauuid.clone()));
    }
    if !q.targetpicurl.is_empty() {
        v.push(Cond::Eq("targetpicurl", q.targetpicurl.clone()));
    }
    if !q.vehiclebrand.is_empty() {
        v.push(Cond::Eq("vehiclebrand", q.vehiclebrand.clone()));
    }
    if !q.platepicurl.is_empty() {
        v.push(Cond::Eq("platepicurl", q.platepicurl.clone()));
    }
    if !q.rollvehiclestype.is_empty() {
        v.push(Cond::Eq("rollvehiclestype", q.rollvehiclestype.clone()));
    }
    if !q.plateno.is_empty() {
        v.push(Cond::Eq("plateno", q.plateno.clone()));
    }
    if !q.directionname.is_empty() {
        v.push(Cond::Like("directionname", q.directionname.clone()));
    }
    if !q.platetype.is_empty() {
        v.push(Cond::Eq("platetype", q.platetype.clone()));
    }
    if !q.dangmark.is_empty() {
        v.push(Cond::Eq("dangmark", q.dangmark.clone()));
    }
    if let Some(t) = q.crosstime.utc() {
        v.push(Cond::EqTimestamp("crosstime", crate::utils::format_datetime(&t).into()));
    }
    if !q.axles.is_empty() {
        v.push(Cond::Eq("axles", q.axles.clone()));
    }
    if !q.devicename.is_empty() {
        v.push(Cond::Like("devicename", q.devicename.clone()));
    }
    if !q.ipaddress.is_empty() {
        v.push(Cond::Eq("ipaddress", q.ipaddress.clone()));
    }
    if !q.servicename.is_empty() {
        v.push(Cond::Like("servicename", q.servicename.clone()));
    }
    if !q.vehicletype.is_empty() {
        v.push(Cond::Eq("vehicletype", q.vehicletype.clone()));
    }
    if !q.load_time.is_empty() {
        v.push(Cond::Eq("load_time", q.load_time.clone()));
    }
    if !q.grade_level.is_empty() {
        v.push(Cond::Eq("grade_level", q.grade_level.clone()));
    }
    if !q.uuid_list.is_empty() {
        v.push(Cond::In("datauuid", q.uuid_list.iter().map(|x| x.to_string()).collect()));
    }
    v
}

pub fn fee_gantry_filters(q: &OdsLwzxsfsjFeeGantryFusion01) -> Vec<Cond> {
    let mut v = vec![];
    if !q.big_id.is_empty() {
        v.push(Cond::Eq("big_id", q.big_id.clone()));
    }
    if !q.id.is_empty() {
        v.push(Cond::Eq("id", q.id.clone()));
    }
    if !q.actualfeeclass.is_empty() {
        v.push(Cond::Eq("actualfeeclass", q.actualfeeclass.clone()));
    }
    if let Some(x) = q.axlecount.get() {
        v.push(Cond::EqI64("axlecount", x));
    }
    if let Some(t) = q.createtime.utc() {
        v.push(Cond::EqTimestamp("createtime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.discountfee.get() {
        v.push(Cond::EqI64("discountfee", x));
    }
    if let Some(x) = q.electricalpercentage.get() {
        v.push(Cond::EqI64("electricalpercentage", x));
    }
    if let Some(x) = q.enaxlecount.get() {
        v.push(Cond::EqI64("enaxlecount", x));
    }
    if let Some(t) = q.entime.utc() {
        v.push(Cond::EqTimestamp("entime", crate::utils::format_datetime(&t).into()));
    }
    if !q.entolllanehex.is_empty() {
        v.push(Cond::Eq("entolllanehex", q.entolllanehex.clone()));
    }
    if !q.entolllaneid.is_empty() {
        v.push(Cond::Eq("entolllaneid", q.entolllaneid.clone()));
    }
    if !q.entollstationid.is_empty() {
        v.push(Cond::Eq("entollstationid", q.entollstationid.clone()));
    }
    if !q.entollstationname.is_empty() {
        v.push(Cond::Like("entollstationname", q.entollstationname.clone()));
    }
    if let Some(x) = q.envehicleclass.get() {
        v.push(Cond::EqI64("envehicleclass", x));
    }
    if !q.envehicleid.is_empty() {
        v.push(Cond::Eq("envehicleid", q.envehicleid.clone()));
    }
    if !q.envehicleidcolor.is_empty() {
        v.push(Cond::Eq("envehicleidcolor", q.envehicleidcolor.clone()));
    }
    if let Some(x) = q.envehicletype.get() {
        v.push(Cond::EqI64("envehicletype", x));
    }
    if let Some(x) = q.enweight.get() {
        v.push(Cond::EqI64("enweight", x));
    }
    if !q.entryoperatorid.is_empty() {
        v.push(Cond::Eq("entryoperatorid", q.entryoperatorid.clone()));
    }
    if let Some(t) = q.extime.utc() {
        v.push(Cond::EqTimestamp("extime", crate::utils::format_datetime(&t).into()));
    }
    if !q.extolllaneid.is_empty() {
        v.push(Cond::Eq("extolllaneid", q.extolllaneid.clone()));
    }
    if !q.extollstationid.is_empty() {
        v.push(Cond::Eq("extollstationid", q.extollstationid.clone()));
    }
    if !q.extollstationname.is_empty() {
        v.push(Cond::Like("extollstationname", q.extollstationname.clone()));
    }
    if let Some(x) = q.exvehicleclass.get() {
        v.push(Cond::EqI64("exvehicleclass", x));
    }
    if !q.exvehicleid.is_empty() {
        v.push(Cond::Eq("exvehicleid", q.exvehicleid.clone()));
    }
    if let Some(x) = q.exvehicletype.get() {
        v.push(Cond::EqI64("exvehicletype", x));
    }
    if let Some(x) = q.exweight.get() {
        v.push(Cond::EqI64("exweight", x));
    }
    if !q.exitid.is_empty() {
        v.push(Cond::Eq("exitid", q.exitid.clone()));
    }
    if let Some(x) = q.fee.get() {
        v.push(Cond::EqI64("fee", x));
    }
    if !q.feeboardplay.is_empty() {
        v.push(Cond::Eq("feeboardplay", q.feeboardplay.clone()));
    }
    if let Some(x) = q.feemileage.get() {
        v.push(Cond::EqI64("feemileage", x));
    }
    if !q.feerate.is_empty() {
        v.push(Cond::Eq("feerate", q.feerate.clone()));
    }
    if !q.fusiondesc.is_empty() {
        v.push(Cond::Eq("fusiondesc", q.fusiondesc.clone()));
    }
    if !q.fusionflag.is_empty() {
        v.push(Cond::Eq("fusionflag", q.fusionflag.clone()));
    }
    if !q.identification.is_empty() {
        v.push(Cond::Eq("identification", q.identification.clone()));
    }
    if !q.identifyvehicleid.is_empty() {
        v.push(Cond::Eq("identifyvehicleid", q.identifyvehicleid.clone()));
    }
    if !q.identifyvehicleidcolor.is_empty() {
        v.push(Cond::Eq("identifyvehicleidcolor", q.identifyvehicleidcolor.clone()));
    }
    if !q.lanetype.is_empty() {
        v.push(Cond::Eq("lanetype", q.lanetype.clone()));
    }
    if !q.mediano.is_empty() {
        v.push(Cond::Eq("mediano", q.mediano.clone()));
    }
    if !q.mediatype.is_empty() {
        v.push(Cond::Eq("mediatype", q.mediatype.clone()));
    }
    if let Some(x) = q.nocardcount.get() {
        v.push(Cond::EqI64("nocardcount", x));
    }
    if !q.obuid.is_empty() {
        v.push(Cond::Eq("obuid", q.obuid.clone()));
    }
    if !q.obusign.is_empty() {
        v.push(Cond::Eq("obusign", q.obusign.clone()));
    }
    if let Some(x) = q.obutotalamount.get() {
        v.push(Cond::EqI64("obutotalamount", x));
    }
    if let Some(x) = q.obutotaldiscountamount.get() {
        v.push(Cond::EqI64("obutotaldiscountamount", x));
    }
    if !q.operid.is_empty() {
        v.push(Cond::Eq("operid", q.operid.clone()));
    }
    if !q.params.is_empty() {
        v.push(Cond::Eq("params", q.params.clone()));
    }
    if !q.passid.is_empty() {
        v.push(Cond::Eq("passid", q.passid.clone()));
    }
    if !q.paycardid.is_empty() {
        v.push(Cond::Eq("paycardid", q.paycardid.clone()));
    }
    if let Some(x) = q.payfee.get() {
        v.push(Cond::EqI64("payfee", x));
    }
    if !q.paytype.is_empty() {
        v.push(Cond::Eq("paytype", q.paytype.clone()));
    }
    if let Some(x) = q.provfee.get() {
        v.push(Cond::EqI64("provfee", x));
    }
    if let Some(x) = q.provtranscount.get() {
        v.push(Cond::EqI64("provtranscount", x));
    }
    if let Some(x) = q.provincecount.get() {
        v.push(Cond::EqI64("provincecount", x));
    }
    if let Some(t) = q.receivetime.utc() {
        v.push(Cond::EqTimestamp("receivetime", crate::utils::format_datetime(&t).into()));
    }
    if !q.shift.is_empty() {
        v.push(Cond::Eq("shift", q.shift.clone()));
    }
    if let Some(x) = q.shortfee.get() {
        v.push(Cond::EqI64("shortfee", x));
    }
    if let Some(x) = q.shortfeemileage.get() {
        v.push(Cond::EqI64("shortfeemileage", x));
    }
    if !q.signstatus.is_empty() {
        v.push(Cond::Eq("signstatus", q.signstatus.clone()));
    }
    if !q.spcrateversion.is_empty() {
        v.push(Cond::Eq("spcrateversion", q.spcrateversion.clone()));
    }
    if !q.specialtype.is_empty() {
        v.push(Cond::Eq("specialtype", q.specialtype.clone()));
    }
    if !q.splitprovince.is_empty() {
        v.push(Cond::Eq("splitprovince", q.splitprovince.clone()));
    }
    if !q.tac.is_empty() {
        v.push(Cond::Eq("tac", q.tac.clone()));
    }
    if !q.terminalno.is_empty() {
        v.push(Cond::Eq("terminalno", q.terminalno.clone()));
    }
    if !q.terminaltransno.is_empty() {
        v.push(Cond::Eq("terminaltransno", q.terminaltransno.clone()));
    }
    if let Some(x) = q.transfee.get() {
        v.push(Cond::EqI64("transfee", x));
    }
    if !q.transpaytype.is_empty() {
        v.push(Cond::Eq("transpaytype", q.transpaytype.clone()));
    }
    if !q.transtype.is_empty() {
        v.push(Cond::Eq("transtype", q.transtype.clone()));
    }
    if !q.vehiclesign.is_empty() {
        v.push(Cond::Eq("vehiclesign", q.vehiclesign.clone()));
    }
    if !q.vehiclesignid.is_empty() {
        v.push(Cond::Eq("vehiclesignid", q.vehiclesignid.clone()));
    }
    if !q.vid.is_empty() {
        v.push(Cond::Eq("vid", q.vid.clone()));
    }
    if let Some(t) = q.load_time.utc() {
        v.push(Cond::EqTimestamp("load_time", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.grade_level.get() {
        v.push(Cond::EqI64("grade_level", x));
    }
    if !q.in_apply_time1.is_empty() {
        v.push(Cond::Gte("entime", q.in_apply_time1.clone()));
    }
    if !q.in_apply_time2.is_empty() {
        v.push(Cond::Lte("entime", q.in_apply_time2.clone()));
    }
    if !q.out_apply_time1.is_empty() {
        v.push(Cond::Gte("extime", q.out_apply_time1.clone()));
    }
    if !q.out_apply_time2.is_empty() {
        v.push(Cond::Lte("extime", q.out_apply_time2.clone()));
    }
    v
}

pub fn fee_enter_filters(q: &OdsLwzxsfsjFeeStationEnter01) -> Vec<Cond> {
    let mut v = vec![];
    if let Some(x) = q.big_id.get() {
        v.push(Cond::EqI64("big_id", x));
    }
    if !q.cardid.is_empty() {
        v.push(Cond::Eq("cardid", q.cardid.clone()));
    }
    if let Some(x) = q.electricalpercentage.get() {
        v.push(Cond::EqI64("electricalpercentage", x));
    }
    if let Some(x) = q.enaxlecount.get() {
        v.push(Cond::EqI64("enaxlecount", x));
    }
    if let Some(t) = q.entime.utc() {
        v.push(Cond::EqTimestamp("entime", crate::utils::format_datetime(&t).into()));
    }
    if !q.entolllanehex.is_empty() {
        v.push(Cond::Eq("entolllanehex", q.entolllanehex.clone()));
    }
    if !q.entolllaneid.is_empty() {
        v.push(Cond::Eq("entolllaneid", q.entolllaneid.clone()));
    }
    if !q.entollstationid.is_empty() {
        v.push(Cond::Eq("entollstationid", q.entollstationid.clone()));
    }
    if let Some(x) = q.enweight.get() {
        v.push(Cond::EqF64("enweight", x));
    }
    if !q.identifyvehicleid.is_empty() {
        v.push(Cond::Eq("identifyvehicleid", q.identifyvehicleid.clone()));
    }
    if !q.lanetype.is_empty() {
        v.push(Cond::Eq("lanetype", q.lanetype.clone()));
    }
    if !q.mediatype.is_empty() {
        v.push(Cond::Eq("mediatype", q.mediatype.clone()));
    }
    if !q.operid.is_empty() {
        v.push(Cond::Eq("operid", q.operid.clone()));
    }
    if !q.operationmedia.is_empty() {
        v.push(Cond::Eq("operationmedia", q.operationmedia.clone()));
    }
    if !q.params.is_empty() {
        v.push(Cond::Eq("params", q.params.clone()));
    }
    if !q.passid.is_empty() {
        v.push(Cond::Eq("passid", q.passid.clone()));
    }
    if let Some(t) = q.receivetime.utc() {
        v.push(Cond::EqTimestamp("receivetime", crate::utils::format_datetime(&t).into()));
    }
    if !q.shift.is_empty() {
        v.push(Cond::Eq("shift", q.shift.clone()));
    }
    if !q.signstatus.is_empty() {
        v.push(Cond::Eq("signstatus", q.signstatus.clone()));
    }
    if !q.specialtype.is_empty() {
        v.push(Cond::Eq("specialtype", q.specialtype.clone()));
    }
    if !q.tac.is_empty() {
        v.push(Cond::Eq("tac", q.tac.clone()));
    }
    if !q.terminalno.is_empty() {
        v.push(Cond::Eq("terminalno", q.terminalno.clone()));
    }
    if !q.terminaltransno.is_empty() {
        v.push(Cond::Eq("terminaltransno", q.terminaltransno.clone()));
    }
    if let Some(x) = q.transfee.get() {
        v.push(Cond::EqF64("transfee", x));
    }
    if !q.transtype.is_empty() {
        v.push(Cond::Eq("transtype", q.transtype.clone()));
    }
    if let Some(x) = q.vcount.get() {
        v.push(Cond::EqI64("vcount", x));
    }
    if !q.vehicleclass.is_empty() {
        v.push(Cond::Eq("vehicleclass", q.vehicleclass.clone()));
    }
    if !q.vehicleid.is_empty() {
        v.push(Cond::Eq("vehicleid", q.vehicleid.clone()));
    }
    if !q.vehiclesign.is_empty() {
        v.push(Cond::Eq("vehiclesign", q.vehiclesign.clone()));
    }
    if !q.vehiclesignid.is_empty() {
        v.push(Cond::Eq("vehiclesignid", q.vehiclesignid.clone()));
    }
    if !q.vehicletype.is_empty() {
        v.push(Cond::Eq("vehicletype", q.vehicletype.clone()));
    }
    if let Some(t) = q.load_time.utc() {
        v.push(Cond::EqTimestamp("load_time", crate::utils::format_datetime(&t).into()));
    }
    if !q.grade_level.is_empty() {
        v.push(Cond::Eq("grade_level", q.grade_level.clone()));
    }
    if !q.cid_list.is_empty() {
        v.push(Cond::In("cid", q.cid_list.iter().map(|x| x.to_string()).collect()));
    }
    if !q.cid.is_empty() {
        v.push(Cond::Eq("cid", q.cid.clone()));
    }
    v
}

pub fn fee_exit_filters(q: &OdsLwzxsfsjFeeStationExit01) -> Vec<Cond> {
    let mut v = vec![];
    if !q.big_id.is_empty() {
        v.push(Cond::Eq("big_id", q.big_id.clone()));
    }
    if !q.actualfeeclass.is_empty() {
        v.push(Cond::Eq("actualfeeclass", q.actualfeeclass.clone()));
    }
    if let Some(x) = q.axlecount.get() {
        v.push(Cond::EqI64("axlecount", x as i64));
    }
    if let Some(x) = q.discountfee.get() {
        v.push(Cond::EqI64("discountfee", x));
    }
    if let Some(x) = q.electricalpercentage.get() {
        v.push(Cond::EqI64("electricalpercentage", x as i64));
    }
    if let Some(x) = q.enaxlecount.get() {
        v.push(Cond::EqI64("enaxlecount", x as i64));
    }
    if let Some(t) = q.entime.utc() {
        v.push(Cond::EqTimestamp("entime", crate::utils::format_datetime(&t).into()));
    }
    if !q.entolllanehex.is_empty() {
        v.push(Cond::Eq("entolllanehex", q.entolllanehex.clone()));
    }
    if !q.entolllaneid.is_empty() {
        v.push(Cond::Eq("entolllaneid", q.entolllaneid.clone()));
    }
    if !q.entollstationid.is_empty() {
        v.push(Cond::Eq("entollstationid", q.entollstationid.clone()));
    }
    if !q.entollstationname.is_empty() {
        v.push(Cond::Like("entollstationname", q.entollstationname.clone()));
    }
    if let Some(x) = q.envehicleclass.get() {
        v.push(Cond::EqI64("envehicleclass", x as i64));
    }
    if !q.envehicleid.is_empty() {
        v.push(Cond::Eq("envehicleid", q.envehicleid.clone()));
    }
    if let Some(x) = q.envehicletype.get() {
        v.push(Cond::EqI64("envehicletype", x as i64));
    }
    if let Some(x) = q.enweight.get() {
        v.push(Cond::EqI64("enweight", x));
    }
    if !q.entryoperatorid.is_empty() {
        v.push(Cond::Eq("entryoperatorid", q.entryoperatorid.clone()));
    }
    if let Some(t) = q.extime.utc() {
        v.push(Cond::EqTimestamp("extime", crate::utils::format_datetime(&t).into()));
    }
    if !q.extolllaneid.is_empty() {
        v.push(Cond::Eq("extolllaneid", q.extolllaneid.clone()));
    }
    if !q.extollstationid.is_empty() {
        v.push(Cond::Eq("extollstationid", q.extollstationid.clone()));
    }
    if !q.extollstationname.is_empty() {
        v.push(Cond::Like("extollstationname", q.extollstationname.clone()));
    }
    if let Some(x) = q.exvehicleclass.get() {
        v.push(Cond::EqI64("exvehicleclass", x as i64));
    }
    if !q.exvehicleid.is_empty() {
        v.push(Cond::Eq("exvehicleid", q.exvehicleid.clone()));
    }
    if let Some(x) = q.exvehicletype.get() {
        v.push(Cond::EqI64("exvehicletype", x as i64));
    }
    if let Some(x) = q.fee.get() {
        v.push(Cond::EqI64("fee", x));
    }
    if let Some(x) = q.exweight.get() {
        v.push(Cond::EqI64("exweight", x));
    }
    if !q.feeboardplay.is_empty() {
        v.push(Cond::Eq("feeboardplay", q.feeboardplay.clone()));
    }
    if let Some(x) = q.feemileage.get() {
        v.push(Cond::EqI64("feemileage", x));
    }
    if !q.identification.is_empty() {
        v.push(Cond::Eq("identification", q.identification.clone()));
    }
    if let Some(x) = q.feerate.get() {
        v.push(Cond::EqF64("feerate", x));
    }
    if !q.identifyvehicleid.is_empty() {
        v.push(Cond::Like("identifyvehicleid", q.identifyvehicleid.clone()));
    }
    if !q.lanetype.is_empty() {
        v.push(Cond::Eq("lanetype", q.lanetype.clone()));
    }
    if !q.mediano.is_empty() {
        v.push(Cond::Eq("mediano", q.mediano.clone()));
    }
    if !q.mediatype.is_empty() {
        v.push(Cond::Eq("mediatype", q.mediatype.clone()));
    }
    if let Some(x) = q.nocardcount.get() {
        v.push(Cond::EqI64("nocardcount", x as i64));
    }
    if !q.obuid.is_empty() {
        v.push(Cond::Eq("obuid", q.obuid.clone()));
    }
    if !q.obusign.is_empty() {
        v.push(Cond::Eq("obusign", q.obusign.clone()));
    }
    if let Some(x) = q.obutotalamount.get() {
        v.push(Cond::EqI64("obutotalamount", x));
    }
    if let Some(x) = q.obutotaldiscountamount.get() {
        v.push(Cond::EqI64("obutotaldiscountamount", x));
    }
    if !q.params.is_empty() {
        v.push(Cond::Eq("params", q.params.clone()));
    }
    if !q.operid.is_empty() {
        v.push(Cond::Eq("operid", q.operid.clone()));
    }
    if !q.passid.is_empty() {
        v.push(Cond::Eq("passid", q.passid.clone()));
    }
    if !q.paycardid.is_empty() {
        v.push(Cond::Eq("paycardid", q.paycardid.clone()));
    }
    if let Some(x) = q.payfee.get() {
        v.push(Cond::EqI64("payfee", x));
    }
    if !q.paytype.is_empty() {
        v.push(Cond::Eq("paytype", q.paytype.clone()));
    }
    if let Some(x) = q.provfee.get() {
        v.push(Cond::EqI64("provfee", x));
    }
    if let Some(x) = q.provtranscount.get() {
        v.push(Cond::EqI64("provtranscount", x as i64));
    }
    if let Some(x) = q.provincecount.get() {
        v.push(Cond::EqI64("provincecount", x as i64));
    }
    if !q.shift.is_empty() {
        v.push(Cond::Eq("shift", q.shift.clone()));
    }
    if let Some(t) = q.receivetime.utc() {
        v.push(Cond::EqTimestamp("receivetime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.shortfee.get() {
        v.push(Cond::EqI64("shortfee", x));
    }
    if let Some(x) = q.shortfeemileage.get() {
        v.push(Cond::EqI64("shortfeemileage", x));
    }
    if !q.signstatus.is_empty() {
        v.push(Cond::Eq("signstatus", q.signstatus.clone()));
    }
    if !q.spcrateversion.is_empty() {
        v.push(Cond::Eq("spcrateversion", q.spcrateversion.clone()));
    }
    if !q.tac.is_empty() {
        v.push(Cond::Eq("tac", q.tac.clone()));
    }
    if !q.specialtype.is_empty() {
        v.push(Cond::Eq("specialtype", q.specialtype.clone()));
    }
    if !q.splitprovince.is_empty() {
        v.push(Cond::Eq("splitprovince", q.splitprovince.clone()));
    }
    if !q.terminalno.is_empty() {
        v.push(Cond::Eq("terminalno", q.terminalno.clone()));
    }
    if !q.terminaltransno.is_empty() {
        v.push(Cond::Eq("terminaltransno", q.terminaltransno.clone()));
    }
    if let Some(x) = q.transfee.get() {
        v.push(Cond::EqI64("transfee", x));
    }
    if !q.transpaytype.is_empty() {
        v.push(Cond::Eq("transpaytype", q.transpaytype.clone()));
    }
    if !q.transtype.is_empty() {
        v.push(Cond::Eq("transtype", q.transtype.clone()));
    }
    if let Some(t) = q.load_time.utc() {
        v.push(Cond::EqTimestamp("load_time", crate::utils::format_datetime(&t).into()));
    }
    if !q.vehiclesign.is_empty() {
        v.push(Cond::Eq("vehiclesign", q.vehiclesign.clone()));
    }
    if !q.grade_level.is_empty() {
        v.push(Cond::Eq("grade_level", q.grade_level.clone()));
    }
    if !q.vehiclesignid.is_empty() {
        v.push(Cond::Eq("vehiclesignid", q.vehiclesignid.clone()));
    }
    if !q.cid_list.is_empty() {
        v.push(Cond::In("cid", q.cid_list.iter().map(|x| x.to_string()).collect()));
    }
    if !q.cid.is_empty() {
        v.push(Cond::Eq("cid", q.cid.clone()));
    }
    v
}

pub fn prov_capture_filters(q: &OdsRtSzdnSnapshotFlowProvcaptureAddcode) -> Vec<Cond> {
    let mut v = vec![];
    if let Some(x) = q.big_id.get() {
        v.push(Cond::EqI64("big_id", x));
    }
    if !q.deviceip.is_empty() {
        v.push(Cond::Eq("deviceip", q.deviceip.clone()));
    }
    if let Some(x) = q.tailcapturetimeunix.get() {
        v.push(Cond::EqI64("tailcapturetimeunix", x));
    }
    if let Some(t) = q.tailcapturetime.utc() {
        v.push(Cond::EqTimestamp("tailcapturetime", crate::utils::format_datetime(&t).into()));
    }
    if !q.extendattribute.is_empty() {
        v.push(Cond::Eq("extendattribute", q.extendattribute.clone()));
    }
    if let Some(x) = q.smallsideimagewidth.get() {
        v.push(Cond::EqI64("smallsideimagewidth", x as i64));
    }
    if !q.axletype.is_empty() {
        v.push(Cond::Eq("axletype", q.axletype.clone()));
    }
    if let Some(x) = q.smallsideimageheight.get() {
        v.push(Cond::EqI64("smallsideimageheight", x as i64));
    }
    if let Some(x) = q.platecolorcode.get() {
        v.push(Cond::EqI64("platecolorcode", x as i64));
    }
    if !q.platecolor.is_empty() {
        v.push(Cond::Eq("platecolor", q.platecolor.clone()));
    }
    if !q.cover.is_empty() {
        v.push(Cond::Eq("cover", q.cover.clone()));
    }
    if let Some(x) = q.averageauthoritative.get() {
        v.push(Cond::EqI64("averageauthoritative", x as i64));
    }
    if let Some(x) = q.headlanecode.get() {
        v.push(Cond::EqI64("headlanecode", x as i64));
    }
    if let Some(x) = q.specialvehicle.get() {
        v.push(Cond::EqI64("specialvehicle", x as i64));
    }
    if let Some(x) = q.carlength.get() {
        v.push(Cond::EqI64("carlength", x as i64));
    }
    if !q.resulttype.is_empty() {
        v.push(Cond::Eq("resulttype", q.resulttype.clone()));
    }
    if let Some(x) = q.carhight.get() {
        v.push(Cond::EqI64("carhight", x as i64));
    }
    if let Some(x) = q.carmodelscode.get() {
        v.push(Cond::EqI64("carmodelscode", x as i64));
    }
    if !q.carmodels.is_empty() {
        v.push(Cond::Eq("carmodels", q.carmodels.clone()));
    }
    if !q.laneposition.is_empty() {
        v.push(Cond::Eq("laneposition", q.laneposition.clone()));
    }
    if let Some(x) = q.firstauthoritative.get() {
        v.push(Cond::EqI64("firstauthoritative", x as i64));
    }
    if let Some(x) = q.tailplateimageheight.get() {
        v.push(Cond::EqI64("tailplateimageheight", x as i64));
    }
    if let Some(x) = q.axlecount.get() {
        v.push(Cond::EqI64("axlecount", x as i64));
    }
    if let Some(x) = q.plateimagewidth.get() {
        v.push(Cond::EqI64("plateimagewidth", x as i64));
    }
    if !q.specialclass.is_empty() {
        v.push(Cond::Eq("specialclass", q.specialclass.clone()));
    }
    if !q.tailplatenumber.is_empty() {
        v.push(Cond::Eq("tailplatenumber", q.tailplatenumber.clone()));
    }
    if !q.tailimage.is_empty() {
        v.push(Cond::Eq("tailimage", q.tailimage.clone()));
    }
    if let Some(x) = q.sidecapturetimeunix.get() {
        v.push(Cond::EqI64("sidecapturetimeunix", x));
    }
    if let Some(t) = q.sidecapturetime.utc() {
        v.push(Cond::EqTimestamp("sidecapturetime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.sidelanecode.get() {
        v.push(Cond::EqI64("sidelanecode", x as i64));
    }
    if let Some(x) = q.wheelbase.get() {
        v.push(Cond::EqI64("wheelbase", x as i64));
    }
    if !q.attached.is_empty() {
        v.push(Cond::Eq("attached", q.attached.clone()));
    }
    if let Some(x) = q.wheelcount.get() {
        v.push(Cond::EqI64("wheelcount", x as i64));
    }
    if !q.guid.is_empty() {
        v.push(Cond::Eq("guid", q.guid.clone()));
    }
    if let Some(x) = q.sideimagewidth.get() {
        v.push(Cond::EqI64("sideimagewidth", x as i64));
    }
    if let Some(x) = q.plateimageheight.get() {
        v.push(Cond::EqI64("plateimageheight", x as i64));
    }
    if !q.datasource.is_empty() {
        v.push(Cond::Eq("datasource", q.datasource.clone()));
    }
    if !q.carclass.is_empty() {
        v.push(Cond::Eq("carclass", q.carclass.clone()));
    }
    if !q.gantryid.is_empty() {
        v.push(Cond::Eq("gantryid", q.gantryid.clone()));
    }
    if !q.smallsideimage.is_empty() {
        v.push(Cond::Eq("smallsideimage", q.smallsideimage.clone()));
    }
    if let Some(x) = q.headimageheight.get() {
        v.push(Cond::EqI64("headimageheight", x as i64));
    }
    if let Some(x) = q.sidescenetypecode.get() {
        v.push(Cond::EqI64("sidescenetypecode", x as i64));
    }
    if !q.sidescenetype.is_empty() {
        v.push(Cond::Eq("sidescenetype", q.sidescenetype.clone()));
    }
    if let Some(x) = q.tailimagewidth.get() {
        v.push(Cond::EqI64("tailimagewidth", x as i64));
    }
    if !q.envstate.is_empty() {
        v.push(Cond::Eq("envstate", q.envstate.clone()));
    }
    if let Some(x) = q.headscenetypecode.get() {
        v.push(Cond::EqI64("headscenetypecode", x as i64));
    }
    if !q.headscenetype.is_empty() {
        v.push(Cond::Eq("headscenetype", q.headscenetype.clone()));
    }
    if let Some(x) = q.sidedrivingdirectioncode.get() {
        v.push(Cond::EqI64("sidedrivingdirectioncode", x as i64));
    }
    if !q.sidedrivingdirection.is_empty() {
        v.push(Cond::Eq("sidedrivingdirection", q.sidedrivingdirection.clone()));
    }
    if let Some(x) = q.sideimageheight.get() {
        v.push(Cond::EqI64("sideimageheight", x as i64));
    }
    if !q.speed.is_empty() {
        v.push(Cond::Eq("speed", q.speed.clone()));
    }
    if !q.tailplateimage.is_empty() {
        v.push(Cond::Eq("tailplateimage", q.tailplateimage.clone()));
    }
    if let Some(x) = q.headdrivingdirectioncode.get() {
        v.push(Cond::EqI64("headdrivingdirectioncode", x as i64));
    }
    if !q.headdrivingdirection.is_empty() {
        v.push(Cond::Eq("headdrivingdirection", q.headdrivingdirection.clone()));
    }
    if !q.cartype.is_empty() {
        v.push(Cond::Eq("cartype", q.cartype.clone()));
    }
    if !q.plateimage.is_empty() {
        v.push(Cond::Eq("plateimage", q.plateimage.clone()));
    }
    if !q.changelane.is_empty() {
        v.push(Cond::Eq("changelane", q.changelane.clone()));
    }
    if !q.sideimage.is_empty() {
        v.push(Cond::Eq("sideimage", q.sideimage.clone()));
    }
    if !q.tailplateposition.is_empty() {
        v.push(Cond::Eq("tailplateposition", q.tailplateposition.clone()));
    }
    if let Some(x) = q.headimagewidth.get() {
        v.push(Cond::EqI64("headimagewidth", x as i64));
    }
    if !q.headimage.is_empty() {
        v.push(Cond::Eq("headimage", q.headimage.clone()));
    }
    if let Some(x) = q.carweight.get() {
        v.push(Cond::EqI64("carweight", x as i64));
    }
    if let Some(x) = q.tailimageheight.get() {
        v.push(Cond::EqI64("tailimageheight", x as i64));
    }
    if !q.devicecode.is_empty() {
        v.push(Cond::Eq("devicecode", q.devicecode.clone()));
    }
    if !q.platenumber.is_empty() {
        v.push(Cond::Eq("platenumber", q.platenumber.clone()));
    }
    if let Some(x) = q.tailplatecolorcode.get() {
        v.push(Cond::EqI64("tailplatecolorcode", x as i64));
    }
    if !q.tailplatecolor.is_empty() {
        v.push(Cond::Eq("tailplatecolor", q.tailplatecolor.clone()));
    }
    if let Some(x) = q.uploadtimeunix.get() {
        v.push(Cond::EqI64("uploadtimeunix", x));
    }
    if let Some(t) = q.uploadtime.utc() {
        v.push(Cond::EqTimestamp("uploadtime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.impostoraxlecount.get() {
        v.push(Cond::EqI64("impostoraxlecount", x as i64));
    }
    if let Some(x) = q.taillanecode.get() {
        v.push(Cond::EqI64("taillanecode", x as i64));
    }
    if let Some(x) = q.siteid.get() {
        v.push(Cond::EqI64("siteid", x as i64));
    }
    if let Some(x) = q.headcapturetimeunix.get() {
        v.push(Cond::EqI64("headcapturetimeunix", x));
    }
    if let Some(t) = q.headcapturetime.utc() {
        v.push(Cond::EqTimestamp("headcapturetime", crate::utils::format_datetime(&t).into()));
    }
    if !q.plateposition.is_empty() {
        v.push(Cond::Eq("plateposition", q.plateposition.clone()));
    }
    if let Some(x) = q.tailplateimagewidth.get() {
        v.push(Cond::EqI64("tailplateimagewidth", x as i64));
    }
    if let Some(t) = q.loadtime.utc() {
        v.push(Cond::EqTimestamp("loadtime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.gradelevel.get() {
        v.push(Cond::EqI64("gradelevel", x as i64));
    }
    if !q.datauuid.is_empty() {
        v.push(Cond::Eq("datauuid", q.datauuid.clone()));
    }
    if !q.reserve1.is_empty() {
        v.push(Cond::Eq("reserve1", q.reserve1.clone()));
    }
    if !q.reserve2.is_empty() {
        v.push(Cond::Eq("reserve2", q.reserve2.clone()));
    }
    if !q.reserve3.is_empty() {
        v.push(Cond::Eq("reserve3", q.reserve3.clone()));
    }
    v
}

pub fn station_capture_filters(q: &OdsRtSzdnSnapshotFlowStationcaptureAddcode) -> Vec<Cond> {
    let mut v = vec![];
    if let Some(x) = q.big_id.get() {
        v.push(Cond::EqI64("big_id", x));
    }
    if !q.datasource.is_empty() {
        v.push(Cond::Eq("datasource", q.datasource.clone()));
    }
    if !q.cameratype.is_empty() {
        v.push(Cond::Eq("cameratype", q.cameratype.clone()));
    }
    if !q.deviceid.is_empty() {
        v.push(Cond::Eq("deviceid", q.deviceid.clone()));
    }
    if !q.deviceip.is_empty() {
        v.push(Cond::Eq("deviceip", q.deviceip.clone()));
    }
    if !q.tollcode.is_empty() {
        v.push(Cond::Eq("tollcode", q.tollcode.clone()));
    }
    if !q.tollname.is_empty() {
        v.push(Cond::Like("tollname", q.tollname.clone()));
    }
    if let Some(x) = q.orgcode.get() {
        v.push(Cond::EqI64("orgcode", x));
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
        v.push(Cond::EqTimestamp("snapshottime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.receivedtimeunix.get() {
        v.push(Cond::EqI64("receivedtimeunix", x));
    }
    if let Some(t) = q.receivedtime.utc() {
        v.push(Cond::EqTimestamp("receivedtime", crate::utils::format_datetime(&t).into()));
    }
    if !q.platenumber.is_empty() {
        v.push(Cond::Eq("platenumber", q.platenumber.clone()));
    }
    if let Some(x) = q.platecolorcode.get() {
        v.push(Cond::EqI64("platecolorcode", x as i64));
    }
    if !q.platecolor.is_empty() {
        v.push(Cond::Eq("platecolor", q.platecolor.clone()));
    }
    if let Some(x) = q.platetypecode.get() {
        v.push(Cond::EqI64("platetypecode", x as i64));
    }
    if !q.platetype.is_empty() {
        v.push(Cond::Eq("platetype", q.platetype.clone()));
    }
    if let Some(x) = q.plateconfidence.get() {
        v.push(Cond::EqI64("plateconfidence", x as i64));
    }
    if !q.carbrand.is_empty() {
        v.push(Cond::Eq("carbrand", q.carbrand.clone()));
    }
    if let Some(x) = q.carcolorcode.get() {
        v.push(Cond::EqI64("carcolorcode", x as i64));
    }
    if !q.carcolor.is_empty() {
        v.push(Cond::Eq("carcolor", q.carcolor.clone()));
    }
    if let Some(x) = q.cartypecode.get() {
        v.push(Cond::EqI64("cartypecode", x as i64));
    }
    if !q.cartype.is_empty() {
        v.push(Cond::Eq("cartype", q.cartype.clone()));
    }
    if let Some(x) = q.cardirectioncode.get() {
        v.push(Cond::EqI64("cardirectioncode", x as i64));
    }
    if !q.cardirection.is_empty() {
        v.push(Cond::Eq("cardirection", q.cardirection.clone()));
    }
    if !q.snappicturepath.is_empty() {
        v.push(Cond::Eq("snappicturepath", q.snappicturepath.clone()));
    }
    if let Some(t) = q.loadtime.utc() {
        v.push(Cond::EqTimestamp("loadtime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.gradelevel.get() {
        v.push(Cond::EqI64("gradelevel", x as i64));
    }
    if !q.datauuid.is_empty() {
        v.push(Cond::Eq("datauuid", q.datauuid.clone()));
    }
    if !q.maindirection.is_empty() {
        v.push(Cond::Eq("maindirection", q.maindirection.clone()));
    }
    if !q.maindirectionname.is_empty() {
        v.push(Cond::Like("maindirectionname", q.maindirectionname.clone()));
    }
    if !q.reserve3.is_empty() {
        v.push(Cond::Eq("reserve3", q.reserve3.clone()));
    }
    if !q.apply_time1.is_empty() {
        v.push(Cond::Gte("snapshottime", q.apply_time1.clone()));
    }
    if !q.apply_time2.is_empty() {
        v.push(Cond::Lte("snapshottime", q.apply_time2.clone()));
    }
    v
}

pub fn gantry_filters(q: &OdsSzdnGantry) -> Vec<Cond> {
    let mut v = vec![];
    if !q.id.is_empty() {
        v.push(Cond::Eq("id", q.id.clone()));
    }
    if !q.gantry_code.is_empty() {
        v.push(Cond::Eq("gantry_code", q.gantry_code.clone()));
    }
    if !q.gantry_name.is_empty() {
        v.push(Cond::Like("gantry_name", q.gantry_name.clone()));
    }
    if !q.road_code.is_empty() {
        v.push(Cond::Eq("road_code", q.road_code.clone()));
    }
    if !q.section_code.is_empty() {
        v.push(Cond::Eq("section_code", q.section_code.clone()));
    }
    if !q.toll_code.is_empty() {
        v.push(Cond::Eq("toll_code", q.toll_code.clone()));
    }
    if !q.org_code.is_empty() {
        v.push(Cond::Eq("org_code", q.org_code.clone()));
    }
    if !q.hex_code.is_empty() {
        v.push(Cond::Eq("hex_code", q.hex_code.clone()));
    }
    if !q.direction.is_empty() {
        v.push(Cond::Eq("direction", q.direction.clone()));
    }
    if !q.pile_no.is_empty() {
        v.push(Cond::Eq("pile_no", q.pile_no.clone()));
    }
    if !q.lon.is_empty() {
        v.push(Cond::Eq("lon", q.lon.clone()));
    }
    if !q.lat.is_empty() {
        v.push(Cond::Eq("lat", q.lat.clone()));
    }
    if !q.is_virtual.is_empty() {
        v.push(Cond::Eq("is_virtual", q.is_virtual.clone()));
    }
    if !q.mileage.is_empty() {
        v.push(Cond::Eq("mileage", q.mileage.clone()));
    }
    if !q.boundary_gantry_type.is_empty() {
        v.push(Cond::Eq("boundary_gantry_type", q.boundary_gantry_type.clone()));
    }
    if !q.gantry_type.is_empty() {
        v.push(Cond::Eq("gantry_type", q.gantry_type.clone()));
    }
    if !q.city_code.is_empty() {
        v.push(Cond::Eq("city_code", q.city_code.clone()));
    }
    if !q.district_name.is_empty() {
        v.push(Cond::Like("district_name", q.district_name.clone()));
    }
    if !q.belong_group.is_empty() {
        v.push(Cond::Eq("belong_group", q.belong_group.clone()));
    }
    if !q.gantry_code_merge.is_empty() {
        v.push(Cond::Eq("gantry_code_merge", q.gantry_code_merge.clone()));
    }
    if !q.gantry_name_alias.is_empty() {
        v.push(Cond::Eq("gantry_name_alias", q.gantry_name_alias.clone()));
    }
    v
}

pub fn gantry_ip_filters(q: &OdsSzdnGantryIp) -> Vec<Cond> {
    let mut v = vec![];
    if let Some(x) = q.id.get() {
        v.push(Cond::EqI64("id", x));
    }
    if !q.gantry_code.is_empty() {
        v.push(Cond::Eq("gantry_code", q.gantry_code.clone()));
    }
    if !q.gantry_name.is_empty() {
        v.push(Cond::Like("gantry_name", q.gantry_name.clone()));
    }
    if !q.org_code.is_empty() {
        v.push(Cond::Eq("org_code", q.org_code.clone()));
    }
    if !q.ip.is_empty() {
        v.push(Cond::Eq("ip", q.ip.clone()));
    }
    if !q.brand.is_empty() {
        v.push(Cond::Eq("brand", q.brand.clone()));
    }
    if !q.r#type.is_empty() {
        v.push(Cond::Eq("type", q.r#type.clone()));
    }
    v
}

pub fn vehicle_weight_filters(q: &OdsSzdnProvinceBorderVehicleWeightNewstructure) -> Vec<Cond> {
    let mut v = vec![];
    if !q.data_source.is_empty() {
        v.push(Cond::Eq("dataSource", q.data_source.clone()));
    }
    if !q.data_type.is_empty() {
        v.push(Cond::Eq("dataType", q.data_type.clone()));
    }
    if !q.plate_no.is_empty() {
        v.push(Cond::Eq("plateNo", q.plate_no.clone()));
    }
    if !q.site_id.is_empty() {
        v.push(Cond::Eq("siteId", q.site_id.clone()));
    }
    if !q.location.is_empty() {
        v.push(Cond::Eq("location", q.location.clone()));
    }
    if let Some(x) = q.drive_no.get() {
        v.push(Cond::EqI64("driveNo", x));
    }
    if !q.plate_color.is_empty() {
        v.push(Cond::Eq("plateColor", q.plate_color.clone()));
    }
    if !q.plate_color_code.is_empty() {
        v.push(Cond::Eq("plateColorCode", q.plate_color_code.clone()));
    }
    if !q.plate_type.is_empty() {
        v.push(Cond::Eq("plateType", q.plate_type.clone()));
    }
    if !q.plate_type_code.is_empty() {
        v.push(Cond::Eq("plateTypeCode", q.plate_type_code.clone()));
    }
    if !q.vehicle_color.is_empty() {
        v.push(Cond::Eq("vehicleColor", q.vehicle_color.clone()));
    }
    if !q.vehicle_color_code.is_empty() {
        v.push(Cond::Eq("vehicleColorCode", q.vehicle_color_code.clone()));
    }
    if !q.vehicle_type.is_empty() {
        v.push(Cond::Eq("vehicleType", q.vehicle_type.clone()));
    }
    if !q.vehicle_type_code.is_empty() {
        v.push(Cond::Eq("vehicleTypeCode", q.vehicle_type_code.clone()));
    }
    if let Some(x) = q.vehicle_speed.get() {
        v.push(Cond::EqI64("vehicleSpeed", x));
    }
    if let Some(x) = q.is_overweight.get() {
        v.push(Cond::EqI64("isOverweight", x));
    }
    if let Some(x) = q.axle_num.get() {
        v.push(Cond::EqI64("axleNum", x));
    }
    if let Some(x) = q.over_weight.get() {
        v.push(Cond::EqI64("overWeight", x));
    }
    if let Some(x) = q.vehicle_weight.get() {
        v.push(Cond::EqI64("vehicleWeight", x));
    }
    if let Some(x) = q.limit_weight.get() {
        v.push(Cond::EqI64("limitWeight", x));
    }
    if let Some(x) = q.check_time_unix.get() {
        v.push(Cond::EqI64("checkTimeUnix", x));
    }
    if let Some(t) = q.check_time.utc() {
        v.push(Cond::EqTimestamp("checkTime", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.axle_model.get() {
        v.push(Cond::EqI64("axleModel", x));
    }
    if let Some(x) = q.load_rate.get() {
        v.push(Cond::EqI64("loadRate", x));
    }
    if !q.axle_array.is_empty() {
        v.push(Cond::Eq("axleArray", q.axle_array.clone()));
    }
    if !q.weighing_images_arry.is_empty() {
        v.push(Cond::Eq("weighingImagesArry", q.weighing_images_arry.clone()));
    }
    if let Some(t) = q.load_time.utc() {
        v.push(Cond::EqTimestamp("load_time", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.grade_level.get() {
        v.push(Cond::EqI64("grade_level", x));
    }
    if !q.datauuid.is_empty() {
        v.push(Cond::Eq("datauuid", q.datauuid.clone()));
    }
    if !q.reserve1.is_empty() {
        v.push(Cond::Eq("reserve1", q.reserve1.clone()));
    }
    if !q.reserve2.is_empty() {
        v.push(Cond::Eq("reserve2", q.reserve2.clone()));
    }
    if !q.reserve3.is_empty() {
        v.push(Cond::Eq("reserve3", q.reserve3.clone()));
    }
    v
}

pub fn section_filters(q: &OdsSzdnSection) -> Vec<Cond> {
    let mut v = vec![];
    if !q.id.is_empty() {
        v.push(Cond::Eq("id", q.id.clone()));
    }
    if !q.road_code.is_empty() {
        v.push(Cond::Eq("road_code", q.road_code.clone()));
    }
    if !q.road_name.is_empty() {
        v.push(Cond::Like("road_name", q.road_name.clone()));
    }
    if !q.section_code.is_empty() {
        v.push(Cond::Eq("section_code", q.section_code.clone()));
    }
    if !q.section_name.is_empty() {
        v.push(Cond::Like("section_name", q.section_name.clone()));
    }
    if let Some(x) = q.start_pile_no.get() {
        v.push(Cond::EqI64("start_pile_no", x));
    }
    if let Some(x) = q.end_pile_no.get() {
        v.push(Cond::EqI64("end_pile_no", x));
    }
    if !q.org_code.is_empty() {
        v.push(Cond::Eq("org_code", q.org_code.clone()));
    }
    if !q.org_name.is_empty() {
        v.push(Cond::Like("org_name", q.org_name.clone()));
    }
    if !q.org_level_code.is_empty() {
        v.push(Cond::Eq("org_level_code", q.org_level_code.clone()));
    }
    if !q.org_category.is_empty() {
        v.push(Cond::Eq("org_category", q.org_category.clone()));
    }
    if let Some(x) = q.mileage.get() {
        v.push(Cond::EqI64("mileage", x));
    }
    if let Some(t) = q.open_date.utc() {
        v.push(Cond::EqTimestamp("open_date", crate::utils::format_datetime(&t).into()));
    }
    v
}

pub fn toll_filters(q: &OdsSzdnToll) -> Vec<Cond> {
    let mut v = vec![];
    if !q.id.is_empty() {
        v.push(Cond::Eq("id", q.id.clone()));
    }
    if !q.road_code.is_empty() {
        v.push(Cond::Eq("road_code", q.road_code.clone()));
    }
    if !q.id_card.is_empty() {
        v.push(Cond::Eq("id_card", q.id_card.clone()));
    }
    if !q.toll_code.is_empty() {
        v.push(Cond::Eq("toll_code", q.toll_code.clone()));
    }
    if !q.toll_name.is_empty() {
        v.push(Cond::Like("toll_name", q.toll_name.clone()));
    }
    if !q.pile_no.is_empty() {
        v.push(Cond::Eq("pile_no", q.pile_no.clone()));
    }
    if !q.org_name.is_empty() {
        v.push(Cond::Like("org_name", q.org_name.clone()));
    }
    if !q.hex_code.is_empty() {
        v.push(Cond::Eq("hex_code", q.hex_code.clone()));
    }
    if !q.state_code.is_empty() {
        v.push(Cond::Eq("state_code", q.state_code.clone()));
    }
    if !q.org_code.is_empty() {
        v.push(Cond::Eq("org_code", q.org_code.clone()));
    }
    if !q.longitude.is_empty() {
        v.push(Cond::Eq("longitude", q.longitude.clone()));
    }
    if !q.latitude.is_empty() {
        v.push(Cond::Eq("latitude", q.latitude.clone()));
    }
    if let Some(t) = q.open_date.utc() {
        v.push(Cond::EqTimestamp("open_date", crate::utils::format_datetime(&t).into()));
    }
    if !q.toll_alias_name.is_empty() {
        v.push(Cond::Like("toll_alias_name", q.toll_alias_name.clone()));
    }
    if !q.in_monitor_resource.is_empty() {
        v.push(Cond::Eq("in_monitor_resource", q.in_monitor_resource.clone()));
    }
    if !q.lane_monitor_resource.is_empty() {
        v.push(Cond::Eq("lane_monitor_resource", q.lane_monitor_resource.clone()));
    }
    if !q.square_monitor_resource.is_empty() {
        v.push(Cond::Eq("square_monitor_resource", q.square_monitor_resource.clone()));
    }
    if !q.dynamic_monitor_resource.is_empty() {
        v.push(Cond::Eq("dynamic_monitor_resource", q.dynamic_monitor_resource.clone()));
    }
    if !q.toll_code_merge.is_empty() {
        v.push(Cond::Eq("toll_code_merge", q.toll_code_merge.clone()));
    }
    if !q.state_code_merge.is_empty() {
        v.push(Cond::Eq("state_code_merge", q.state_code_merge.clone()));
    }
    if !q.toll_name_merge.is_empty() {
        v.push(Cond::Eq("toll_name_merge", q.toll_name_merge.clone()));
    }
    if !q.section_code.is_empty() {
        v.push(Cond::Eq("section_code", q.section_code.clone()));
    }
    if !q.toll_org_code.is_empty() {
        v.push(Cond::Eq("toll_org_code", q.toll_org_code.clone()));
    }
    if !q.is_access.is_empty() {
        v.push(Cond::Eq("is_access", q.is_access.clone()));
    }
    v
}

pub fn toll_station_ip_filters(q: &OdsSzdnTollStationIp) -> Vec<Cond> {
    let mut v = vec![];
    if !q.toll_code.is_empty() {
        v.push(Cond::Eq("toll_code", q.toll_code.clone()));
    }
    if !q.toll_name.is_empty() {
        v.push(Cond::Like("toll_name", q.toll_name.clone()));
    }
    if !q.org_code.is_empty() {
        v.push(Cond::Eq("org_code", q.org_code.clone()));
    }
    if !q.ip.is_empty() {
        v.push(Cond::Eq("ip", q.ip.clone()));
    }
    if !q.brand.is_empty() {
        v.push(Cond::Eq("brand", q.brand.clone()));
    }
    v
}

pub fn org_filters(q: &OdsYhglVBaseOrg) -> Vec<Cond> {
    let mut v = vec![];
    if !q.big_id.is_empty() {
        v.push(Cond::Eq("big_id", q.big_id.clone()));
    }
    if !q.org_code.is_empty() {
        v.push(Cond::Eq("org_code", q.org_code.clone()));
    }
    if !q.org_name.is_empty() {
        v.push(Cond::Like("org_name", q.org_name.clone()));
    }
    if !q.org_short_name.is_empty() {
        v.push(Cond::Like("org_short_name", q.org_short_name.clone()));
    }
    if !q.org_parent_id.is_empty() {
        v.push(Cond::Eq("org_parent_id", q.org_parent_id.clone()));
    }
    if !q.org_level_code.is_empty() {
        v.push(Cond::Eq("org_level_code", q.org_level_code.clone()));
    }
    if !q.org_is_virtual.is_empty() {
        v.push(Cond::Eq("org_is_virtual", q.org_is_virtual.clone()));
    }
    if !q.org_maintenance.is_empty() {
        v.push(Cond::Eq("org_maintenance", q.org_maintenance.clone()));
    }
    if let Some(x) = q.org_sequence.get() {
        v.push(Cond::EqI64("org_sequence", x));
    }
    if !q.org_is_manager.is_empty() {
        v.push(Cond::Eq("org_is_manager", q.org_is_manager.clone()));
    }
    if !q.org_is_deleted.is_empty() {
        v.push(Cond::Eq("org_is_deleted", q.org_is_deleted.clone()));
    }
    if !q.org_category.is_empty() {
        v.push(Cond::Eq("org_category", q.org_category.clone()));
    }
    if !q.org_is_authorized.is_empty() {
        v.push(Cond::Eq("org_is_authorized", q.org_is_authorized.clone()));
    }
    if !q.org_address.is_empty() {
        v.push(Cond::Eq("org_address", q.org_address.clone()));
    }
    if !q.org_is_yh_autarky.is_empty() {
        v.push(Cond::Eq("org_is_yh_autarky", q.org_is_yh_autarky.clone()));
    }
    if let Some(t) = q.load_time.utc() {
        v.push(Cond::EqTimestamp("load_time", crate::utils::format_datetime(&t).into()));
    }
    if let Some(x) = q.grade_level.get() {
        v.push(Cond::EqI64("grade_level", x as i64));
    }
    v
}

pub fn location_dict_filters(q: &ZdataLocationDict) -> Vec<Cond> {
    let mut v = vec![];
    if let Some(x) = q.id.get() {
        v.push(Cond::EqI64("id", x));
    }
    if !q.r#type.is_empty() {
        v.push(Cond::Eq("type", q.r#type.clone()));
    }
    if !q.name.is_empty() {
        v.push(Cond::Like("name", q.name.clone()));
    }
    if !q.raw_code.is_empty() {
        v.push(Cond::Eq("raw_code", q.raw_code.clone()));
    }
    if !q.standard_code.is_empty() {
        v.push(Cond::Eq("standard_code", q.standard_code.clone()));
    }
    if !q.roadcode.is_empty() {
        v.push(Cond::Eq("roadcode", q.roadcode.clone()));
    }
    if !q.roadname.is_empty() {
        v.push(Cond::Like("roadname", q.roadname.clone()));
    }
    if !q.sectioncode.is_empty() {
        v.push(Cond::Eq("sectioncode", q.sectioncode.clone()));
    }
    if !q.sectionname.is_empty() {
        v.push(Cond::Like("sectionname", q.sectionname.clone()));
    }
    if !q.tollcode.is_empty() {
        v.push(Cond::Eq("tollcode", q.tollcode.clone()));
    }
    if !q.tollname.is_empty() {
        v.push(Cond::Like("tollname", q.tollname.clone()));
    }
    if !q.orgcode.is_empty() {
        v.push(Cond::Eq("orgcode", q.orgcode.clone()));
    }
    if !q.orgname.is_empty() {
        v.push(Cond::Like("orgname", q.orgname.clone()));
    }
    if let Some(t) = q.created_at.utc() {
        v.push(Cond::EqTimestamp("created_at", crate::utils::format_datetime(&t).into()));
    }
    if let Some(t) = q.updated_at.utc() {
        v.push(Cond::EqTimestamp("updated_at", crate::utils::format_datetime(&t).into()));
    }
    v
}

pub fn trail_tracks_filters(q: &ZdataTrailTracks) -> Vec<Cond> {
    let mut v = vec![];
    if !q.uuid.is_empty() {
        v.push(Cond::Eq("uuid", q.uuid.clone()));
    }
    if let Some(x) = q.r#type.get() {
        v.push(Cond::EqI64("type", x as i64));
    }
    if let Some(x) = q.point_count.get() {
        v.push(Cond::EqI64("point_count", x));
    }
    if !q.plate_key.is_empty() {
        v.push(Cond::Eq("plate_key", q.plate_key.clone()));
    }
    if let Some(t) = q.enter_time.utc() {
        v.push(Cond::EqTimestamp("enter_time", crate::utils::format_datetime(&t).into()));
    }
    if let Some(t) = q.exit_time.utc() {
        v.push(Cond::EqTimestamp("exit_time", crate::utils::format_datetime(&t).into()));
    }
    if !q.trail_points.is_empty() {
        v.push(Cond::Eq("trail_points", q.trail_points.clone()));
    }
    v
}
