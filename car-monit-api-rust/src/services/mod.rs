// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/**（interface + impl）
// 职责: 业务层。对应 Java 的 IService / ServiceImpl 分层。
//
// DIFF: Java 的 interface + impl 双文件在 Rust 中通常不需要；只有存在多实现（ES/DB 双路由）
// 时才抽 trait。本模块用具体 struct + 显式构造替代 @Service / @Autowired。
pub mod consistency;
pub mod consumer;
pub mod delay_monitor;
pub mod dict;
pub mod export;
pub mod large;
pub mod loss_detection;
pub mod multisource;
pub mod producer;
pub mod progressive;
pub mod query;
pub mod reliability;
pub mod sync;
pub mod sysutil;
pub mod track_sync;
pub mod trail;

/// 数据类型常量，对应 MultiSourceDataFlowService / SysUtilServiceImpl 里的 stateType。
pub const DATA_TYPE_GANTRY_CAPTURE: &str = "GantryCapture";
pub const DATA_TYPE_BORDER_WEIGHING: &str = "BorderWeighingCapture";
pub const DATA_TYPE_PROV_CAPTURE: &str = "ProvCapture";
pub const DATA_TYPE_SERVICE_AREA_CAPTURE: &str = "ServiceAreaCapture";
pub const DATA_TYPE_STATION_CAPTURE: &str = "StationCapture";
pub const DATA_TYPE_FEE_RECORD: &str = "FeeRecord";
pub const DATA_TYPE_FEE_STATION_ENTER: &str = "FeeStationEnter";
pub const DATA_TYPE_FEE_STATION_EXIT: &str = "FeeStationExit";

/// 抓拍对象缓存 key 前缀（Constants.java:361-369）。
pub const DATE_BORDER_WEIGHING_PREFIX: &str = "DATE_BorderWeighingCapture:";
pub const DATE_GANTRY_PREFIX: &str = "DATE_GantryCapture:";
pub const DATE_PROV_PREFIX: &str = "DATE_ProvCapture:";
pub const DATE_SERVICE_AREA_PREFIX: &str = "DATE_ServiceAreaCapture:";
pub const DATE_STATION_PREFIX: &str = "DATE_StationCapture:";
pub const DATE_FEE_RECORD_PREFIX: &str = "DATE_FeeRecord:";
pub const DATE_FEE_STATION_ENTER_PREFIX: &str = "DATE_FeeStationEnter:";
pub const DATE_FEE_STATION_EXIT_PREFIX: &str = "DATE_FeeStationExit:";

/// 字典缓存 key（Constants.java）。
pub const DICT_KEY_LOCATION: &str = "dev_post";
pub const DICT_KEY_GANTRY_IP: &str = "gantry_ip";
pub const DICT_KEY_STATION_IP: &str = "station_ip";
pub const DICT_KEY_SECTION: &str = "section_road_map";
pub const DICT_KEY_STATION_INFO: &str = "station_info";
pub const DICT_KEY_GANTRY_LIST: &str = "gantry_list";

/// 轨迹 / 车辆缓存 key。
pub const CAR_LIST_JC: &str = "car_list_jc";
pub const CAR_CURRENT_TRAIL_PREFIX: &str = "car_curent_trail:";
pub const CAR_HISTORY_TRAIL_PREFIX: &str = "car_history_trail:";
pub const CAR_SYNC_TIME_PREFIX: &str = "car_sync_time:";

/// 幂等 key，与 Java 完全一致（切换期可共用 Redis）。
pub const IDEMPOTENT_KEY_PREFIX: &str = "pulsar:msg:processed:";
