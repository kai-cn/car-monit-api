package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeStationEnter01Mapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeStationEnter01Service;
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

    @Override
    public Map<String, OdsLwzxsfsjFeeStationEnter01> selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids(String queryUuids) {
        Map<String, OdsLwzxsfsjFeeStationEnter01> map = new HashMap<>();
        if(CommonUtil.isNotBlank(queryUuids)) {
            String[] split = queryUuids.split(",");
            List<String> uuidList = Arrays.stream(split).collect(Collectors.toList());
            for (String uuid : uuidList) {
                if(CommonUtil.isNotBlank(uuid)) {
                    String key = Constants.DATE_FeeStationEnter + uuid;
                    Object obj = redisCache.getCacheObject(key);
                    if (null != obj) {
                        map.put(uuid, (OdsLwzxsfsjFeeStationEnter01) obj);
                    } else {
                        OdsLwzxsfsjFeeStationEnter01 querybo = new OdsLwzxsfsjFeeStationEnter01();
                        querybo.setCid(uuid);
                        List<OdsLwzxsfsjFeeStationEnter01> list = odsLwzxsfsjFeeStationEnter01Mapper.selectOdsLwzxsfsjFeeStationEnter01List(querybo);
                        if (null!=list && list.size() > 0) {
                            map.put(uuid, list.get(0));
                            redisCache.setCacheObject(key, list.get(0));
                        }else{
                            redisCache.setCacheObject(key, querybo);
                        }
                    }
                }
            }
        }
        return map;
    }
}
