// 来源:
//   ZdataLocationDictServiceImpl.java:55-82
//   OdsSzdnGantryIpServiceImpl.java:66-138
//   OdsSzdnTollStationIpServiceImpl.java:66-95
//   OdsSzdnSectionServiceImpl.java:55-84
//   OdsSzdnTollServiceImpl.java:88-107
//   OdsSzdnGantryServiceImpl.java:74-83
// 职责: 六张设备/位置字典的 Redis 缓存 + 内存 Map 装配。
// 对应关系:
//   redisCache.getCacheObject(Constants.xxx) ↔ cache.get_json
//   updateRedis() 的列表 + in-memory join      ↔ load_or_cache + join
//
// DIFF: Java 每个 ServiceImpl 各自持有一份 RedisCache 并互相 @Autowired；
// Rust 收敛为一个 DictService，轨迹富集只依赖「几张 map」，避免循环依赖。

use std::collections::HashMap;
use std::time::Duration;

use serde::de::DeserializeOwned;
use serde::Serialize;
use tracing::{info, warn};

use crate::cache::Cache;
use crate::error::AppResult;
use crate::models::*;
use crate::repo::*;
use crate::services::*;
use crate::utils;

#[derive(Clone)]
pub struct DictService {
    pub location: LocationDictRepo,
    pub gantry_ip: GantryIpRepo,
    pub gantry: GantryRepo,
    pub station_ip: TollStationIpRepo,
    pub toll: TollRepo,
    pub section: SectionRepo,
    pub cache: Option<Cache>,
}

impl DictService {
    pub fn new(
        location: LocationDictRepo,
        gantry_ip: GantryIpRepo,
        gantry: GantryRepo,
        station_ip: TollStationIpRepo,
        toll: TollRepo,
        section: SectionRepo,
        cache: Option<Cache>,
    ) -> Self {
        Self {
            location,
            gantry_ip,
            gantry,
            station_ip,
            toll,
            section,
            cache,
        }
    }

    /// 对应四个 updateRedis() 的合并：强制回源重建全部字典。
    pub async fn refresh_all(&self) -> AppResult<()> {
        let _ = self.location_map().await?;
        let _ = self.gantry_ip_map().await?;
        let _ = self.station_ip_map().await?;
        let _ = self.section_map().await?;
        let _ = self.toll_map().await?;
        let _ = self.gantry_map().await?;
        Ok(())
    }

    pub async fn location_map(&self) -> AppResult<HashMap<String, ZdataLocationDict>> {
        let list = self
            .load_or_cache(DICT_KEY_LOCATION, || self.location.list_all())
            .await?;
        Ok(list
            .into_iter()
            .map(|x| (x.raw_code.as_str().to_string(), x))
            .collect())
    }

    pub async fn gantry_ip_map(&self) -> AppResult<HashMap<String, OdsSzdnGantryIp>> {
        let list = self
            .load_or_cache(DICT_KEY_GANTRY_IP, || async {
                let mut ips = self.gantry_ip.list_all().await?;
                let gantries = self.gantry.list_all().await?;
                let by_code: HashMap<String, OdsSzdnGantry> = gantries
                    .into_iter()
                    .map(|g| (g.gantry_code.as_str().to_string(), g))
                    .collect();
                for ip in &mut ips {
                    if let Some(g) = by_code.get(ip.gantry_code.as_str()) {
                        ip.ods_szdn_gantry = Some(Box::new(g.clone()));
                    }
                }
                Ok(ips)
            })
            .await?;

        let mut m = HashMap::with_capacity(list.len() * 6);
        for item in list {
            let id = item.id.get().map(|v| v.to_string()).unwrap_or_default();
            let code = item.gantry_code.as_str().to_string();
            for prefix in ["gantryip:", "bwlocation:", "gantryid:", "gantry:"] {
                m.insert(format!("{}{}", prefix, id), item.clone());
                m.insert(format!("{}{}", prefix, code), item.clone());
            }
            m.insert(id, item.clone());
            m.insert(code, item.clone());
        }
        Ok(m)
    }

    pub async fn station_ip_map(&self) -> AppResult<HashMap<String, OdsSzdnTollStationIp>> {
        let list = self
            .load_or_cache(DICT_KEY_STATION_IP, || async {
                let mut ips = self.station_ip.list_all().await?;
                let tolls = self.toll.list_all().await?;
                let by_code: HashMap<String, OdsSzdnToll> = tolls
                    .into_iter()
                    .map(|t| (t.toll_code.as_str().to_string(), t))
                    .collect();
                for ip in &mut ips {
                    if let Some(t) = by_code.get(ip.toll_code.as_str()) {
                        ip.ods_szdn_toll = Some(Box::new(t.clone()));
                    }
                }
                Ok(ips)
            })
            .await?;

        let mut m = HashMap::with_capacity(list.len() * 6);
        for item in list {
            let ip = item.ip.as_str().to_string();
            let code = item.toll_code.as_str().to_string();
            for prefix in ["stationip:", "station:"] {
                m.insert(format!("{}{}", prefix, ip), item.clone());
                m.insert(format!("{}{}", prefix, code), item.clone());
            }
            m.insert(ip, item.clone());
            m.insert(code, item.clone());
            m.insert(utils::replace_toll_name(&item.toll_name), item.clone());
        }
        Ok(m)
    }

    pub async fn toll_map(&self) -> AppResult<HashMap<String, OdsSzdnToll>> {
        let list = self
            .load_or_cache(DICT_KEY_STATION_INFO, || self.toll.list_all())
            .await?;
        let mut m = HashMap::with_capacity(list.len() * 2);
        for item in list {
            m.insert(item.toll_code.as_str().to_string(), item.clone());
            m.insert(item.state_code_merge.as_str().to_string(), item);
        }
        Ok(m)
    }

    pub async fn gantry_map(&self) -> AppResult<HashMap<String, OdsSzdnGantry>> {
        let list = self
            .load_or_cache(DICT_KEY_GANTRY_LIST, || self.gantry.list_all())
            .await?;
        Ok(list
            .into_iter()
            .map(|g| (g.gantry_code.as_str().to_string(), g))
            .collect())
    }

    pub async fn section_map(&self) -> AppResult<HashMap<String, OdsSzdnSection>> {
        let list = self
            .load_or_cache(DICT_KEY_SECTION, || self.section.list_all())
            .await?;
        Ok(list
            .into_iter()
            .map(|s| (s.section_code.as_str().to_string(), s))
            .collect())
    }

    /// 对应 getRedisList()：先读 Redis（JSON），未命中回源并写回；缓存失败不阻断业务。
    async fn load_or_cache<T, F, Fut>(&self, key: &str, loader: F) -> AppResult<Vec<T>>
    where
        T: Serialize + DeserializeOwned + Clone,
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = AppResult<Vec<T>>>,
    {
        if let Some(c) = &self.cache {
            match c.get_json::<Vec<T>>(key).await {
                Ok(Some(list)) => return Ok(list),
                Ok(None) => {}
                Err(e) => warn!(key, err = %e, "字典缓存反序列化失败，回源重建"),
            }
        }
        let list = loader().await?;
        if let Some(c) = &self.cache {
            if let Err(e) = c.set_json(key, &list, Duration::ZERO).await {
                warn!(key, err = %e, "字典写缓存失败");
            }
        }
        info!(key, count = list.len(), "字典缓存已重建");
        Ok(list)
    }
}
