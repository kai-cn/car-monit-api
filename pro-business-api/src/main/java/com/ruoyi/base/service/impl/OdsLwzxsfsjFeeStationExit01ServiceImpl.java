package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeStationExit01Mapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeStationExit01Service;
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
 * 收费站出口流水Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsLwzxsfsjFeeStationExit01ServiceImpl extends ServiceImpl<OdsLwzxsfsjFeeStationExit01Mapper, OdsLwzxsfsjFeeStationExit01> implements IOdsLwzxsfsjFeeStationExit01Service {

    @Autowired
    private OdsLwzxsfsjFeeStationExit01Mapper odsLwzxsfsjFeeStationExit01Mapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询收费站出口流水
     *
     * @param bigId 收费站出口流水ID
     * @return 收费站出口流水
     */
    @Override
    public OdsLwzxsfsjFeeStationExit01 selectOdsLwzxsfsjFeeStationExit01ById(String bigId) {
        return odsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01ById(bigId);
    }

    /**
     * 查询收费站出口流水列表
     *
     * @param odsLwzxsfsjFeeStationExit01 收费站出口流水
     * @return 收费站出口流水
     */
    @Override
    public List<OdsLwzxsfsjFeeStationExit01> selectOdsLwzxsfsjFeeStationExit01List(OdsLwzxsfsjFeeStationExit01 odsLwzxsfsjFeeStationExit01) {
        return odsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01List(odsLwzxsfsjFeeStationExit01);
    }

    /**
     * 单批查询的 UUID 数量上限
     */
    private static final int UUID_BATCH_SIZE = 1000;

    /**
     * 详情缓存时长（分钟）
     */
    private static final int DETAIL_CACHE_MINUTES = 10;

    @Override
    public Map<String, OdsLwzxsfsjFeeStationExit01> selectOdsLwzxsfsjFeeStationExit01ByQueryUuids(String queryUuids) {
        Map<String, OdsLwzxsfsjFeeStationExit01> map = new HashMap<>();
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
            String key = Constants.DATE_FeeStationExit + uuid;
            Object obj = redisCache.getCacheObject(key);
            if (null != obj) {
                map.put(uuid, (OdsLwzxsfsjFeeStationExit01) obj);
            } else {
                missList.add(uuid);
            }
        }
        if (missList.isEmpty()) {
            return map;
        }

        for (int i = 0; i < missList.size(); i += UUID_BATCH_SIZE) {
            List<String> chunk = missList.subList(i, Math.min(i + UUID_BATCH_SIZE, missList.size()));
            OdsLwzxsfsjFeeStationExit01 querybo = new OdsLwzxsfsjFeeStationExit01();
            querybo.setCidList(chunk);
            List<OdsLwzxsfsjFeeStationExit01> list = odsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01List(querybo);
            Map<String, OdsLwzxsfsjFeeStationExit01> loaded = new HashMap<>();
            if (list != null) {
                for (OdsLwzxsfsjFeeStationExit01 row : list) {
                    if (row.getCid() != null) {
                        loaded.putIfAbsent(row.getCid(), row);
                    }
                }
            }
            for (String uuid : chunk) {
                OdsLwzxsfsjFeeStationExit01 row = loaded.get(uuid);
                if (row != null) {
                    map.put(uuid, row);
                    redisCache.setCacheObject(Constants.DATE_FeeStationExit + uuid, row, DETAIL_CACHE_MINUTES, TimeUnit.MINUTES);
                }
            }
        }
        return map;
    }
}
