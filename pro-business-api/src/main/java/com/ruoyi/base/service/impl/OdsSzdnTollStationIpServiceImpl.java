package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsSzdnToll;
import com.ruoyi.base.domain.OdsSzdnTollStationIp;
import com.ruoyi.base.mapper.OdsSzdnTollStationIpMapper;
import com.ruoyi.base.service.IOdsSzdnTollService;
import com.ruoyi.base.service.IOdsSzdnTollStationIpService;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 收费站ipService业务层处理
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Service
public class OdsSzdnTollStationIpServiceImpl extends ServiceImpl<OdsSzdnTollStationIpMapper, OdsSzdnTollStationIp> implements IOdsSzdnTollStationIpService {

    @Autowired
    private OdsSzdnTollStationIpMapper odsSzdnTollStationIpMapper;

    @Autowired
    private IOdsSzdnTollService odsSzdnTollService;

    /**
     * 查询收费站ip
     *
     * @param id 收费站ipID
     * @return 收费站ip
     */
    @Override
    public OdsSzdnTollStationIp selectOdsSzdnTollStationIpById(Long id) {
        return odsSzdnTollStationIpMapper.selectOdsSzdnTollStationIpById(id);
    }

    /**
     * 查询收费站ip列表
     *
     * @param odsSzdnTollStationIp 收费站ip
     * @return 收费站ip
     */
    @Override
    public List<OdsSzdnTollStationIp> selectOdsSzdnTollStationIpList(OdsSzdnTollStationIp odsSzdnTollStationIp) {
        return odsSzdnTollStationIpMapper.selectOdsSzdnTollStationIpList(odsSzdnTollStationIp);
    }

    /**
     * 查询收费站ip列表
     *
     * @param
     * @return 收费站ip集合
     */
    @Override
    public Map<String,OdsSzdnTollStationIp> selectStationIpMap(){
        Map<String,OdsSzdnTollStationIp> map = new HashMap<String,OdsSzdnTollStationIp>();
        // 收费站ip列表
        List<OdsSzdnTollStationIp> list = odsSzdnTollStationIpMapper.selectOdsSzdnTollStationIpList(new OdsSzdnTollStationIp());
        // 收费站map
        Map<String,OdsSzdnToll> odsSzdnTollMap = odsSzdnTollService.selectOdsSzdnTollMap(new OdsSzdnToll());
        for (OdsSzdnTollStationIp rtn : list) {
            String key = CommonUtil.isNull(rtn.getTollCode()); // 收费站编号
            if (odsSzdnTollMap.containsKey(key)){
                rtn.setOdsSzdnToll(odsSzdnTollMap.get(key));
            }
            map.put("stationip:"+CommonUtil.isNull(rtn.getIp()), rtn);
            map.put("stationip:"+CommonUtil.isNull(rtn.getTollCode()), rtn);
        }
        return map;
    }


}
