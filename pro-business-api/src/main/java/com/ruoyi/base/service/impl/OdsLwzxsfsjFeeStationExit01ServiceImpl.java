package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeStationExit01Mapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeStationExit01Service;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
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

    @Override
    public Map<String, OdsLwzxsfsjFeeStationExit01> selectOdsLwzxsfsjFeeStationExit01ByQueryUuids(String queryUuids) {
        Map<String, OdsLwzxsfsjFeeStationExit01> map = new HashMap<>();
        if (StringUtils.isNotBlank(queryUuids)) {
            String[] split = queryUuids.split(",");
            List<String> uuidList = Arrays.stream(split).collect(Collectors.toList());
            for (String uuid : uuidList) {
                String key = Constants.FeeStationExit + uuid;
                Object obj = redisCache.getCacheObject(key);
                if (null != obj) {
                    map.put(uuid, (OdsLwzxsfsjFeeStationExit01) obj);
                } else {
                    OdsLwzxsfsjFeeStationExit01 querybo = new OdsLwzxsfsjFeeStationExit01();
                    querybo.setCid(uuid);
                    List<OdsLwzxsfsjFeeStationExit01> list = odsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01List(querybo);
                    if (null!=list && list.size() > 0) {
                        map.put(uuid, list.get(0));
                        redisCache.setCacheObject(key, list.get(0));
                    }
                }
            }
        }
        return map;
    }
}
