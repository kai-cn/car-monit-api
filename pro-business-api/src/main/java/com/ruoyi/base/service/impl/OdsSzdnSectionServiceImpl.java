package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsSzdnSection;
import com.ruoyi.base.mapper.OdsSzdnSectionMapper;
import com.ruoyi.base.service.IOdsSzdnSectionService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 路段信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsSzdnSectionServiceImpl extends ServiceImpl<OdsSzdnSectionMapper, OdsSzdnSection> implements IOdsSzdnSectionService {

    @Autowired
    private OdsSzdnSectionMapper odsSzdnSectionMapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询路段信息
     *
     * @param id 路段信息ID
     * @return 路段信息
     */
    @Override
    public OdsSzdnSection selectOdsSzdnSectionById(String id) {
        return odsSzdnSectionMapper.selectOdsSzdnSectionById(id);
    }

    /**
     * 查询路段信息列表
     *
     * @param odsSzdnSection 路段信息
     * @return 路段信息
     */
    @Override
    public List<OdsSzdnSection> selectOdsSzdnSectionList(OdsSzdnSection odsSzdnSection) {
        return odsSzdnSectionMapper.selectOdsSzdnSectionList(odsSzdnSection);
    }

    @Override
    public Map<String, OdsSzdnSection> getSectionMap() {
        List<OdsSzdnSection> list = null;
        Object obj = redisCache.getCacheObject(Constants.SECTION_ROAD_MAP);
        if (null != obj) {
            list = (List) obj;
        } else {
            list = this.updateRedis();
        }
        Map<String, OdsSzdnSection> map = new HashMap<>();
        for (OdsSzdnSection section : list) {
            map.put(CommonUtil.isNull(section.getSectionCode()), section);
        }
        return map;
    }


    /**
     * 获取路段map
     * @return
     */
    public List<OdsSzdnSection> getSectionList(){
        List<OdsSzdnSection> list = null;
        Object obj = redisCache.getCacheObject(Constants.SECTION_ROAD_MAP);
        if (null != obj) {
            list = (List) obj;
        } else {
            list = this.updateRedis();
        }
        return list;
    }



    @Override
    public List<OdsSzdnSection> updateRedis() {
        List<OdsSzdnSection> sectionList = odsSzdnSectionMapper.selectOdsSzdnSectionList(new OdsSzdnSection());
        redisCache.setCacheObject(Constants.SECTION_ROAD_MAP, sectionList);
        return sectionList;
    }
}
