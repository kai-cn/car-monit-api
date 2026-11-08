package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure;
import com.ruoyi.base.mapper.OdsSzdnProvinceBorderVehicleWeightNewstructureMapper;
import com.ruoyi.base.service.IOdsSzdnProvinceBorderVehicleWeightNewstructureService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 省界称重Service业务层处理
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Service
public class OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl extends ServiceImpl<OdsSzdnProvinceBorderVehicleWeightNewstructureMapper, OdsSzdnProvinceBorderVehicleWeightNewstructure> implements IOdsSzdnProvinceBorderVehicleWeightNewstructureService {

    @Autowired
    private OdsSzdnProvinceBorderVehicleWeightNewstructureMapper odsSzdnProvinceBorderVehicleWeightNewstructureMapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询省界称重
     *
     * @param dataSource 省界称重ID
     * @return 省界称重
     */
    @Override
    public OdsSzdnProvinceBorderVehicleWeightNewstructure selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(String dataSource) {
        return odsSzdnProvinceBorderVehicleWeightNewstructureMapper.selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(dataSource);
    }

    /**
     * 查询省界称重列表
     *
     * @param odsSzdnProvinceBorderVehicleWeightNewstructure 省界称重
     * @return 省界称重
     */
    @Override
    public List<OdsSzdnProvinceBorderVehicleWeightNewstructure> selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(OdsSzdnProvinceBorderVehicleWeightNewstructure odsSzdnProvinceBorderVehicleWeightNewstructure) {
        return odsSzdnProvinceBorderVehicleWeightNewstructureMapper.selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(odsSzdnProvinceBorderVehicleWeightNewstructure);
    }

    /**
     * 单批查询的 UUID 数量上限
     */
    private static final int UUID_BATCH_SIZE = 1000;

    /**
     * 详情缓存时长（分钟）
     */
    private static final int DETAIL_CACHE_MINUTES = 10;

    /**
     * 查询省界称重 : 通过IDS查询
     *
     * 优化：先批量读缓存，未命中的 UUID 合并为 IN 查询（每批 1000），
     * 命中结果回写并设置 TTL；不写入负缓存，避免数据入库后永久读不到。
     *
     * @param queryUuids 逗号分隔的 UUID 列表
     * @return UUID -> 省界称重
     */
    @Override
    public Map<String, OdsSzdnProvinceBorderVehicleWeightNewstructure> selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(String queryUuids) {
        Map<String, OdsSzdnProvinceBorderVehicleWeightNewstructure> map = new HashMap<>();
        if (CommonUtil.isBlank(queryUuids)) {
            return map;
        }
        List<String> uuidList = Arrays.stream(queryUuids.split(","))
                .filter(CommonUtil::isNotBlank)
                .distinct()
                .collect(Collectors.toList());
        if (uuidList.isEmpty()) {
            return map;
        }

        List<String> missList = new ArrayList<>();
        for (String uuid : uuidList) {
            String key = Constants.DATE_BORDER_WEIGHING_CAPTURE + uuid;
            Object obj = redisCache.getCacheObject(key);
            if (null != obj) {
                map.put(uuid, (OdsSzdnProvinceBorderVehicleWeightNewstructure) obj);
            } else {
                missList.add(uuid);
            }
        }
        if (missList.isEmpty()) {
            return map;
        }

        for (int i = 0; i < missList.size(); i += UUID_BATCH_SIZE) {
            List<String> chunk = missList.subList(i, Math.min(i + UUID_BATCH_SIZE, missList.size()));
            List<OdsSzdnProvinceBorderVehicleWeightNewstructure> list =
                    odsSzdnProvinceBorderVehicleWeightNewstructureMapper.selectOdsSzdnProvinceBorderVehicleWeightNewstructureByUuidList(chunk);
            Map<String, OdsSzdnProvinceBorderVehicleWeightNewstructure> loaded = new HashMap<>();
            if (list != null) {
                for (OdsSzdnProvinceBorderVehicleWeightNewstructure row : list) {
                    if (row.getDatauuid() != null) {
                        loaded.putIfAbsent(row.getDatauuid(), row);
                    }
                }
            }
            for (String uuid : chunk) {
                OdsSzdnProvinceBorderVehicleWeightNewstructure row = loaded.get(uuid);
                if (row != null) {
                    map.put(uuid, row);
                    redisCache.setCacheObject(Constants.DATE_BORDER_WEIGHING_CAPTURE + uuid, row, DETAIL_CACHE_MINUTES, TimeUnit.MINUTES);
                }
            }
        }
        return map;
    }
}
