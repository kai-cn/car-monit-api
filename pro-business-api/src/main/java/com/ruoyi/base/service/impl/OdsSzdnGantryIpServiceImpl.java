package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsSzdnGantry;
import com.ruoyi.base.domain.OdsSzdnGantryIp;
import com.ruoyi.base.mapper.OdsSzdnGantryIpMapper;
import com.ruoyi.base.service.IOdsSzdnGantryIpService;
import com.ruoyi.base.service.IOdsSzdnGantryService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 省界设备ipService业务层处理
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Service
public class OdsSzdnGantryIpServiceImpl extends ServiceImpl<OdsSzdnGantryIpMapper, OdsSzdnGantryIp> implements IOdsSzdnGantryIpService {

    @Autowired
    private OdsSzdnGantryIpMapper odsSzdnGantryIpMapper;

    @Autowired
    private IOdsSzdnGantryService odsSzdnGantryService;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询省界设备ip
     *
     * @param id 省界设备ipID
     * @return 省界设备ip
     */
    @Override
    public OdsSzdnGantryIp selectOdsSzdnGantryIpById(Long id) {
        return odsSzdnGantryIpMapper.selectOdsSzdnGantryIpById(id);
    }

    /**
     * 查询省界设备ip列表
     *
     * @param odsSzdnGantryIp 省界设备ip
     * @return 省界设备ip
     */
    @Override
    public List<OdsSzdnGantryIp> selectOdsSzdnGantryIpList(OdsSzdnGantryIp odsSzdnGantryIp) {
        return odsSzdnGantryIpMapper.selectOdsSzdnGantryIpList(odsSzdnGantryIp);
    }


    /**
     * 查询省界设备ip列表
     *
     * @return 省界设备ip集合
     */
    @Override
    public Map<String, OdsSzdnGantryIp> selectOdsSzdnGantryIpMap() {
        Map<String, OdsSzdnGantryIp> map = new HashMap<String, OdsSzdnGantryIp>();
        List<OdsSzdnGantryIp> list = this.getRedisList();

        for (OdsSzdnGantryIp rtn : list) {

            // 门架
            map.put("gantryip:"+CommonUtil.isNull(""+rtn.getId()),rtn);
            map.put("gantryip:"+CommonUtil.isNull(""+rtn.getGantryCode()),rtn);

            // 省界门架称重事件
            map.put("bwlocation:"+CommonUtil.isNull(""+rtn.getId()),rtn);
            map.put("bwlocation:"+CommonUtil.isNull(""+rtn.getGantryCode()),rtn);

            // 省界门架抓拍事件模型
            map.put("gantryid:"+CommonUtil.isNull(""+rtn.getId()),rtn);
            map.put("gantryid:"+CommonUtil.isNull(""+rtn.getGantryCode()),rtn);


            // 卡口流水
            map.put("gantry:"+CommonUtil.isNull(""+rtn.getId()),rtn);
            map.put("gantry:"+CommonUtil.isNull(""+rtn.getGantryCode()),rtn);


            // 通过IP 或者code查询
            map.put(CommonUtil.isNull(rtn.getId()),rtn);
            map.put(CommonUtil.isNull(rtn.getGantryCode()),rtn);


        }
        return map;

    }

    @Override
    public Set<String> selectIPSet() {
        return odsSzdnGantryIpMapper.selectIPSet();
    }


    /**
     * 跟新redis
     */
    public  List<OdsSzdnGantryIp> updateRedis(){
        Map<String, OdsSzdnGantryIp> map = new HashMap<String, OdsSzdnGantryIp>();
        List<OdsSzdnGantryIp> list = odsSzdnGantryIpMapper.selectOdsSzdnGantryIpList(new OdsSzdnGantryIp());
        OdsSzdnGantry odsSzdnGantry = new OdsSzdnGantry();
        odsSzdnGantry.setDirection("0"); // 查询上行的门架
        Map<String,OdsSzdnGantry> osSzdnGantryMap = odsSzdnGantryService.selectOdsSzdnGantryMap(odsSzdnGantry);
        for (OdsSzdnGantryIp rtn : list) {
            String key = CommonUtil.isNull(rtn.getGantryCode()); // 门架编号
            if(osSzdnGantryMap.containsKey(key)){
                rtn.setOdsSzdnGantry(osSzdnGantryMap.get(key));
            }
        }
        redisCache.setCacheObject(Constants.gantry_ip, list);
        return  list;
    }


    /**
     * 从缓存拿到carlist
     */
    public List<OdsSzdnGantryIp> getRedisList(){
        List<OdsSzdnGantryIp> list = null;
        Object obj = redisCache.getCacheObject(Constants.gantry_ip);
        if (null != obj) {
            list = (List) obj;
        } else {
            list = this.updateRedis();
        }
        return list;
    }


}
