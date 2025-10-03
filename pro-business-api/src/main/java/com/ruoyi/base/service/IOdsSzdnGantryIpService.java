package com.ruoyi.base.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.base.domain.OdsSzdnGantryIp;

import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 省界设备ipService接口
 *
 * @author ruoyi
 * @date 2025-09-18
 */
public interface IOdsSzdnGantryIpService extends IService<OdsSzdnGantryIp> {
    /**
     * 查询省界设备ip
     *
     * @param id 省界设备ipID
     * @return 省界设备ip
     */
    OdsSzdnGantryIp selectOdsSzdnGantryIpById(Long id);

    /**
     * 查询省界设备ip列表
     *
     * @param odsSzdnGantryIp 省界设备ip
     * @return 省界设备ip集合
     */
    List<OdsSzdnGantryIp> selectOdsSzdnGantryIpList(OdsSzdnGantryIp odsSzdnGantryIp);


    /**
     * 查询省界设备ip列表
     *
     * @return 省界设备ip集合
     */
    Map<String,OdsSzdnGantryIp> selectOdsSzdnGantryIpMap();


    Set<String> selectIPSet();

    /**
     * 跟新redis
     */
    List<OdsSzdnGantryIp> updateRedis();


    /**
     * 从缓存拿到carlist
     */
    List<OdsSzdnGantryIp> getRedisList();
}
