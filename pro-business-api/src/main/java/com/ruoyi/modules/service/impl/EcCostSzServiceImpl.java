package com.ruoyi.modules.service.impl;

import com.ruoyi.modules.constant.CacheConstant;
import com.ruoyi.modules.service.IEcCostSzService;
import com.ruoyi.modules.entity.EcCostSz;
import com.ruoyi.modules.mapper.EcCostSzMapper;
import org.apache.commons.collections.CollectionUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 费用设置Service业务层处理
 *
 * @author ruoyi
 * @date 2024-07-09
 */
@Service
public class EcCostSzServiceImpl implements IEcCostSzService {

    @Autowired
    private EcCostSzMapper ecCostSzMapper;

    /**
     * 根据费用类型获取扣款明细
     *
     * @param costType
     * @return
     */
    @Override
    @Cacheable(value = CacheConstant.EC_CACHE_COST_TYPE_SZ, key = "#tenantId+#costType", unless = "#result == null ")
    public EcCostSz getByCostType(String costType, Long tenantId) {
        EcCostSz querybo = new EcCostSz();
        querybo.setTenantId(tenantId);
        querybo.setCostType(costType);
        List<EcCostSz> list = ecCostSzMapper.selectEcCostSzList(querybo);
        if(CollectionUtils.isNotEmpty(list)){
            return list.get(0);
        }
        return null;
    }

}
