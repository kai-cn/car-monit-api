package com.ruoyi.modules.service.impl;

import com.ruoyi.modules.entity.EcShopBind;
import com.ruoyi.modules.mapper.EcShopBindMapper;
import com.ruoyi.modules.service.IEcShopBindService;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.List;

/**
 * 店铺绑定Service业务层处理
 *
 * @author ruoyi
 * @date 2024-07-04
 */
@Service
public class EcShopBindServiceImpl implements IEcShopBindService {

    @Resource
    private EcShopBindMapper ecShopBindMapper;

    /**
     * 查询店铺绑定列表
     *
     * @param ecShopBind 店铺绑定
     * @return 店铺绑定
     */
    @Override
    public List<EcShopBind> selectEcShopBindList(EcShopBind ecShopBind) {
        return ecShopBindMapper.selectEcShopBindList(ecShopBind);
    }

    /**
     * 根据店铺id 获取绑定店铺信息
     *
     * @return 店铺绑定
     */
    @Override
    public EcShopBind selectByShopId(String shopId) {
        if (StringUtils.isBlank(shopId)) {
            shopId = "-9999";
        }
        EcShopBind ecShopBind = null;

        EcShopBind queryBo = new EcShopBind();
        queryBo.setStoreId(shopId);
        List<EcShopBind> boList = ecShopBindMapper.selectEcShopAccout(queryBo);
        if (null != boList && boList.size() > 0) {
            ecShopBind = boList.get(0);
        }
        return ecShopBind;
    }
}
