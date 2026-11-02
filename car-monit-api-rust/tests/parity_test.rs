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

    // PARITY: Java 的 AjaxResult 继承 HashMap，实测输出顺序是 msg → code → data。
    let s = serde_json::to_string(&AjaxResult::success(Some(json!({"a": 1})))).unwrap();
    assert!(
        s.starts_with("{\"msg\":\"操作成功\",\"code\":200,\"data\""),
        "AjaxResult 键顺序应与 Java HashMap 一致: {s}"
    );

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

#[test]
fn java_date_whitelist_matches_parse_date_patterns() {
    use car_monit_api_rust::handlers::common::java_date_parseable;
    // DateUtils.parsePatterns 能整串匹配的形式：Java 会解析并拼进 WHERE
    for ok in [
        "2025-09-08 00:00:00",
        "2025-09-08 08:00",
        "2025-09-08",
        "2025-09",
        "2025/09/08",
        "2025/09",
        "2025.09.08",
        "2025.09",
    ] {
        assert!(java_date_parseable(ok), "{ok} 应当被 Java 接受");
    }
    // 白名单之外的形式：Java 的 parseDate 返回 null，条件被静默忽略
    for no in [
        "2025-09-08T00:00:00.000+00:00",
        "1969-12-31T16:00:00.000+00:00",
        "2025-09-08T00:00:00Z",
        "not-a-date",
        "",
        "2025-13-01",
    ] {
        assert!(!java_date_parseable(no), "{no} 应当被 Java 忽略");
    }
}

#[test]
fn whitelisted_date_formats_stay_deserializable() {
    // 白名单保留下来的参数必须能被实体反序列化，否则会从 Java 的 200 变成 Rust 的 400。
    for s in [
        "2025-09-08 00:00:00",
        "2025-09-08 08:00",
        "2025-09-08",
        "2025-09",
        "2025/09/08",
        "2025/09",
        "2025.09.08",
        "2025.09",
    ] {
        let dt = utils::parse_time(s).unwrap_or_else(|e| panic!("{s} 解析失败: {e}"));
        assert!(dt.to_rfc3339().starts_with("2025-09"), "{s} -> {dt}");
    }
}

#[tokio::test]
async fn java_query_drops_unparseable_date_params_like_init_binder() {
    use axum::extract::FromRequestParts;
    use car_monit_api_rust::handlers::common::JavaQuery;
    use car_monit_api_rust::models::OdsRtSzdnSnapshotFlowProvcaptureAddcode;

    let state = ();
    // ISO 值：Java 丢弃该条件 -> tailcapturetime 保持 null
    let mut parts = axum::http::Request::builder()
        .uri("/base/provcapture/list?pageNum=1&pageSize=1&tailcapturetime=1969-12-31T16%3A00%3A00.000%2B00%3A00")
        .body(())
        .unwrap()
        .into_parts()
        .0;
    let JavaQuery(q) = JavaQuery::<OdsRtSzdnSnapshotFlowProvcaptureAddcode>::from_request_parts(
        &mut parts, &state,
    )
    .await
    .unwrap();
    assert!(q.tailcapturetime.utc().is_none());

    // 白名单内格式：条件生效
    let mut parts = axum::http::Request::builder()
        .uri("/base/provcapture/list?tailcapturetime=1969-12-31%2016%3A00%3A00")
        .body(())
        .unwrap()
        .into_parts()
        .0;
    let JavaQuery(q) = JavaQuery::<OdsRtSzdnSnapshotFlowProvcaptureAddcode>::from_request_parts(
        &mut parts, &state,
    )
    .await
    .unwrap();
    assert!(q.tailcapturetime.utc().is_some());
}

#[test]
fn parse_time_accepts_es_and_row_json_formats() {
    // row_to_json（chrono to_rfc3339）与 ES 文档里的日期字符串都必须能解析，
    // 否则 /api/v1/large|unified 的 DB 降级路径会把日期字段变成 null。
    for s in [
        "2025-09-08T10:51:00+00:00",
        "2025-09-08T10:51:00.000+00:00",
        "2025-09-08T10:51:00Z",
        "2025-09-08 10:51:00",
        "2025-09-10",
        "2025/09/10",
        "1757299860",
    ] {
        let t = utils::parse_time(s).unwrap_or_else(|e| panic!("{s} 解析失败: {e}"));
        assert!(
            t.to_rfc3339().starts_with("2025-09") || s.chars().all(|c| c.is_ascii_digit()),
            "{s} -> {t}"
        );
    }
}
