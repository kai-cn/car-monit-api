package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsSzdnGantry;
import com.ruoyi.base.service.IOdsSzdnGantryService;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import com.ruoyi.base.mapper.OdsSzdnGantryIpMapper;
import com.ruoyi.base.domain.OdsSzdnGantryIp;
import com.ruoyi.base.service.IOdsSzdnGantryIpService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

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
        List<OdsSzdnGantryIp> list = odsSzdnGantryIpMapper.selectOdsSzdnGantryIpList(new OdsSzdnGantryIp());
        Map<String,OdsSzdnGantry> osSzdnGantryMap = odsSzdnGantryService.selectOdsSzdnGantryMap(new OdsSzdnGantry());
        for (OdsSzdnGantryIp rtn : list) {
            String key = CommonUtil.isNull(rtn.getGantryCode()); // 门架编号
            if(osSzdnGantryMap.containsKey(key)){
                rtn.setOdsSzdnGantry(osSzdnGantryMap.get(key));
            }
            // 门架
            map.put("gantryip:"+CommonUtil.isNull(""+rtn.getId()),rtn);
            map.put("gantryip:"+CommonUtil.isNull(""+rtn.getGantryCode()),rtn);

            // 省界门架称重事件
            map.put("bwlocation:"+CommonUtil.isNull(""+rtn.getId()),rtn);
            map.put("bwlocation:"+CommonUtil.isNull(""+rtn.getGantryCode()),rtn);

            // 省界门架抓拍事件模型
            map.put("gantryid:"+CommonUtil.isNull(""+rtn.getId()),rtn);
            map.put("gantryid:"+CommonUtil.isNull(""+rtn.getGantryCode()),rtn);


        }
        return map;

    }

    @Override
    public Set<String> selectIPSet() {
        return odsSzdnGantryIpMapper.selectIPSet();
    }
}
