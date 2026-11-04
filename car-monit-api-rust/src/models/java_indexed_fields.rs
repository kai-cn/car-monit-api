// 由本轮双端校验补录：哪些实体的 `params` 是标量属性（因此 `params[x]=v` 必须 500）。
// 对应 Java 侧 AbstractNestablePropertyAccessor#processKeyedProperty 抛出的
// InvalidPropertyException，Spring 未做 @ControllerAdvice，最终是 /error 的 500 JSON。
use super::JavaIndexedFields;
use crate::models::{
    CarParaVO, CarVO, DwdLcztFwqjcxx, DwdLcztSfsjcxx, DwdLcztSfzjcxx, KafkaMessageRecord, OdsCxztFwqclls, OdsLwzxsfsjFeeGantryFusion01, OdsLwzxsfsjFeeRecords01, OdsLwzxsfsjFeeStationEnter01, OdsLwzxsfsjFeeStationExit01, OdsRtSzdnSnapshotFlowAddcode, OdsRtSzdnSnapshotFlowProvcaptureAddcode, OdsRtSzdnSnapshotFlowStationcaptureAddcode, OdsSzdnGantry, OdsSzdnGantryIp, OdsSzdnProvinceBorderVehicleWeightNewstructure, OdsSzdnSection, OdsSzdnToll, OdsSzdnTollStationIp, OdsYhglVBaseOrg, PulsarMessageRecord, SuspiciousCarVO, SysUtil, TrailBo, TrailInfo, TrailTracksVo, ZdataLocationDict, ZdataTrailFitting, ZdataTrailTracks
};

impl JavaIndexedFields for OdsLwzxsfsjFeeGantryFusion01 {
    const JAVA_INDEXED_FIELDS: &[&str] = &["params"];
}

impl JavaIndexedFields for OdsLwzxsfsjFeeRecords01 {
    const JAVA_INDEXED_FIELDS: &[&str] = &["params"];
}

impl JavaIndexedFields for OdsLwzxsfsjFeeStationEnter01 {
    const JAVA_INDEXED_FIELDS: &[&str] = &["params"];
}

impl JavaIndexedFields for OdsLwzxsfsjFeeStationExit01 {
    const JAVA_INDEXED_FIELDS: &[&str] = &["params"];
}

impl JavaIndexedFields for CarParaVO {}

impl JavaIndexedFields for CarVO {}

impl JavaIndexedFields for DwdLcztFwqjcxx {}

impl JavaIndexedFields for DwdLcztSfsjcxx {}

impl JavaIndexedFields for DwdLcztSfzjcxx {}

impl JavaIndexedFields for KafkaMessageRecord {}

impl JavaIndexedFields for OdsCxztFwqclls {}

impl JavaIndexedFields for OdsRtSzdnSnapshotFlowAddcode {}

impl JavaIndexedFields for OdsRtSzdnSnapshotFlowProvcaptureAddcode {}

impl JavaIndexedFields for OdsRtSzdnSnapshotFlowStationcaptureAddcode {}

impl JavaIndexedFields for OdsSzdnGantry {}

impl JavaIndexedFields for OdsSzdnGantryIp {}

impl JavaIndexedFields for OdsSzdnProvinceBorderVehicleWeightNewstructure {}

impl JavaIndexedFields for OdsSzdnSection {}

impl JavaIndexedFields for OdsSzdnToll {}

impl JavaIndexedFields for OdsSzdnTollStationIp {}

impl JavaIndexedFields for OdsYhglVBaseOrg {}

impl JavaIndexedFields for PulsarMessageRecord {}

impl JavaIndexedFields for SuspiciousCarVO {}

impl JavaIndexedFields for SysUtil {}

impl JavaIndexedFields for TrailBo {}

impl JavaIndexedFields for TrailInfo {}

impl JavaIndexedFields for TrailTracksVo {}

impl JavaIndexedFields for ZdataLocationDict {}

impl JavaIndexedFields for ZdataTrailFitting {}

impl JavaIndexedFields for ZdataTrailTracks {}
