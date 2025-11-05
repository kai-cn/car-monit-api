package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.domain.OdsSzdnGantry;
import com.ruoyi.base.mapper.OdsSzdnGantryMapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service;
import com.ruoyi.base.service.IOdsSzdnGantryService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 门架信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsSzdnGantryServiceImpl extends ServiceImpl<OdsSzdnGantryMapper, OdsSzdnGantry> implements IOdsSzdnGantryService {

    @Autowired
    private OdsSzdnGantryMapper odsSzdnGantryMapper;

    @Autowired
    private RedisCache redisCache;

    @Autowired
    private IOdsLwzxsfsjFeeRecords01Service feeRecords01Service;

    /**
     * 查询门架信息
     *
     * @param id 门架信息ID
     * @return 门架信息
     */
    @Override
    public OdsSzdnGantry selectOdsSzdnGantryById(String id) {
        return odsSzdnGantryMapper.selectOdsSzdnGantryById(id);
    }

    /**
     * 查询门架信息列表
     *
     * @param odsSzdnGantry 门架信息
     * @return 门架信息
     */
    @Override
    public List<OdsSzdnGantry> selectOdsSzdnGantryList(OdsSzdnGantry odsSzdnGantry) {
        return odsSzdnGantryMapper.selectOdsSzdnGantryList(odsSzdnGantry);
    }


    /**
     * 查询门架信息列表
     *
     * @param
     * @return 门架信息集合
     */
    public  List<OdsSzdnGantry> saveGantryRedis(){
        List<OdsSzdnGantry> list = odsSzdnGantryMapper.selectOdsSzdnGantryList(new OdsSzdnGantry());
        for (OdsSzdnGantry g : list) {
            Long count = feeRecords01Service.lambdaQuery().eq(OdsLwzxsfsjFeeRecords01::getGantryid, g.getGantryCode()).count();
            g.setIsData(count > 0 ? "1" : "0");
        }
        redisCache.setCacheObject(Constants.gantry_list, list);
        return  list;

    }

    /**
     * 查询门架信息列表
     *
     * @param
     * @return 门架信息集合
     */
    public List<OdsSzdnGantry> getGantryRedis(){
        List<OdsSzdnGantry> list = null;
        Object obj = redisCache.getCacheObject(Constants.gantry_list);
        if (null != obj) {
            list = (List) obj;
        } else {
            list = this.saveGantryRedis();
        }
        return list;
    }


    /**
     * 查询门架信息列表
     *
     * @param odsSzdnGantry 门架信息
     * @return 门架信息集合
     */
    @Override
    public Map<String, OdsSzdnGantry> selectOdsSzdnGantryMap(OdsSzdnGantry odsSzdnGantry) {
        Map<String, OdsSzdnGantry> map = new HashMap<String, OdsSzdnGantry>();
        List<OdsSzdnGantry> list = odsSzdnGantryMapper.selectOdsSzdnGantryList(odsSzdnGantry);
        for (OdsSzdnGantry rtn : list) {
            map.put(CommonUtil.isNull(rtn.getGantryCode()),rtn);
        }
        return map;
    }

}
