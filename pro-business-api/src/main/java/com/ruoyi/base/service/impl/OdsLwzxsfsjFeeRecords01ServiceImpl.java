package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 基础-收费流水Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsLwzxsfsjFeeRecords01ServiceImpl extends ServiceImpl<OdsLwzxsfsjFeeRecords01Mapper, OdsLwzxsfsjFeeRecords01> implements IOdsLwzxsfsjFeeRecords01Service {

    @Autowired
    private OdsLwzxsfsjFeeRecords01Mapper odsLwzxsfsjFeeRecords01Mapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询基础-收费流水
     *
     * @param bigId 基础-收费流水ID
     * @return 基础-收费流水
     */
    @Override
    public OdsLwzxsfsjFeeRecords01 selectOdsLwzxsfsjFeeRecords01ById(String bigId) {
        return odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ById(bigId);
    }

    /**
     * 查询基础-收费流水列表
     *
     * @param odsLwzxsfsjFeeRecords01 基础-收费流水
     * @return 基础-收费流水
     */
    @Override
    public List<OdsLwzxsfsjFeeRecords01> selectOdsLwzxsfsjFeeRecords01List(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01) {
        return odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01);
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
    public Map<String, OdsLwzxsfsjFeeRecords01> selectOdsLwzxsfsjFeeRecords01ByQueryUuids(String queryUuids,String applyTime1, String applyTime2) {
        Map<String, OdsLwzxsfsjFeeRecords01> map = new HashMap<>();
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

        // 1. 先读缓存，收集未命中
        List<String> missList = new ArrayList<>();
        for (String uuid : uuidList) {
            String key = Constants.DATE_FeeRecord + uuid;
            Object obj = redisCache.getCacheObject(key);
            if (null != obj) {
                map.put(uuid, (OdsLwzxsfsjFeeRecords01) obj);
            } else {
                missList.add(uuid);
            }
        }
        if (missList.isEmpty()) {
            return map;
        }

        // 2. 按批 IN 查询（列表 SQL 按 transtime desc，取每个 cid 的首条即最新记录）
        for (int i = 0; i < missList.size(); i += UUID_BATCH_SIZE) {
            List<String> chunk = missList.subList(i, Math.min(i + UUID_BATCH_SIZE, missList.size()));
            OdsLwzxsfsjFeeRecords01 querybo = new OdsLwzxsfsjFeeRecords01();
            querybo.setCidList(chunk);
            querybo.setInApplyTime1(applyTime1);
            querybo.setInApplyTime2(applyTime2);
            List<OdsLwzxsfsjFeeRecords01> list = odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01List(querybo);
            Map<String, OdsLwzxsfsjFeeRecords01> loaded = new HashMap<>();
            if (list != null) {
                for (OdsLwzxsfsjFeeRecords01 row : list) {
                    if (row.getCid() != null) {
                        loaded.putIfAbsent(row.getCid(), row);
                    }
                }
            }
            for (String uuid : chunk) {
                OdsLwzxsfsjFeeRecords01 row = loaded.get(uuid);
                if (row != null) {
                    map.put(uuid, row);
                    redisCache.setCacheObject(Constants.DATE_FeeRecord + uuid, row, DETAIL_CACHE_MINUTES, TimeUnit.MINUTES);
                }
            }
        }
        return map;
    }

    /**
     * 查询基础-收费流水列表
     *
     * @param odsLwzxsfsjFeeRecords01 基础-收费流水
     * @return 基础-收费流水集合
     */
    public int selectGantryNum(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01){
        return odsLwzxsfsjFeeRecords01Mapper.selectGantryNum(odsLwzxsfsjFeeRecords01);
    }

    @Override
    public List<OdsLwzxsfsjFeeRecords01> selectOdsLwzxsfsjFeeRecords01ListNew(OdsLwzxsfsjFeeRecords01 bo) {
        return odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ListNew(bo);
    }
}
