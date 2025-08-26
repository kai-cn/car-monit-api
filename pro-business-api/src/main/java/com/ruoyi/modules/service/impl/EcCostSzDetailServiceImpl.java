package com.ruoyi.modules.service.impl;

import com.ruoyi.modules.entity.EcCostSzDetail;
import com.ruoyi.modules.mapper.EcCostSzDetailMapper;
import com.ruoyi.modules.service.IEcCostSzDetailService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 扣费费用明细Service业务层处理
 *
 * @author ruoyi
 * @date 2024-08-16
 */
@Service
public class EcCostSzDetailServiceImpl implements IEcCostSzDetailService {

    @Autowired
    private EcCostSzDetailMapper ecCostSzDetailMapper;


    /**
     * 查询扣费费用明细列表
     *
     * @param ecCostSzDetail 扣费费用明细
     * @return 扣费费用明细
     */
    @Override
    public List<EcCostSzDetail> selectEcCostSzDetailList(EcCostSzDetail ecCostSzDetail) {
        return ecCostSzDetailMapper.selectEcCostSzDetailList(ecCostSzDetail);
    }

}
