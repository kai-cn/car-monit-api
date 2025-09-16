package com.ruoyi.base.service.impl;


import com.alibaba.fastjson.JSON;
import com.ruoyi.base.domain.SysUtil;
import com.ruoyi.base.domain.TrailBo;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.redis.RedisCache;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * 服务区基础信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class SysUtilServiceImpl implements ISysUtilService {


    @Autowired
    private RedisCache redisCache;

    /**
     * 新增或者修改车辆信息
     *
     * @param sysUtil 基础类
     * @return 结果
     */
    public AjaxResult saveRedis(SysUtil sysUtil) {

        List<TrailBo> list = new ArrayList<TrailBo>();

        TrailBo bo1 = new TrailBo("749364ff-b651-4c6d-8aeb-4c386b855b7d","StationCapture","2025-09-14 14:38:29", true,"stationip:36.120.3.80");
        list.add(bo1);

        TrailBo bo2 = new TrailBo("505ead39-6698-49d6-9d66-17ae9c2bea2f","GantryCapture","2025-09-14 14:41:47", null,"gantryip:36.100.120.66");
        list.add(bo2);




        String carNo = "云HPU838";
        redisCache.setCacheObject(Constants.trail + carNo, JSON.toJSON(list));

       //  List<TrailBo> rtnlist = JSONUtil.toList(jsonArray, TrailBo.class);


        return AjaxResult.success();
    }

    /**
     * 取得数据
     *
     * @param sysUtil 基础类
     * @return 结果
     */
    public AjaxResult getRedis(SysUtil sysUtil){
        return AjaxResult.success();
    }


}
