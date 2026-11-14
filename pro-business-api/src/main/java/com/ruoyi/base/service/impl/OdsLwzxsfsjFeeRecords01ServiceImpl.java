package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
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

    @Override
    public Map<String, OdsLwzxsfsjFeeRecords01> selectOdsLwzxsfsjFeeRecords01ByQueryUuids(String queryUuids,String applyTime1, String applyTime2) {
        Map<String, OdsLwzxsfsjFeeRecords01> map = new HashMap<>();
        if(CommonUtil.isNotBlank(queryUuids)) {
            String[] split = queryUuids.split(",");
            List<String> uuidList = Arrays.stream(split).collect(Collectors.toList());
            for (String uuid : uuidList) {
                if(CommonUtil.isNotBlank(uuid)) {
                    // redis查找
                    String key = Constants.DATE_FeeRecord + uuid;
                    Object obj = redisCache.getCacheObject(key);
                    if (null != obj) {
                        map.put(uuid, (OdsLwzxsfsjFeeRecords01) obj);
                    } else {
                        OdsLwzxsfsjFeeRecords01 querybo = new OdsLwzxsfsjFeeRecords01();
                        querybo.setCid(uuid);
                        querybo.setInApplyTime1(applyTime1);
                        querybo.setInApplyTime2(applyTime2);
                        List<OdsLwzxsfsjFeeRecords01> list = odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01List(querybo);
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
