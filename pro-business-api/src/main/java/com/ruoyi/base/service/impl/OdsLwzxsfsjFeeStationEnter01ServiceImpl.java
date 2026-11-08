package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeStationEnter01Mapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeStationEnter01Service;
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
 * 收费站入口数据Service业务层处理
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Service
public class OdsLwzxsfsjFeeStationEnter01ServiceImpl extends ServiceImpl<OdsLwzxsfsjFeeStationEnter01Mapper, OdsLwzxsfsjFeeStationEnter01> implements IOdsLwzxsfsjFeeStationEnter01Service {

    @Autowired
    private OdsLwzxsfsjFeeStationEnter01Mapper odsLwzxsfsjFeeStationEnter01Mapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询收费站入口数据
     *
     * @param bigId 收费站入口数据ID
     * @return 收费站入口数据
     */
    @Override
    public OdsLwzxsfsjFeeStationEnter01 selectOdsLwzxsfsjFeeStationEnter01ById(Long bigId) {
        return odsLwzxsfsjFeeStationEnter01Mapper.selectOdsLwzxsfsjFeeStationEnter01ById(bigId);
    }

    /**
     * 查询收费站入口数据列表
     *
     * @param odsLwzxsfsjFeeStationEnter01 收费站入口数据
     * @return 收费站入口数据
     */
    @Override
    public List<OdsLwzxsfsjFeeStationEnter01> selectOdsLwzxsfsjFeeStationEnter01List(OdsLwzxsfsjFeeStationEnter01 odsLwzxsfsjFeeStationEnter01) {
        return odsLwzxsfsjFeeStationEnter01Mapper.selectOdsLwzxsfsjFeeStationEnter01List(odsLwzxsfsjFeeStationEnter01);
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
    public Map<String, OdsLwzxsfsjFeeStationEnter01> selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids(String queryUuids) {
        Map<String, OdsLwzxsfsjFeeStationEnter01> map = new HashMap<>();
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
            String key = Constants.DATE_FeeStationEnter + uuid;
            Object obj = redisCache.getCacheObject(key);
            if (null != obj) {
                map.put(uuid, (OdsLwzxsfsjFeeStationEnter01) obj);
            } else {
                missList.add(uuid);
            }
        }
        if (missList.isEmpty()) {
            return map;
        }

        for (int i = 0; i < missList.size(); i += UUID_BATCH_SIZE) {
            List<String> chunk = missList.subList(i, Math.min(i + UUID_BATCH_SIZE, missList.size()));
            OdsLwzxsfsjFeeStationEnter01 querybo = new OdsLwzxsfsjFeeStationEnter01();
            querybo.setCidList(chunk);
            List<OdsLwzxsfsjFeeStationEnter01> list = odsLwzxsfsjFeeStationEnter01Mapper.selectOdsLwzxsfsjFeeStationEnter01List(querybo);
            Map<String, OdsLwzxsfsjFeeStationEnter01> loaded = new HashMap<>();
            if (list != null) {
                for (OdsLwzxsfsjFeeStationEnter01 row : list) {
                    if (row.getCid() != null) {
                        loaded.putIfAbsent(row.getCid(), row);
                    }
                }
            }
            for (String uuid : chunk) {
                OdsLwzxsfsjFeeStationEnter01 row = loaded.get(uuid);
                if (row != null) {
                    map.put(uuid, row);
                    redisCache.setCacheObject(Constants.DATE_FeeStationEnter + uuid, row, DETAIL_CACHE_MINUTES, TimeUnit.MINUTES);
                }
            }
        }
        return map;
    }
}
