package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.DwdLcztFwqjcxx;
import com.ruoyi.base.domain.ZdataLocationDict;
import com.ruoyi.base.mapper.DwdLcztFwqjcxxMapper;
import com.ruoyi.base.service.IDwdLcztFwqjcxxService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 服务区基础信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class DwdLcztFwqjcxxServiceImpl extends ServiceImpl<DwdLcztFwqjcxxMapper, DwdLcztFwqjcxx> implements IDwdLcztFwqjcxxService {

    @Autowired
    private DwdLcztFwqjcxxMapper dwdLcztFwqjcxxMapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询服务区基础信息
     *
     * @param agentPk 服务区基础信息ID
     * @return 服务区基础信息
     */
    @Override
    public DwdLcztFwqjcxx selectDwdLcztFwqjcxxById(String agentPk) {
        return dwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxById(agentPk);
    }

    /**
     * 查询服务区基础信息列表
     *
     * @param dwdLcztFwqjcxx 服务区基础信息
     * @return 服务区基础信息
     */
    @Override
    public List<DwdLcztFwqjcxx> selectDwdLcztFwqjcxxList(DwdLcztFwqjcxx dwdLcztFwqjcxx) {
        return dwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxList(dwdLcztFwqjcxx);
    }

    /**
     * 跟新redis
     */
    public List<DwdLcztFwqjcxx> updateRedis(){
        List<DwdLcztFwqjcxx> list = dwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxList(new DwdLcztFwqjcxx());
        redisCache.setCacheObject(Constants.fwq_name, list);
        return list;
    }


    @Override
    public Map<String, DwdLcztFwqjcxx> getServiceNameMap() {

        List<DwdLcztFwqjcxx> list = null;
        Object obj = redisCache.getCacheObject(Constants.fwq_name);
        if (null != obj) {
            list = (List) obj;
        } else {
            list = this.updateRedis();
        }

        Map<String, DwdLcztFwqjcxx> map = new HashMap<>();
        for (DwdLcztFwqjcxx fwqjcxx : list) {
            map.put(CommonUtil.isNull(fwqjcxx.getFwqmc()), fwqjcxx);
        }
        return map;
    }
}
