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

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
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
     * 查询省界称重 : 通过IDS查询
     *
     * @return 省界称重
     */
    @Override
    public Map<String, OdsSzdnProvinceBorderVehicleWeightNewstructure> selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(String queryUuids) {
        Map<String, OdsSzdnProvinceBorderVehicleWeightNewstructure> map = new HashMap<>();
        if (CommonUtil.isNotBlank(queryUuids)) {
            List<String> uuidList = Arrays.stream(queryUuids.split(",")).collect(Collectors.toList());
            for (String uuid : uuidList) {
                if (CommonUtil.isNotBlank(uuid)){
                    // redis查找
                    String key = Constants.BORDER_WEIGHING_CAPTURE + uuid;
                    Object obj = redisCache.getCacheObject(key);
                    if (null != obj) {
                        map.put(uuid, (OdsSzdnProvinceBorderVehicleWeightNewstructure) obj);
                    } else {
                        OdsSzdnProvinceBorderVehicleWeightNewstructure querybo = new OdsSzdnProvinceBorderVehicleWeightNewstructure();
                        querybo.setDatauuid(uuid);
                        List<OdsSzdnProvinceBorderVehicleWeightNewstructure> list = odsSzdnProvinceBorderVehicleWeightNewstructureMapper.selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(querybo);
                        if (null != list && list.size() > 0) {
                            map.put(uuid, list.get(0));
                            redisCache.setCacheObject(key, list.get(0));
                        }
                    }
                }
            }
        }
        return map;
    }
}
