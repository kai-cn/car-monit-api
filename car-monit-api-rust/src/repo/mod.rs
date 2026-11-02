// 来源: pro-business-api/src/main/java/com/ruoyi/base/mapper/*.java
//       pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/*.xml
// 职责: 数据访问层。逐表复刻 Mapper XML 的 WHERE 条件与查询语义。
// 对应关系:
//   BaseMapper<T>.selectList(q)       ↔ Repo::<T>::list / 各 XxxRepo::list
//   BaseMapper<T>.selectById(id)      ↔ Repo::<T>::get_by_id
//   PageHelper.startPage + count      ↔ LIMIT/OFFSET + COUNT(*)
//   @Select(selectByCursorShard ...)  ↔ list_by_cursor_shard
//   getMaxSnapshotTime()              ↔ max_snapshot_time
//
// DIFF: MyBatis 的 `<if test="x != null and x != ''">` 在 Rust 里被显式翻译成
// `Vec<Cond>`；QueryBuilder 用 $n 占位符绑定，避免 SQL 注入。
// PARITY: Java 缺少 XML 的语句（如 ods_lwzxsfsj_fee_records_01 的 selectList）在 Java 侧
// 实际会抛 Invalid bound statement；本实现沿用 Go 版按字段语义重建的行为，并在 README 标注。

use std::marker::PhantomData;

use chrono::{DateTime, Utc};
use sqlx::postgres::PgRow;
use sqlx::{FromRow, Postgres, QueryBuilder, Row};

use crate::db::Db;
use crate::error::{AppError, AppResult};
use crate::models::*;

mod filters_gen;
pub use filters_gen::*;

/// WHERE 条件的最小表达（对应 MyBatis 的 <if> 分支）。
#[derive(Debug, Clone)]
pub enum Cond {
    Eq(&'static str, JString),
    EqI64(&'static str, i64),
    EqF64(&'static str, f64),
    Like(&'static str, JString),
    In(&'static str, Vec<String>),
    Gte(&'static str, JString),
    Lte(&'static str, JString),
}

pub fn push_where(qb: &mut QueryBuilder<'_, Postgres>, conds: &[Cond]) {
    if conds.is_empty() {
        return;
    }
    qb.push(" WHERE ");
    for (i, c) in conds.iter().enumerate() {
        if i > 0 {
            qb.push(" AND ");
        }
        match c {
            Cond::Eq(col, v) => {
                qb.push(*col).push(" = ").push_bind(v.clone());
            }
            Cond::EqI64(col, v) => {
                qb.push(*col).push(" = ").push_bind(*v);
            }
            Cond::EqF64(col, v) => {
                qb.push(*col).push(" = ").push_bind(*v);
            }
            Cond::Like(col, v) => {
                // PARITY: MyBatis `like concat('%', x, '%')` 大小写敏感。
                qb.push(*col).push(" LIKE ").push_bind(format!("%{}%", v));
            }
            Cond::In(col, vs) => {
                qb.push(*col).push(" IN (");
                let mut sep = qb.separated(", ");
                for v in vs {
                    sep.push_bind(v.clone());
                }
                qb.push(")");
            }
            Cond::Gte(col, v) => {
                // PARITY: XML 写成 `col >= to_timestamp(#{f},'yyyy-mm-dd HH24:MI:SS')`，
                // 直接绑定文本会让数据库报类型错误，必须走同一个 to_timestamp 转换。
                qb.push(*col)
                    .push(" >= to_timestamp(")
                    .push_bind(v.clone())
                    .push(", 'yyyy-mm-dd HH24:MI:SS')");
            }
            Cond::Lte(col, v) => {
                qb.push(*col)
                    .push(" <= to_timestamp(")
                    .push_bind(v.clone())
                    .push(", 'yyyy-mm-dd HH24:MI:SS')");
            }
        }
    }
}

/// 通用只读仓库。`select` 可以是 "*"，也可以是带别名的列清单（服务区 Mapper）。
#[derive(Clone)]
pub struct Repo<T> {
    db: Db,
    table: &'static str,
    select: &'static str,
    pk: &'static str,
    order: &'static str,
    _m: PhantomData<T>,
}

impl<T> Repo<T>
where
    T: for<'r> FromRow<'r, PgRow> + Send + Unpin,
{
    pub fn new(
        db: Db,
        table: &'static str,
        select: &'static str,
        pk: &'static str,
        order: &'static str,
    ) -> Self {
        Self {
            db,
            table,
            select,
            pk,
            order,
            _m: PhantomData,
        }
    }

    pub async fn list(&self, conds: Vec<Cond>, limit: i64, offset: i64) -> AppResult<Vec<T>> {
        let mut qb =
            QueryBuilder::<Postgres>::new(format!("SELECT {} FROM {}", self.select, self.table));
        push_where(&mut qb, &conds);
        if !self.order.is_empty() {
            qb.push(" ").push(self.order);
        }
        // 对应 PageHelper 的 LIMIT/OFFSET（Rust 直接下推，无需内存切片）
        qb.push(" LIMIT ").push_bind(limit.max(1));
        qb.push(" OFFSET ").push_bind(offset.max(0));
        Ok(qb.build_query_as::<T>().fetch_all(&self.db.pool).await?)
    }

    pub async fn list_unbounded(&self, conds: Vec<Cond>) -> AppResult<Vec<T>> {
        let mut qb =
            QueryBuilder::<Postgres>::new(format!("SELECT {} FROM {}", self.select, self.table));
        push_where(&mut qb, &conds);
        if !self.order.is_empty() {
            qb.push(" ").push(self.order);
        }
        Ok(qb.build_query_as::<T>().fetch_all(&self.db.pool).await?)
    }

    pub async fn count(&self, conds: Vec<Cond>) -> AppResult<i64> {
        let mut qb = QueryBuilder::<Postgres>::new(format!("SELECT COUNT(*) FROM {}", self.table));
        push_where(&mut qb, &conds);
        let row = qb.build().fetch_one(&self.db.pool).await?;
        Ok(row.try_get::<i64, _>(0).unwrap_or(0))
    }

    pub async fn get_by_id(&self, id: &str) -> AppResult<Option<T>> {
        let mut qb =
            QueryBuilder::<Postgres>::new(format!("SELECT {} FROM {}", self.select, self.table));
        qb.push(" WHERE ")
            .push(self.pk)
            .push(" = ")
            .push_bind(id.to_string());
        qb.push(" LIMIT 1");
        Ok(qb
            .build_query_as::<T>()
            .fetch_optional(&self.db.pool)
            .await?)
    }

    pub async fn get_by_id_i64(&self, id: i64) -> AppResult<Option<T>> {
        let mut qb =
            QueryBuilder::<Postgres>::new(format!("SELECT {} FROM {}", self.select, self.table));
        qb.push(" WHERE ").push(self.pk).push(" = ").push_bind(id);
        qb.push(" LIMIT 1");
        Ok(qb
            .build_query_as::<T>()
            .fetch_optional(&self.db.pool)
            .await?)
    }

    pub async fn list_all(&self) -> AppResult<Vec<T>> {
        let mut qb =
            QueryBuilder::<Postgres>::new(format!("SELECT {} FROM {}", self.select, self.table));
        if !self.order.is_empty() {
            qb.push(" ").push(self.order);
        }
        Ok(qb.build_query_as::<T>().fetch_all(&self.db.pool).await?)
    }

    pub async fn list_in(
        &self,
        col: &'static str,
        values: &[String],
        limit: i64,
    ) -> AppResult<Vec<T>> {
        self.list(vec![Cond::In(col, values.to_vec())], limit, 0)
            .await
    }

    pub async fn list_eq(&self, col: &'static str, value: &str, limit: i64) -> AppResult<Vec<T>> {
        self.list(vec![Cond::Eq(col, value.into())], limit, 0).await
    }

    pub fn db(&self) -> &Db {
        &self.db
    }
}

/// 只读仓库契约：让 handler 可以泛型处理 19 张基础表（对应 MyBatis-Plus BaseMapper<T> 的默认方法）。
#[async_trait::async_trait]
pub trait ReadRepo<T>: Send + Sync {
    async fn list(&self, q: &T, limit: i64, offset: i64) -> AppResult<Vec<T>>;
    async fn count(&self, q: &T) -> AppResult<i64>;
    async fn get_by_id(&self, id: &str) -> AppResult<Option<T>>;
    async fn list_all(&self) -> AppResult<Vec<T>>;
}

/// 生成某张表的仓库包装：list/count/get_by_id/list_all 全部走同一套 SQL 语义。
macro_rules! entity_repo {
    ($repo:ident, $model:ty, $table:expr, $pk:expr, $select:expr, $order:expr, $filters:path) => {
        #[derive(Clone)]
        pub struct $repo {
            pub repo: Repo<$model>,
        }

        impl $repo {
            pub fn new(db: Db) -> Self {
                Self {
                    repo: Repo::new(db, $table, $select, $pk, $order),
                }
            }

            pub async fn list(
                &self,
                q: &$model,
                limit: i64,
                offset: i64,
            ) -> AppResult<Vec<$model>> {
                self.repo.list($filters(q), limit, offset).await
            }

            pub async fn count(&self, q: &$model) -> AppResult<i64> {
                self.repo.count($filters(q)).await
            }

            pub async fn get_by_id(&self, id: &str) -> AppResult<Option<$model>> {
                self.repo.get_by_id(id).await
            }

            pub async fn list_all(&self) -> AppResult<Vec<$model>> {
                self.repo.list_all().await
            }
        }

        #[async_trait::async_trait]
        impl ReadRepo<$model> for $repo {
            async fn list(&self, q: &$model, limit: i64, offset: i64) -> AppResult<Vec<$model>> {
                $repo::list(self, q, limit, offset).await
            }
            async fn count(&self, q: &$model) -> AppResult<i64> {
                $repo::count(self, q).await
            }
            async fn get_by_id(&self, id: &str) -> AppResult<Option<$model>> {
                $repo::get_by_id(self, id).await
            }
            async fn list_all(&self) -> AppResult<Vec<$model>> {
                $repo::list_all(self).await
            }
        }
    };
}

/// 主键是 bigint 的两张表（gantry_ip / toll_station_ip）：非法 id → 400（Spring @PathVariable Long 语义）。
macro_rules! entity_repo_numeric {
    ($repo:ident, $model:ty, $table:expr, $pk:expr, $select:expr, $order:expr, $filters:path) => {
        #[derive(Clone)]
        pub struct $repo {
            pub repo: Repo<$model>,
        }

        impl $repo {
            pub fn new(db: Db) -> Self {
                Self {
                    repo: Repo::new(db, $table, $select, $pk, $order),
                }
            }

            pub async fn list(
                &self,
                q: &$model,
                limit: i64,
                offset: i64,
            ) -> AppResult<Vec<$model>> {
                self.repo.list($filters(q), limit, offset).await
            }

            pub async fn count(&self, q: &$model) -> AppResult<i64> {
                self.repo.count($filters(q)).await
            }

            pub async fn get_by_id(&self, id: &str) -> AppResult<Option<$model>> {
                let n = parse_numeric_id(id)?;
                self.repo.get_by_id_i64(n).await
            }

            pub async fn list_all(&self) -> AppResult<Vec<$model>> {
                self.repo.list_all().await
            }
        }

        #[async_trait::async_trait]
        impl ReadRepo<$model> for $repo {
            async fn list(&self, q: &$model, limit: i64, offset: i64) -> AppResult<Vec<$model>> {
                $repo::list(self, q, limit, offset).await
            }
            async fn count(&self, q: &$model) -> AppResult<i64> {
                $repo::count(self, q).await
            }
            async fn get_by_id(&self, id: &str) -> AppResult<Option<$model>> {
                $repo::get_by_id(self, id).await
            }
            async fn list_all(&self) -> AppResult<Vec<$model>> {
                $repo::list_all(self).await
            }
        }
    };
}

// ============================================================
// 19 张基础表
// ============================================================

// 服务区：Java DwdLcztFwqjcxxMapper.xml 实际查 jl_data01.ods_szdn_service，
// 并把 id_card/service_code/... 逐列 AS 成 agent_pk/yxtzj/...。
const FWQ_SELECT: &str =
    "id AS agent_pk, id_card AS yxtzj, service_code AS fwqbm, service_name AS fwqmc, \
direction AS fxdm, longitude AS jd, latitude AS wd, road_code AS sslxbh, section_code AS ssldbh, \
section_name AS ssldmc, pile_no AS sczhkgs, org_code AS ssglzxbm, org_name AS ssglzxmc, \
city_code AS xzqhmc, district_name AS xzqhdm, business_date AS yyrq, parking_num AS cws, \
has_cross AS sfszlkk, charge_num AS cdzs, food_service AS sfcyfw, stay_service AS sftgzsfw, \
automobile_service AS sftgqxfw, supermarket_service AS sftgcsfw, gas_service AS sftgjyfw, \
service_alias_name AS lyxt";

entity_repo!(
    FwqjcxxRepo,
    DwdLcztFwqjcxx,
    "jl_data01.ods_szdn_service",
    "id",
    FWQ_SELECT,
    "",
    fwq_filters
);
entity_repo!(
    SfsjcxxRepo,
    DwdLcztSfsjcxx,
    "jl_data01.dwd_lczt_sfsjcxx",
    "agent_pk",
    "*",
    "",
    sfsj_filters
);
entity_repo!(
    SfzjcxxRepo,
    DwdLcztSfzjcxx,
    "jl_data01.dwd_lczt_sfzjcxx",
    "agent_pk",
    "*",
    "",
    sfzj_filters
);
entity_repo_numeric!(
    FwqcllsRepo,
    OdsCxztFwqclls,
    "jl_data01.ods_cxzt_fwqclls",
    "big_id",
    "*",
    "",
    fwqclls_filters
);
entity_repo!(
    FeeGantryRepo,
    OdsLwzxsfsjFeeGantryFusion01,
    "jl_data01.ods_lwzxsfsj_fee_gantry_fusion_01",
    "big_id",
    "*",
    "",
    fee_gantry_filters
);
entity_repo!(
    FeeRecordsRepo,
    OdsLwzxsfsjFeeRecords01,
    "jl_data01.ods_lwzxsfsj_fee_records_01",
    "big_id",
    "*",
    "",
    fee_records_filters
);
entity_repo_numeric!(
    FeeStationEnterRepo,
    OdsLwzxsfsjFeeStationEnter01,
    "jl_data01.ods_lwzxsfsj_fee_station_enter_01",
    "big_id",
    "*",
    "",
    fee_enter_filters
);
entity_repo!(
    FeeStationExitRepo,
    OdsLwzxsfsjFeeStationExit01,
    "jl_data01.ods_lwzxsfsj_fee_station_exit_01",
    "big_id",
    "*",
    "",
    fee_exit_filters
);
const SNAPSHOT_SELECT: &str = "datauuid, gantryname, roadname, sectionname, direction, snapshottimeunix, snapshottime, platenumber, platecolor, platecolorcode, platetype, platetypecode, carcolor, carcolorcode, cartype, cartypecode, snappicturepath";

entity_repo!(
    SnapshotFlowRepo,
    OdsRtSzdnSnapshotFlowAddcode,
    "jl_data01.ods_rt_szdn_snapshot_flow_addcode",
    "big_id",
    SNAPSHOT_SELECT,
    "ORDER BY snapshottime DESC",
    snapshot_filters
);
entity_repo_numeric!(
    ProvCaptureRepo,
    OdsRtSzdnSnapshotFlowProvcaptureAddcode,
    "jl_data01.ods_rt_szdn_snapshot_flow_provcapture_addcode",
    "big_id",
    "*",
    "",
    prov_capture_filters
);
entity_repo_numeric!(
    StationCaptureRepo,
    OdsRtSzdnSnapshotFlowStationcaptureAddcode,
    "jl_data01.ods_rt_szdn_snapshot_flow_stationcapture_addcode",
    "big_id",
    "*",
    "",
    station_capture_filters
);
entity_repo!(
    GantryRepo,
    OdsSzdnGantry,
    "jl_data01.ods_szdn_gantry",
    "id",
    "*",
    "",
    gantry_filters
);
entity_repo_numeric!(
    GantryIpRepo,
    OdsSzdnGantryIp,
    "jl_data01.ods_szdn_gantry_ip",
    "id",
    "*",
    "",
    gantry_ip_filters
);
entity_repo!(
    VehicleWeightRepo,
    OdsSzdnProvinceBorderVehicleWeightNewstructure,
    "jl_data01.ods_szdn_province_border_vehicle_weight_newstructure",
    "datauuid",
    "*",
    "",
    vehicle_weight_filters
);
entity_repo!(
    SectionRepo,
    OdsSzdnSection,
    "jl_data01.ods_szdn_section",
    "id",
    "*",
    "",
    section_filters
);
entity_repo!(
    TollRepo,
    OdsSzdnToll,
    "jl_data01.ods_szdn_toll",
    "id",
    "*",
    "",
    toll_filters
);
entity_repo_numeric!(
    TollStationIpRepo,
    OdsSzdnTollStationIp,
    "jl_data01.ods_szdn_toll_station_ip",
    "id",
    "*",
    "",
    toll_station_ip_filters
);
entity_repo!(
    OrgRepo,
    OdsYhglVBaseOrg,
    "jl_data01.ods_yhgl_v_base_org",
    "big_id",
    "*",
    "",
    org_filters
);
entity_repo!(
    TrailTracksRepo,
    ZdataTrailTracks,
    "jl_data01.zdata_trail_tracks",
    "uuid",
    "*",
    "",
    trail_tracks_filters
);
entity_repo!(
    LocationDictRepo,
    ZdataLocationDict,
    "jl_data01.zdata_location_dict",
    "big_id",
    "*",
    "",
    location_dict_filters
);
entity_repo!(
    TrailFittingRepo,
    ZdataTrailFitting,
    "jl_data01.zdata_trail_fitting",
    "big_id",
    "*",
    "",
    trail_fitting_filters
);
entity_repo!(
    KafkaMessageRecordRepo,
    KafkaMessageRecord,
    "jl_data01.kafka_message_record",
    "id",
    "*",
    "ORDER BY create_time ASC",
    kafka_record_filters
);

// ============================================================
// 各表 <if> 条件（逐条对应 Mapper XML / Go 侧已核对实现）
// ============================================================

pub fn fee_records_filters(q: &OdsLwzxsfsjFeeRecords01) -> Vec<Cond> {
    let mut v = vec![];
    if !q.vehicleplate.is_empty() {
        v.push(Cond::Like("vehicleplate", q.vehicleplate.clone().into()));
    }
    if !q.big_id.is_empty() {
        v.push(Cond::Eq("big_id", q.big_id.clone().into()));
    }
    if !q.antennaid.is_empty() {
        v.push(Cond::Eq("antennaid", q.antennaid.clone().into()));
    }
    if !q.cpucardid.is_empty() {
        v.push(Cond::Eq("cpucardid", q.cpucardid.clone().into()));
    }
    if !q.cpuissueid.is_empty() {
        v.push(Cond::Eq("cpuissueid", q.cpuissueid.clone().into()));
    }
    if !q.cpunetid.is_empty() {
        v.push(Cond::Eq("cpunetid", q.cpunetid.clone().into()));
    }
    if !q.entolllaneid.is_empty() {
        v.push(Cond::Eq("entolllaneid", q.entolllaneid.clone().into()));
    }
    if !q.gantryid.is_empty() {
        v.push(Cond::Eq("gantryid", q.gantryid.clone().into()));
    }
    if !q.obuissueid.is_empty() {
        v.push(Cond::Eq("obuissueid", q.obuissueid.clone().into()));
    }
    if !q.passid.is_empty() {
        v.push(Cond::Eq("passid", q.passid.clone().into()));
    }
    if !q.tollintervalid.is_empty() {
        v.push(Cond::Eq("tollintervalid", q.tollintervalid.clone().into()));
    }
    if !q.tradeid.is_empty() {
        v.push(Cond::Eq("tradeid", q.tradeid.clone().into()));
    }
    if !q.verifycode.is_empty() {
        v.push(Cond::Eq("verifycode", q.verifycode.clone().into()));
    }
    if !q.code_list.is_empty() {
        v.push(Cond::In("gantryid", q.code_list.to_vec()));
    }
    v
}

pub fn trail_fitting_filters(q: &ZdataTrailFitting) -> Vec<Cond> {
    let mut v = vec![];
    if !q.cid.is_empty() {
        v.push(Cond::Eq("cid", q.cid.clone().into()));
    }
    if !q.entolllaneid.is_empty() {
        v.push(Cond::Eq("entolllaneid", q.entolllaneid.clone().into()));
    }
    if !q.entollstationid.is_empty() {
        v.push(Cond::Eq(
            "entollstationid",
            q.entollstationid.clone().into(),
        ));
    }
    if !q.envehicleid.is_empty() {
        v.push(Cond::Eq("envehicleid", q.envehicleid.clone().into()));
    }
    if !q.extolllaneid.is_empty() {
        v.push(Cond::Eq("extolllaneid", q.extolllaneid.clone().into()));
    }
    if !q.extollstationid.is_empty() {
        v.push(Cond::Eq(
            "extollstationid",
            q.extollstationid.clone().into(),
        ));
    }
    if !q.exvehicleid.is_empty() {
        v.push(Cond::Eq("exvehicleid", q.exvehicleid.clone().into()));
    }
    v
}

fn kafka_record_filters(q: &KafkaMessageRecord) -> Vec<Cond> {
    let mut v = vec![];
    if !q.id.is_empty() {
        v.push(Cond::Eq("id", q.id.clone().into()));
    }
    if !q.data_id.is_empty() {
        v.push(Cond::Eq("data_id", q.data_id.clone().into()));
    }
    v
}

// ============================================================
// 手写 SQL：游标同步 / 对账计数 / 轨迹查询 / 回源查询 / 消息状态机
// ============================================================

impl SnapshotFlowRepo {
    /// XML: `[start, end)` 半开区间 + (time, uuid) 复合游标。
    pub async fn list_by_cursor_shard(
        &self,
        start_time: &str,
        end_time: &str,
        cursor_time: &str,
        cursor_uuid: &str,
        limit: i64,
    ) -> AppResult<Vec<OdsRtSzdnSnapshotFlowAddcode>> {
        let mut sql =
            String::from("SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode WHERE 1=1");
        let mut args: Vec<String> = vec![];
        if !start_time.is_empty() {
            sql.push_str(" AND snapshottime >= ?");
            args.push(start_time.into());
        }
        if !end_time.is_empty() {
            sql.push_str(" AND snapshottime < ?");
            args.push(end_time.into());
        }
        if !cursor_time.is_empty() {
            if !cursor_uuid.is_empty() {
                sql.push_str(" AND (snapshottime, datauuid) > (?, ?)");
                args.push(cursor_time.into());
                args.push(cursor_uuid.into());
            } else {
                sql.push_str(" AND snapshottime > ?");
                args.push(cursor_time.into());
            }
        }
        sql.push_str(" ORDER BY snapshottime ASC, datauuid ASC LIMIT ?");
        let sql = pg_placeholders(&sql, args.len() + 1);
        let mut q = sqlx::query_as::<_, OdsRtSzdnSnapshotFlowAddcode>(&sql);
        for a in args {
            q = q.bind(a);
        }
        q = q.bind(limit.max(1));
        Ok(q.fetch_all(&self.repo.db().pool).await?)
    }

    pub async fn max_snapshot_time(&self) -> AppResult<DateTime<Utc>> {
        let row = sqlx::query(
            "SELECT COALESCE(MAX(snapshottime), now()) AS t FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode",
        )
        .fetch_one(&self.repo.db().pool)
        .await?;
        Ok(row
            .try_get::<Option<DateTime<Utc>>, _>("t")?
            .unwrap_or_else(Utc::now))
    }

    pub async fn count_between(&self, start: &str, end: &str) -> AppResult<i64> {
        let n: Option<i64> = sqlx::query_scalar(
            "SELECT COUNT(*) FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode WHERE snapshottime BETWEEN $1 AND $2",
        )
        .bind(start)
        .bind(end)
        .fetch_one(&self.repo.db().pool)
        .await?;
        Ok(n.unwrap_or(0))
    }

    /// 对应 DataLossDetectionService 的 ListBigIDsBetween：只取主键，避免拉整行。
    pub async fn list_big_ids_between(&self, start: &str, end: &str) -> AppResult<Vec<String>> {
        let rows = sqlx::query(
            "SELECT big_id FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode \
WHERE snapshottime BETWEEN $1 AND $2",
        )
        .bind(start)
        .bind(end)
        .fetch_all(&self.repo.db().pool)
        .await?;
        Ok(rows
            .iter()
            .map(|r| r.try_get::<String, _>(0).unwrap_or_default())
            .collect())
    }

    pub async fn list_by_datauuid(
        &self,
        uuid: &str,
        from: i64,
        to: i64,
    ) -> AppResult<Vec<OdsRtSzdnSnapshotFlowAddcode>> {
        let mut sql = String::from(
            "SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode WHERE datauuid = $1",
        );
        if from > 0 {
            sql.push_str(" AND snapshottime >= $2");
        }
        if to > 0 {
            sql.push_str(if from > 0 {
                " AND snapshottime <= $3"
            } else {
                " AND snapshottime <= $2"
            });
        }
        sql.push_str(" LIMIT 1");
        let mut q = sqlx::query_as::<_, OdsRtSzdnSnapshotFlowAddcode>(&sql).bind(uuid);
        if from > 0 {
            q = q.bind(DateTime::<Utc>::from_timestamp_millis(from).unwrap_or_else(Utc::now));
        }
        if to > 0 {
            q = q.bind(DateTime::<Utc>::from_timestamp_millis(to).unwrap_or_else(Utc::now));
        }
        Ok(q.fetch_all(&self.repo.db().pool).await?)
    }

    /// 对应 snapshotFlowService.saveOrUpdate：先查主键，再 insert/update。
    pub async fn insert(&self, m: &OdsRtSzdnSnapshotFlowAddcode) -> AppResult<()> {
        sqlx::query(
            "INSERT INTO jl_data01.ods_rt_szdn_snapshot_flow_addcode \
(big_id,datasource,cameratype,deviceid,gantrycode,gantryname,roadcode,roadname,sectioncode,sectionname,\
tollcode,tollname,orgcode,orgname,direction,hexcode,pileno,lon,lat,deviceip,siteid,laneid,\
snapshottimeunix,snapshottime,receivedtimeunix,receivedtime,platenumber,platecolor,platecolorcode,\
platetype,platetypecode,plateconfidence,carbrand,carcolor,carcolorcode,cartype,cartypecode,cardirection,\
snappicturepath,loadtime,gradelevel,datauuid,reserve3) \
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,\
$27,$28,$29,$30,$31,$32,$33,$34,$35,$36,$37,$38,$39,$40,$41,$42,$43)",
        )
        .bind(&m.big_id).bind(&m.datasource).bind(&m.cameratype).bind(&m.deviceid)
        .bind(&m.gantrycode).bind(&m.gantryname).bind(&m.roadcode).bind(&m.roadname)
        .bind(&m.sectioncode).bind(&m.sectionname).bind(&m.tollcode).bind(&m.tollname)
        .bind(&m.orgcode).bind(&m.orgname).bind(m.direction).bind(&m.hexcode)
        .bind(&m.pileno).bind(m.lon).bind(m.lat).bind(&m.deviceip)
        .bind(m.siteid).bind(m.laneid).bind(m.snapshottimeunix).bind(m.snapshottime)
        .bind(m.receivedtimeunix).bind(m.receivedtime).bind(&m.platenumber).bind(&m.platecolor)
        .bind(m.platecolorcode).bind(&m.platetype).bind(m.platetypecode).bind(m.plateconfidence)
        .bind(&m.carbrand).bind(&m.carcolor).bind(m.carcolorcode).bind(&m.cartype)
        .bind(m.cartypecode).bind(&m.cardirection).bind(&m.snappicturepath).bind(m.loadtime)
        .bind(m.gradelevel).bind(&m.datauuid).bind(&m.reserve3)
        .execute(&self.repo.db().pool)
        .await?;
        Ok(())
    }

    pub async fn update(&self, m: &OdsRtSzdnSnapshotFlowAddcode) -> AppResult<()> {
        sqlx::query(
            "UPDATE jl_data01.ods_rt_szdn_snapshot_flow_addcode SET \
datasource=$2,cameratype=$3,deviceid=$4,gantrycode=$5,gantryname=$6,roadcode=$7,roadname=$8,\
sectioncode=$9,sectionname=$10,tollcode=$11,tollname=$12,orgcode=$13,orgname=$14,direction=$15,\
hexcode=$16,pileno=$17,lon=$18,lat=$19,deviceip=$20,siteid=$21,laneid=$22,snapshottimeunix=$23,\
snapshottime=$24,receivedtimeunix=$25,receivedtime=$26,platenumber=$27,platecolor=$28,\
platecolorcode=$29,platetype=$30,platetypecode=$31,plateconfidence=$32,carbrand=$33,carcolor=$34,\
carcolorcode=$35,cartype=$36,cartypecode=$37,cardirection=$38,snappicturepath=$39,loadtime=$40,\
gradelevel=$41,datauuid=$42,reserve3=$43 WHERE big_id=$1",
        )
        .bind(&m.big_id)
        .bind(&m.datasource)
        .bind(&m.cameratype)
        .bind(&m.deviceid)
        .bind(&m.gantrycode)
        .bind(&m.gantryname)
        .bind(&m.roadcode)
        .bind(&m.roadname)
        .bind(&m.sectioncode)
        .bind(&m.sectionname)
        .bind(&m.tollcode)
        .bind(&m.tollname)
        .bind(&m.orgcode)
        .bind(&m.orgname)
        .bind(m.direction)
        .bind(&m.hexcode)
        .bind(&m.pileno)
        .bind(m.lon)
        .bind(m.lat)
        .bind(&m.deviceip)
        .bind(m.siteid)
        .bind(m.laneid)
        .bind(m.snapshottimeunix)
        .bind(m.snapshottime)
        .bind(m.receivedtimeunix)
        .bind(m.receivedtime)
        .bind(&m.platenumber)
        .bind(&m.platecolor)
        .bind(m.platecolorcode)
        .bind(&m.platetype)
        .bind(m.platetypecode)
        .bind(m.plateconfidence)
        .bind(&m.carbrand)
        .bind(&m.carcolor)
        .bind(m.carcolorcode)
        .bind(&m.cartype)
        .bind(m.cartypecode)
        .bind(&m.cardirection)
        .bind(&m.snappicturepath)
        .bind(m.loadtime)
        .bind(m.gradelevel)
        .bind(&m.datauuid)
        .bind(&m.reserve3)
        .execute(&self.repo.db().pool)
        .await?;
        Ok(())
    }

    pub async fn delete_by_id(&self, id: &str) -> AppResult<()> {
        sqlx::query("DELETE FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode WHERE big_id = $1")
            .bind(id)
            .execute(&self.repo.db().pool)
            .await?;
        Ok(())
    }
}

impl FeeRecordsRepo {
    pub async fn list_by_cursor_shard(
        &self,
        start: &str,
        end: &str,
        cursor_time: &str,
        cursor_uuid: &str,
        limit: i64,
    ) -> AppResult<Vec<OdsLwzxsfsjFeeRecords01>> {
        cursor_query::<OdsLwzxsfsjFeeRecords01>(
            &self.repo.db().pool,
            "jl_data01.ods_lwzxsfsj_fee_records_01",
            "transtime",
            "big_id",
            start,
            end,
            cursor_time,
            cursor_uuid,
            limit,
        )
        .await
    }

    pub async fn count_between(&self, start: &str, end: &str) -> AppResult<i64> {
        count_between(
            &self.repo.db().pool,
            "jl_data01.ods_lwzxsfsj_fee_records_01",
            "transtime",
            start,
            end,
        )
        .await
    }
}

impl TrailFittingRepo {
    pub async fn list_by_cursor_shard(
        &self,
        start: &str,
        end: &str,
        cursor_time: &str,
        cursor_uuid: &str,
        limit: i64,
    ) -> AppResult<Vec<ZdataTrailFitting>> {
        cursor_query::<ZdataTrailFitting>(
            &self.repo.db().pool,
            "jl_data01.zdata_trail_fitting",
            "extime",
            "cid",
            start,
            end,
            cursor_time,
            cursor_uuid,
            limit,
        )
        .await
    }

    pub async fn count_between(&self, start: &str, end: &str) -> AppResult<i64> {
        count_between(
            &self.repo.db().pool,
            "jl_data01.zdata_trail_fitting",
            "extime",
            start,
            end,
        )
        .await
    }
}

impl VehicleWeightRepo {
    pub async fn list_by_datauuid(
        &self,
        uuid: &str,
    ) -> AppResult<Vec<OdsSzdnProvinceBorderVehicleWeightNewstructure>> {
        self.repo.list_eq("datauuid", uuid, 1).await
    }
}

impl ProvCaptureRepo {
    pub async fn list_by_datauuid(
        &self,
        uuid: &str,
    ) -> AppResult<Vec<OdsRtSzdnSnapshotFlowProvcaptureAddcode>> {
        self.repo.list_eq("datauuid", uuid, 1).await
    }
}

impl FwqcllsRepo {
    pub async fn list_by_datauuid(&self, uuid: &str) -> AppResult<Vec<OdsCxztFwqclls>> {
        self.repo.list_eq("datauuid", uuid, 1).await
    }
}

impl StationCaptureRepo {
    pub async fn list_by_datauuid(
        &self,
        uuid: &str,
        from: i64,
        to: i64,
    ) -> AppResult<Vec<OdsRtSzdnSnapshotFlowStationcaptureAddcode>> {
        let mut conds = vec![Cond::Eq("datauuid", uuid.into())];
        if from > 0 {
            conds.push(Cond::Gte(
                "snapshottime",
                crate::utils::format_datetime(
                    &chrono::DateTime::<Utc>::from_timestamp_millis(from).unwrap_or_else(Utc::now),
                )
                .into(),
            ));
        }
        if to > 0 {
            conds.push(Cond::Lte(
                "snapshottime",
                crate::utils::format_datetime(
                    &chrono::DateTime::<Utc>::from_timestamp_millis(to).unwrap_or_else(Utc::now),
                )
                .into(),
            ));
        }
        self.repo.list(conds, 1, 0).await
    }
}

impl FeeStationEnterRepo {
    pub async fn list_by_cid(&self, cid: &str) -> AppResult<Vec<OdsLwzxsfsjFeeStationEnter01>> {
        self.repo.list_eq("cid", cid, 1).await
    }
}

impl FeeStationExitRepo {
    pub async fn list_by_cid(&self, cid: &str) -> AppResult<Vec<OdsLwzxsfsjFeeStationExit01>> {
        self.repo.list_eq("cid", cid, 1).await
    }
}

impl FeeRecordsRepo {
    pub async fn list_by_cid(
        &self,
        cid: &str,
        from: i64,
        to: i64,
    ) -> AppResult<Vec<OdsLwzxsfsjFeeRecords01>> {
        let mut sql =
            String::from("SELECT * FROM jl_data01.ods_lwzxsfsj_fee_records_01 WHERE cid = $1");
        if from > 0 {
            sql.push_str(" AND transtime >= $2");
        }
        if to > 0 {
            sql.push_str(if from > 0 {
                " AND transtime <= $3"
            } else {
                " AND transtime <= $2"
            });
        }
        sql.push_str(" LIMIT 1");
        let mut q = sqlx::query_as::<_, OdsLwzxsfsjFeeRecords01>(&sql).bind(cid);
        if from > 0 {
            q = q.bind(DateTime::<Utc>::from_timestamp_millis(from).unwrap_or_else(Utc::now));
        }
        if to > 0 {
            q = q.bind(DateTime::<Utc>::from_timestamp_millis(to).unwrap_or_else(Utc::now));
        }
        Ok(q.fetch_all(&self.repo.db().pool).await?)
    }
}

impl TrailTracksRepo {
    /// ZdataTrailTracksMapper.xml:116-158 getHistoryTrail（读 zdata_trail_fitting）。
    pub async fn get_history_trail(
        &self,
        vo: &CarParaVO,
        limit: i64,
    ) -> AppResult<Vec<ZdataTrailTracks>> {
        let mut sql = String::from(
            "SELECT cid AS uuid, envehicleid AS plate_key, entime AS enter_time, extime AS exit_time, \
trailpoints AS trail_points FROM jl_data01.zdata_trail_fitting WHERE 1=1",
        );
        let mut args: Vec<String> = vec![];
        if !vo.car_no_list.is_empty() {
            sql.push_str(&format!(
                " AND envehicleid IN ({})",
                placeholders(vo.car_no_list.len())
            ));
            args.extend(vo.car_no_list.iter().cloned());
        } else if !vo.car_no.is_empty() {
            sql.push_str(" AND envehicleid = ?");
            args.push(vo.car_no.as_str().to_string());
        }
        if !vo.apply_time1.is_empty() {
            sql.push_str(" AND extime >= to_timestamp(?, 'yyyy-mm-dd HH24:MI:SS')");
            args.push(vo.apply_time1.as_str().to_string());
        }
        if !vo.apply_time2.is_empty() {
            sql.push_str(" AND extime <= to_timestamp(?, 'yyyy-mm-dd HH24:MI:SS')");
            args.push(vo.apply_time2.as_str().to_string());
        }
        match vo.flag.as_str() {
            "bannian" => sql.push_str(" AND extime >= now() - 180"),
            "yiyue" => sql.push_str(" AND extime >= now() - 3"),
            _ => {}
        }
        sql.push_str(" ORDER BY cid, extime LIMIT ?");
        let sql = pg_placeholders(&sql, args.len() + 1);
        let mut q = sqlx::query_as::<_, ZdataTrailTracks>(&sql);
        for a in args {
            q = q.bind(a);
        }
        q = q.bind(limit.max(1));
        Ok(q.fetch_all(&self.repo.db().pool).await?)
    }
}

impl KafkaMessageRecordRepo {
    pub const STATUS_PENDING: i32 = 0;
    pub const STATUS_SUCCESS: i32 = 1;
    pub const STATUS_FAILED: i32 = 2;
    pub const STATUS_DEAD: i32 = 3;

    pub async fn update_status_by_id(
        &self,
        id: &str,
        status: i32,
        send_time: DateTime<Utc>,
    ) -> AppResult<()> {
        sqlx::query(
            "UPDATE jl_data01.kafka_message_record SET status = $1, send_time = $2 WHERE id = $3",
        )
        .bind(status)
        .bind(send_time)
        .bind(id)
        .execute(&self.repo.db().pool)
        .await?;
        Ok(())
    }

    pub async fn increment_retry_count(&self, id: &str, error_msg: &str) -> AppResult<()> {
        sqlx::query(
            "UPDATE jl_data01.kafka_message_record SET retry_count = COALESCE(retry_count,0) + 1, \
status = $1, error_msg = $2 WHERE id = $3",
        )
        .bind(Self::STATUS_FAILED)
        .bind(truncate(error_msg, 500))
        .bind(id)
        .execute(&self.repo.db().pool)
        .await?;
        Ok(())
    }

    pub async fn select_failed_records(
        &self,
        max_retry: i32,
        limit: i64,
    ) -> AppResult<Vec<KafkaMessageRecord>> {
        Ok(sqlx::query_as::<_, KafkaMessageRecord>(
            "SELECT * FROM jl_data01.kafka_message_record WHERE status IN (0, 2) \
AND COALESCE(retry_count,0) < $1 ORDER BY create_time ASC LIMIT $2",
        )
        .bind(max_retry)
        .bind(limit.max(1))
        .fetch_all(&self.repo.db().pool)
        .await?)
    }

    pub async fn insert(&self, m: &KafkaMessageRecord) -> AppResult<()> {
        sqlx::query(
            "INSERT INTO jl_data01.kafka_message_record \
(id,data_id,topic,message_json,status,retry_count,create_time,send_time,error_msg) \
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        )
        .bind(&m.id)
        .bind(&m.data_id)
        .bind(&m.topic)
        .bind(&m.message_json)
        .bind(m.status)
        .bind(m.retry_count)
        .bind(m.create_time)
        .bind(m.send_time)
        .bind(&m.error_msg)
        .execute(&self.repo.db().pool)
        .await?;
        Ok(())
    }
}

// ============================================================
// 通用 SQL 小工具
// ============================================================

/// MyBatis 用 ? 占位；PostgreSQL 需要 $1..$n。这里统一改号并保留参数顺序。
fn pg_placeholders(sql: &str, _bind_count: usize) -> String {
    let mut out = String::with_capacity(sql.len() + 8);
    let mut idx = 0;
    for ch in sql.chars() {
        if ch == '?' {
            idx += 1;
            out.push_str(&format!("${}", idx));
        } else {
            out.push(ch);
        }
    }
    out
}

fn placeholders(n: usize) -> String {
    (1..=n)
        .map(|i| format!("${}", i))
        .collect::<Vec<_>>()
        .join(",")
}

async fn cursor_query<T>(
    pool: &sqlx::PgPool,
    table: &str,
    time_col: &str,
    id_col: &str,
    start: &str,
    end: &str,
    cursor_time: &str,
    cursor_uuid: &str,
    limit: i64,
) -> AppResult<Vec<T>>
where
    T: for<'r> FromRow<'r, PgRow> + Send + Unpin,
{
    // 列名来自本函数内的固定常量，不接受外部输入。
    let mut sql = format!("SELECT * FROM {} WHERE 1=1", table);
    let mut args: Vec<String> = vec![];
    if !start.is_empty() {
        sql.push_str(&format!(" AND {} >= ?", time_col));
        args.push(start.into());
    }
    if !end.is_empty() {
        sql.push_str(&format!(" AND {} < ?", time_col));
        args.push(end.into());
    }
    if !cursor_time.is_empty() {
        if !cursor_uuid.is_empty() {
            sql.push_str(&format!(" AND ({}, {}) > (?, ?)", time_col, id_col));
            args.push(cursor_time.into());
            args.push(cursor_uuid.into());
        } else {
            sql.push_str(&format!(" AND {} > ?", time_col));
            args.push(cursor_time.into());
        }
    }
    sql.push_str(&format!(
        " ORDER BY {} ASC, {} ASC LIMIT ?",
        time_col, id_col
    ));
    let sql = pg_placeholders(&sql, args.len() + 1);
    let mut q = sqlx::query_as::<_, T>(&sql);
    for a in args {
        q = q.bind(a);
    }
    q = q.bind(limit.max(1));
    Ok(q.fetch_all(pool).await?)
}

async fn count_between(
    pool: &sqlx::PgPool,
    table: &str,
    col: &str,
    start: &str,
    end: &str,
) -> AppResult<i64> {
    let sql = format!(
        "SELECT COUNT(*) FROM {} WHERE {} BETWEEN $1 AND $2",
        table, col
    );
    let n: Option<i64> = sqlx::query_scalar(&sql)
        .bind(start)
        .bind(end)
        .fetch_one(pool)
        .await?;
    Ok(n.unwrap_or(0))
}

fn truncate(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// 把「必须整数」的路径参数转成 400（对应 Spring `@PathVariable Long` 的绑定失败）。
pub fn parse_numeric_id(id: &str) -> AppResult<i64> {
    id.trim()
        .parse::<i64>()
        .map_err(|_| AppError::bad_request(format!("路径参数 id 必须是整数：{}", id)))
}

/// 读取单列（供 /healthz 之类探针使用）。
pub async fn ping(pool: &sqlx::PgPool) -> AppResult<()> {
    sqlx::query("SELECT 1").execute(pool).await?;
    Ok(())
}
