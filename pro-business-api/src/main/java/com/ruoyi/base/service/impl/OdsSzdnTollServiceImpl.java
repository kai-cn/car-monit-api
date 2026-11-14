package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsSzdnToll;
import com.ruoyi.base.mapper.OdsSzdnTollMapper;
import com.ruoyi.base.service.IOdsSzdnTollService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 收费站基础信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsSzdnTollServiceImpl extends ServiceImpl<OdsSzdnTollMapper, OdsSzdnToll> implements IOdsSzdnTollService {

    @Autowired
    private OdsSzdnTollMapper odsSzdnTollMapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询收费站基础信息
     *
     * @param id 收费站基础信息ID
     * @return 收费站基础信息
     */
    @Override
    public OdsSzdnToll selectOdsSzdnTollById(String id) {
        return odsSzdnTollMapper.selectOdsSzdnTollById(id);
    }

    /**
     * 查询收费站基础信息列表
     *
     * @param odsSzdnToll 收费站基础信息
     * @return 收费站基础信息
     */
    @Override
    public List<OdsSzdnToll> selectOdsSzdnTollList(OdsSzdnToll odsSzdnToll) {
        return odsSzdnTollMapper.selectOdsSzdnTollList(odsSzdnToll);
    }

    /**
     * 查询收费站基础信息列表
     *
     * @param odsSzdnToll 收费站基础信息
     * @return 收费站基础信息集合
     */
    @Override
    public Map<String, OdsSzdnToll> selectOdsSzdnTollMap(OdsSzdnToll odsSzdnToll) {
        Map<String, OdsSzdnToll> map = new HashMap<String, OdsSzdnToll>();
        List<OdsSzdnToll> list = odsSzdnTollMapper.selectOdsSzdnTollList(odsSzdnToll);
        for (OdsSzdnToll rtn : list) {
            // 大脑编码
            map.put(CommonUtil.isNull(rtn.getTollCode()), rtn);
            // 国网编码
            map.put(CommonUtil.isNull(rtn.getStateCodeMerge()), rtn);
        }
        return map;
    }


    /**
     * 跟新redis
     */
    public List<OdsSzdnToll> updateRedis(){
        OdsSzdnToll odsSzdnToll = new OdsSzdnToll();
        List<OdsSzdnToll> list = odsSzdnTollMapper.selectOdsSzdnTollList(odsSzdnToll);
        redisCache.setCacheObject(Constants.station_info, list);
        return list;
    }


    /**
     * 从缓存拿到carlist
     */
    public Map<String,OdsSzdnToll> getRedisMap(){

        List<OdsSzdnToll> list = null;
        Object obj = redisCache.getCacheObject(Constants.station_info);
        if (null != obj) {
            list = (List) obj;
        } else {
            list = this.updateRedis();
        }

        Map<String, OdsSzdnToll> map = new HashMap<String, OdsSzdnToll>();
        for (OdsSzdnToll rtn : list) {
            // 大脑编码
            map.put(CommonUtil.isNull(rtn.getTollCode()), rtn);
            // 国网编码
            map.put(CommonUtil.isNull(rtn.getStateCodeMerge()), rtn);
        }
        return map;

    }





}
