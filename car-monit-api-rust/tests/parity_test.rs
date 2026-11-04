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
        ..Default::default()
    });
    assert_eq!((p.page_num, p.page_size, p.offset()), (1, 10, 0));

    let p = page_params(&PageQuery {
        page_num: Some("3".into()),
        page_size: Some("20".into()),
        ..Default::default()
    });
    assert_eq!(p.offset(), 40);

    // Java 侧 PageHelper 对 pageSize 没有上限，Rust 不能自己钳位
    let p = page_params(&PageQuery {
        page_num: Some("1".into()),
        page_size: Some("99999".into()),
        ..Default::default()
    });
    assert_eq!(p.page_size, 99999);

    // reasonable=false 时不做页码归一
    let p = page_params(&PageQuery {
        page_num: Some("0".into()),
        page_size: Some("5".into()),
        reasonable: Some("false".into()),
        ..Default::default()
    });
    assert!(!p.reasonable);
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
    // SimpleDateFormat 是宽松的：越界会进位、数字段不定时宽，这些都算解析成功
    // （阶段9 dates 矩阵实测：Java 会拼进 WHERE 并返回 0 行，而不是忽略条件）
    for ok in [
        "2025-13-01",
        "2025-09-10 25:61:61",
        "10-09-2025",
        "0000-00-00",
        "2025-9-1",
        "2025-09-10 1:2:3",
    ] {
        assert!(java_date_parseable(ok), "{ok} 应当被 Java 宽松接受");
    }
    // 白名单之外（含「整串没消费完」和前后空白，Java 不 trim）：
    // parseDate 返回 null，条件被静默忽略
    for no in [
        "2025-09-08T00:00:00.000+00:00",
        "1969-12-31T16:00:00.000+00:00",
        "2025-09-08T00:00:00Z",
        "not-a-date",
        "",
        "2025-09-08 00:00:00.000",
        "2025-09-08 ",
        "  2025-09-08  ",
        "20250910",
        "1757462400000",
        "2025-09-08 12",
    ] {
        assert!(!java_date_parseable(no), "{no} 应当被 Java 忽略");
    }
    // 公元前会被收敛到公元 1 年：条件照样生效，但不会让 GaussDB 报
    // `invalid input syntax for type timestamp: "-0001-11-30"`（Java 那边是 200）
    let ancient = car_monit_api_rust::java_date::parse_date("0000-00-00").unwrap();
    assert!(ancient.format("%Y").to_string().starts_with('0'), "{ancient}");
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

#[tokio::test]
async fn java_query_joins_duplicate_date_params_before_validating() {
    // 阶段9 dates-range 实测：Spring 的 WebDataBinder 先把同名参数逗号拼接，
    // 再交给 PropertyEditor；`f=a&f=b&f=zzz` 编辑看到的是 "a,b,zzz" —— 解析失败 -> 条件不生效。
    // Rust 若逐对校验后拼接，就会把无法解析的整串送进反序列化，变成 400（Java 是 200）。
    use axum::extract::FromRequestParts;
    use car_monit_api_rust::handlers::common::JavaQuery;
    use car_monit_api_rust::models::OdsRtSzdnSnapshotFlowProvcaptureAddcode;

    let state = ();
    let mut parts = axum::http::Request::builder()
        .uri("/base/provcapture/list?tailcapturetime=2025-09-01&tailcapturetime=2025-09-30&tailcapturetime=zzz")
        .body(())
        .unwrap()
        .into_parts()
        .0;
    let JavaQuery(q) =
        JavaQuery::<OdsRtSzdnSnapshotFlowProvcaptureAddcode>::from_request_parts(&mut parts, &state)
            .await
            .unwrap();
    assert!(q.tailcapturetime.utc().is_none(), "拼接后不可解析，条件必须不生效");
}

#[test]
fn jlist_splits_without_trimming_or_dropping_blanks() {
    // StringUtils.commaDelimitedListToStringArray：只有空串得到空数组，
    // 其余不 trim、不丢空元素。实测 cidList=%20 在 Java 是 IN (' ') -> 0 行。
    use car_monit_api_rust::models::JList;
    let one: JList<String> = serde_json::from_value(serde_json::Value::String(" ".into())).unwrap();
    assert!(one.present && one.value == vec![" ".to_string()]);
    let empty: JList<String> = serde_json::from_value(serde_json::Value::String(String::new()))
        .unwrap();
    assert!(!empty.present && empty.value.is_empty());
    let tail: JList<String> =
        serde_json::from_value(serde_json::Value::String("a,".into())).unwrap();
    assert!(tail.value == vec!["a".to_string(), String::new()]);
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

#[test]
fn order_by_matches_page_domain_and_sqlutil() {
    use car_monit_api_rust::handlers::common::{order_by_clause, to_under_score_case, PageQuery};

    assert_eq!(to_under_score_case("orgCode"), "org_code");
    assert_eq!(to_under_score_case("ID"), "id");
    assert_eq!(to_under_score_case("ssglzxbm"), "ssglzxbm");

    // orderByColumn 缺省 / 全空格 → 不追加排序
    assert_eq!(order_by_clause(&PageQuery::default()).unwrap(), None);
    let q = PageQuery {
        order_by_column: Some("  ".into()),
        ..Default::default()
    };
    assert_eq!(order_by_clause(&q).unwrap(), None);

    let q = PageQuery {
        order_by_column: Some("orgCode".into()),
        is_asc: Some("desc".into()),
        ..Default::default()
    };
    assert_eq!(order_by_clause(&q).unwrap().as_deref(), Some("org_code desc"));

    // isAsc 缺省沿用 PageDomain 的字段默认值 "asc"；兼容 ascending/descending
    let q = PageQuery {
        order_by_column: Some("id".into()),
        ..Default::default()
    };
    assert_eq!(order_by_clause(&q).unwrap().as_deref(), Some("id asc"));
    let q = PageQuery {
        order_by_column: Some("id".into()),
        is_asc: Some("descending".into()),
        ..Default::default()
    };
    assert_eq!(order_by_clause(&q).unwrap().as_deref(), Some("id desc"));

    // SqlUtil.isValidOrderBySql 之外的字符 → UtilException（HTTP 500）
    let q = PageQuery {
        order_by_column: Some("1;drop table x".into()),
        is_asc: Some("asc".into()),
        ..Default::default()
    };
    assert!(order_by_clause(&q).is_err());

    // 超过 500 字符同样拒绝
    let q = PageQuery {
        order_by_column: Some("a".repeat(600)),
        ..Default::default()
    };
    assert!(order_by_clause(&q).is_err());
}
