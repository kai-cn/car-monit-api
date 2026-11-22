// 职责: 组合根（composition root）的依赖容器。
//
// DIFF: Spring 用 @Autowired 在运行时注入 Bean；Rust 没有 DI 容器，main() 显式构造全部依赖，
// 再以 Arc<AppState> 注入 axum::extract::State。依赖缺失 = 编译失败，而不是启动后 NPE。

use std::sync::Arc;

use crate::cache::Cache;
use crate::config::Config;
use crate::db::Db;
use crate::es::EsClient;
use crate::mq::Bus;
use crate::repo::*;
use crate::services::consistency::ConsistencyService;
use crate::services::delay_monitor::DelayMonitorService;
use crate::services::dict::DictService;
use crate::services::export::ExportService;
use crate::services::large::LargeScaleQueryService;
use crate::services::loss_detection::LossDetectionService;
use crate::services::multisource::MultiSourceService;
use crate::services::progressive::ProgressiveService;
use crate::services::query::QueryService;
use crate::services::reliability::ReliabilityService;
use crate::services::sync::SyncService;
use crate::services::sysutil::SysUtilService;
use crate::services::trail::TrailAggregationService;

pub struct AppState {
    pub cfg: Arc<Config>,
    pub db: Db,
    pub cache: Option<Cache>,
    pub es: Option<EsClient>,
    pub bus: Bus,

    pub fwqjcxx: FwqjcxxRepo,
    pub sfsjcxx: SfsjcxxRepo,
    pub sfzjcxx: SfzjcxxRepo,
    pub fwqclls: FwqcllsRepo,
    pub fee_gantry: FeeGantryRepo,
    pub fee_records: FeeRecordsRepo,
    pub fee_station_enter: FeeStationEnterRepo,
    pub fee_station_exit: FeeStationExitRepo,
    pub snapshot_flow: SnapshotFlowRepo,
    pub prov_capture: ProvCaptureRepo,
    pub station_capture: StationCaptureRepo,
    pub gantry: GantryRepo,
    pub gantry_ip: GantryIpRepo,
    pub vehicle_weight: VehicleWeightRepo,
    pub section: SectionRepo,
    pub toll: TollRepo,
    pub toll_station_ip: TollStationIpRepo,
    pub org: OrgRepo,
    pub trail_tracks: TrailTracksRepo,
    pub location_dict: LocationDictRepo,
    pub trail_fitting: TrailFittingRepo,
    pub kafka_record: KafkaMessageRecordRepo,

    pub dict: Option<DictService>,
    pub query: QueryService,
    pub large: LargeScaleQueryService,
    pub export: ExportService,
    pub progressive: ProgressiveService,
    pub sync: Arc<SyncService>,
    pub consistency: ConsistencyService,
    pub reliability: Arc<ReliabilityService>,
    pub loss_detection: Arc<LossDetectionService>,
    pub delay_monitor: Arc<DelayMonitorService>,
    pub multisource: MultiSourceService,
    pub trail: TrailAggregationService,
    pub sysutil: Arc<SysUtilService>,
    pub consumer_state: crate::mq::ConsumerState,
}

impl AppState {
    pub fn db(&self) -> &Db {
        &self.db
    }
}
