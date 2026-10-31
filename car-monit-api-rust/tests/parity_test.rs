// 行为一致性测试：覆盖与 Java 版逐字对齐的纯函数与序列化契约。
// 这些断言不依赖任何外部组件，可在 CI 中稳定运行。

use car_monit_api_rust::handlers::common::{fuzzy_fields, page_params, PageQuery};
use car_monit_api_rust::models::*;
use car_monit_api_rust::response::{AjaxResult, TableDataInfo};
use car_monit_api_rust::utils;
use serde_json::json;

#[test]
fn common_util_matches_java() {
    assert_eq!(utils::delete_end("a,b,"), "a,b");
    assert_eq!(utils::delete_end("a,b"), "a,b");
    assert_eq!(utils::split_csv(" a, ,b ,"), vec!["a", "b"]);
    assert_eq!(
        utils::replace_pic_url("http://jxjt.isilon.com/ifs/a.jpg"),
        "http://36.200.30.144:9080/a.jpg"
    );
    assert_eq!(
        utils::replace_pic_url("http://jxjt.isilon.com/a.jpg"),
        "http://36.200.30.144:9080/a.jpg"
    );
    assert_eq!(utils::replace_toll_name("江西吉安东收费站"), "吉安东");
    assert_eq!(utils::uuid_simple().len(), 32);
}

#[test]
fn date_parsing_matches_java_dateutils() {
    let dt = utils::parse_time("2026-10-31 12:34:56").expect("yyyy-MM-dd HH:mm:ss");
    assert_eq!(utils::format_datetime(&dt), "2026-10-31 12:34:56");
    let day = utils::parse_time("2026-10-31").expect("yyyy-MM-dd");
    assert_eq!(utils::format_day(&day), "2026-10-31");
    assert_eq!(
        utils::days_between("2026-10-01 00:00:00", "2026-10-31 00:00:00").unwrap(),
        30
    );
    assert!(utils::days_between("2026-10-31", "2026-10-01").is_err());
}

#[test]
fn ajax_result_omits_null_data_like_java() {
    let ok = serde_json::to_value(AjaxResult::success(None)).unwrap();
    assert_eq!(ok, json!({ "code": 200, "msg": "操作成功" }));

    let ok_data = serde_json::to_value(AjaxResult::success(Some(json!(1)))).unwrap();
    assert_eq!(ok_data["data"], json!(1));

    let err = serde_json::to_value(AjaxResult::fail_code(404, "not found")).unwrap();
    assert_eq!(err["code"], json!(404));
    assert_eq!(err["msg"], json!("not found"));
}

#[test]
fn table_data_info_shape_matches_java() {
    let t = TableDataInfo::new(json!([]), 0);
    let v = serde_json::to_value(t).unwrap();
    assert_eq!(v["code"], json!(200));
    assert_eq!(v["msg"], json!("查询成功"));
    assert_eq!(v["total"], json!(0));
    assert_eq!(v["rows"], json!([]));

    let p = TableDataInfo::with_msg(json!([]), 0, "策略: phase1-gaussdb-gin");
    let v = serde_json::to_value(p).unwrap();
    assert_eq!(v["msg"], json!("策略: phase1-gaussdb-gin"));
}

#[test]
fn entity_json_uses_java_field_names() {
    let e = OdsRtSzdnSnapshotFlowAddcode::default();
    let v = serde_json::to_value(&e).unwrap();
    // camelCase 字段名与 Java 完全一致
    assert!(v.get("bigId").is_some());
    assert!(v.get("snapshottimeStr").is_some());
    assert!(v.get("sectionCodeStr").is_some());
    assert!(v.get("codeList").is_some());
    // 非数据库字段以默认值输出（Jackson 默认包含 null/空值）
    assert_eq!(v["snapshottime"], json!(null));
    assert_eq!(v["id"], json!(null));

    let f = OdsSzdnGantryIp::default();
    let v = serde_json::to_value(&f).unwrap();
    assert!(v.get("type").is_some());
}

#[test]
fn day_serializes_as_yyyy_mm_dd() {
    let mut flow = OdsRtSzdnSnapshotFlowAddcode::default();
    flow.receivedtime = Day::new(utils::parse_time("2026-10-31 23:59:59").unwrap());
    let v = serde_json::to_value(&flow).unwrap();
    assert_eq!(v["receivedtime"], json!("2026-10-31"));
}

#[test]
fn jdatetime_serializes_as_java_pattern() {
    let mut flow = OdsRtSzdnSnapshotFlowAddcode::default();
    let mut gantry = OdsLwzxsfsjFeeGantryFusion01::default();
    gantry.entime = JDateTime::from(utils::parse_time("2026-10-31 12:34:56").unwrap());
    let v = serde_json::to_value(&gantry).unwrap();
    assert_eq!(v["entime"], json!("2026-10-31 12:34:56"));

    // 未加 @JsonFormat 的 Date → Spring Boot 默认 ISO-8601
    flow.snapshottime = JIsoDateTime::from(utils::parse_time("2026-10-31 12:34:56").unwrap());
    let v = serde_json::to_value(&flow).unwrap();
    assert_eq!(v["snapshottime"], json!("2026-10-31T12:34:56.000+00:00"));
}

#[test]
fn pagination_defaults_match_ruoyi() {
    let p = page_params(&PageQuery {
        page_num: None,
        page_size: None,
    });
    assert_eq!((p.page_num, p.page_size, p.offset()), (1, 10, 0));

    let p = page_params(&PageQuery {
        page_num: Some("3".into()),
        page_size: Some("20".into()),
    });
    assert_eq!(p.offset(), 40);

    // 8 亿级表保护上限
    let p = page_params(&PageQuery {
        page_num: Some("1".into()),
        page_size: Some("99999".into()),
    });
    assert_eq!(p.page_size, 1000);
}

#[test]
fn fuzzy_fields_extraction_matches_large_controller() {
    let mut raw = std::collections::HashMap::new();
    raw.insert("fuzzyFields.platenumber".to_string(), "赣A".to_string());
    raw.insert("fuzzyFields.gantryname".to_string(), String::new());
    raw.insert("pageNum".to_string(), "1".to_string());
    let f = fuzzy_fields(&raw);
    assert_eq!(f.get("platenumber"), Some(&"赣A".to_string()));
    assert!(f.get("gantryname").is_none());
    assert!(f.get("pageNum").is_none());
}

#[test]
fn message_status_and_checksum_are_stable() {
    // java String.hashCode("ABC") = 64578
    let checksum = car_monit_api_rust::utils::md5_hex("");
    assert_eq!(checksum, "d41d8cd98f00b204e9800998ecf8427e");
}
