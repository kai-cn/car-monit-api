// 由 tools/gen_date_fields.py 自动生成，勿手改。
// 每个实体的 JAVA_DATE_FIELDS = Java 侧声明为 java.util.Date 的查询参数名，
// 这些参数在 Java 里走 DateUtils.parseDate 白名单，解析失败会被静默忽略。
use super::JavaDateFields;
use crate::models::{
    CarParaVO, CarVO, DwdLcztFwqjcxx, DwdLcztSfsjcxx, DwdLcztSfzjcxx, KafkaMessageRecord,
    OdsCxztFwqclls, OdsLwzxsfsjFeeGantryFusion01, OdsLwzxsfsjFeeRecords01,
    OdsLwzxsfsjFeeStationEnter01, OdsLwzxsfsjFeeStationExit01, OdsRtSzdnSnapshotFlowAddcode,
    OdsRtSzdnSnapshotFlowProvcaptureAddcode, OdsRtSzdnSnapshotFlowStationcaptureAddcode,
    OdsSzdnGantry, OdsSzdnGantryIp, OdsSzdnProvinceBorderVehicleWeightNewstructure, OdsSzdnSection,
    OdsSzdnToll, OdsSzdnTollStationIp, OdsYhglVBaseOrg, PulsarMessageRecord, SuspiciousCarVO,
    SysUtil, TrailBo, TrailInfo, TrailTracksVo, ZdataLocationDict, ZdataTrailFitting,
    ZdataTrailTracks,
};

impl JavaDateFields for CarParaVO {
    const JAVA_DATE_FIELDS: &[&str] = &["lastExitTime"];
}

impl JavaDateFields for CarVO {}

impl JavaDateFields for DwdLcztFwqjcxx {}

impl JavaDateFields for DwdLcztSfsjcxx {}

impl JavaDateFields for DwdLcztSfzjcxx {}

impl JavaDateFields for KafkaMessageRecord {
    const JAVA_DATE_FIELDS: &[&str] = &["createTime", "sendTime"];
}

impl JavaDateFields for OdsCxztFwqclls {
    const JAVA_DATE_FIELDS: &[&str] = &["crosstime"];
}

impl JavaDateFields for OdsLwzxsfsjFeeGantryFusion01 {
    const JAVA_DATE_FIELDS: &[&str] =
        &["createtime", "entime", "extime", "receivetime", "loadTime"];
}

impl JavaDateFields for OdsLwzxsfsjFeeRecords01 {
    const JAVA_DATE_FIELDS: &[&str] = &[
        "entime",
        "lastgantrytime",
        "obulastgantrytime",
        "receivetime",
        "stationdbtime",
        "stationdealtime",
        "stationmatchtime",
        "stationvalidtime",
        "transtime",
        "loadTime",
    ];
}

impl JavaDateFields for OdsLwzxsfsjFeeStationEnter01 {
    const JAVA_DATE_FIELDS: &[&str] = &["entime", "receivetime", "loadTime"];
}

impl JavaDateFields for OdsLwzxsfsjFeeStationExit01 {
    const JAVA_DATE_FIELDS: &[&str] = &["entime", "extime", "receivetime", "loadTime"];
}

impl JavaDateFields for OdsRtSzdnSnapshotFlowAddcode {
    const JAVA_DATE_FIELDS: &[&str] = &["snapshottime", "receivedtime", "loadtime"];
}

impl JavaDateFields for OdsRtSzdnSnapshotFlowProvcaptureAddcode {
    const JAVA_DATE_FIELDS: &[&str] = &[
        "tailcapturetime",
        "sidecapturetime",
        "uploadtime",
        "headcapturetime",
        "loadtime",
    ];
}

impl JavaDateFields for OdsRtSzdnSnapshotFlowStationcaptureAddcode {
    const JAVA_DATE_FIELDS: &[&str] = &["snapshottime", "receivedtime", "loadtime"];
}

impl JavaDateFields for OdsSzdnGantry {}

impl JavaDateFields for OdsSzdnGantryIp {}

impl JavaDateFields for OdsSzdnProvinceBorderVehicleWeightNewstructure {
    const JAVA_DATE_FIELDS: &[&str] = &["checkTime", "loadTime"];
}

impl JavaDateFields for OdsSzdnSection {
    const JAVA_DATE_FIELDS: &[&str] = &["openDate"];
}

impl JavaDateFields for OdsSzdnToll {
    const JAVA_DATE_FIELDS: &[&str] = &["openDate"];
}

impl JavaDateFields for OdsSzdnTollStationIp {}

impl JavaDateFields for OdsYhglVBaseOrg {
    const JAVA_DATE_FIELDS: &[&str] = &["loadTime"];
}

impl JavaDateFields for PulsarMessageRecord {
    const JAVA_DATE_FIELDS: &[&str] = &["createTime", "sendTime"];
}

impl JavaDateFields for SuspiciousCarVO {}

impl JavaDateFields for SysUtil {}

impl JavaDateFields for TrailBo {}

impl JavaDateFields for TrailInfo {
    const JAVA_DATE_FIELDS: &[&str] = &["enterTime"];
}

impl JavaDateFields for TrailTracksVo {
    const JAVA_DATE_FIELDS: &[&str] = &["enterTime", "exitTime"];
}

impl JavaDateFields for ZdataLocationDict {
    const JAVA_DATE_FIELDS: &[&str] = &["createdAt", "updatedAt"];
}

impl JavaDateFields for ZdataTrailFitting {
    const JAVA_DATE_FIELDS: &[&str] = &["entime", "extime"];
}

impl JavaDateFields for ZdataTrailTracks {
    const JAVA_DATE_FIELDS: &[&str] = &["enterTime", "exitTime"];
}
