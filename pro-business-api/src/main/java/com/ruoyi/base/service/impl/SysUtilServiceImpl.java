package com.ruoyi.base.service.impl;


import cn.hutool.json.JSONUtil;
import com.alibaba.fastjson.JSON;
import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.SysUtil;
import com.ruoyi.base.domain.TrailBo;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.redis.RedisCache;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Iterator;
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
     * 设置cache key
     *
     * @param configKey 参数键
     * @return 缓存键key
     */
    private String getCacheKey(String configKey)
    {
        return Constants.trail + configKey;
    }


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

        TrailBo bo3 = new TrailBo("706b9d6d-84f8-46c6-a4ff-3ebb03823a53","GantryCapture","2025-09-14 14:43:29", null,"gantryip:36.100.120.66");
        list.add(bo3);
        TrailBo bo4 = new TrailBo("706b9d6d-84f8-46c6-a4ff-3ebb03823a53","GantryCapture","2025-09-14 14:43:29", null,"gantryip:36.100.120.66");
        list.add(bo4);



        String carNo = "云HPU838";
        redisCache.setCacheObject(getCacheKey(carNo), JSON.toJSONString(list));

        String carNo1 = "云HPU834";

        redisCache.setCacheObject(getCacheKey(carNo1), JSON.toJSONString(list));


        List<TrailBo> rtnlist = new ArrayList<TrailBo>();

        Collection<String> keys = redisCache.keys(Constants.trail + "*");
        Iterator<String> it = keys.iterator();
        while (it.hasNext()) {
            String key = it.next();
            String keyValue = redisCache.getCacheObject(key);
            System.out.println(key + "值---"+keyValue);
            List<TrailBo> josnList = JSON.parseArray(keyValue,TrailBo.class);
            rtnlist.addAll(josnList);
        }


        return AjaxResult.success(rtnlist);
    }

    /**
     * 同步轨迹
     *
     * @param carParaVO carParaVO 车俩列表
     * @return 结果
     */
    public AjaxResult syncTrack(CarParaVO carParaVO){
        return AjaxResult.success(carParaVO);
    }


}
