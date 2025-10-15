package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.ZdataLocationDict;
import com.ruoyi.base.mapper.ZdataLocationDictMapper;
import com.ruoyi.base.service.IZdataLocationDictService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 车辆位置Service业务层处理
 *
 * @author ruoyi
 * @date 2025-10-15
 */
@Service
public class ZdataLocationDictServiceImpl extends ServiceImpl<ZdataLocationDictMapper, ZdataLocationDict> implements IZdataLocationDictService {

    @Autowired
    private ZdataLocationDictMapper zdataLocationDictMapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询车辆位置
     *
     * @param id 车辆位置ID
     * @return 车辆位置
     */
    @Override
    public ZdataLocationDict selectZdataLocationDictById(Long id) {
        return zdataLocationDictMapper.selectZdataLocationDictById(id);
    }

    /**
     * 查询车辆位置列表
     *
     * @param zdataLocationDict 车辆位置
     * @return 车辆位置
     */
    @Override
    public List<ZdataLocationDict> selectZdataLocationDictList(ZdataLocationDict zdataLocationDict) {
        return zdataLocationDictMapper.selectZdataLocationDictList(zdataLocationDict);
    }


    /**
     * 跟新redis
     */
    public  List<ZdataLocationDict> updateRedis(){
        List<ZdataLocationDict> list = zdataLocationDictMapper.selectZdataLocationDictList(new ZdataLocationDict());
        redisCache.setCacheObject(Constants.dev_post, list);
        return  list;
    }


    /**
     * 从缓存拿到carlist
     */
    public Map<String,ZdataLocationDict> getRedisList(){
        List<ZdataLocationDict> list = null;
        Object obj = redisCache.getCacheObject(Constants.dev_post);
        if (null != obj) {
            list = (List) obj;
        } else {
            list = this.updateRedis();
        }

        Map<String,ZdataLocationDict> map = new HashMap<>();
        for (ZdataLocationDict rtn : list) {
            map.put(CommonUtil.isNull(rtn.getRawCode()),rtn);
        }
        return map;
    }




}
