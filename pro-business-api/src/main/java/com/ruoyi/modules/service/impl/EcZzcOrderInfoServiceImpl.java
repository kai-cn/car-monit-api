package com.ruoyi.modules.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.modules.entity.EcZzcOrderInfo;
import com.ruoyi.modules.mapper.EcZzcOrderInfoMapper;
import com.ruoyi.modules.service.IEcZzcOrderInfoService;
import org.springframework.stereotype.Service;
import javax.annotation.Resource;

/**
 * 中转仓订单Service业务层处理
 *
 * @author ruoyi
 * @date 2024-09-30
 */
@Service
public class EcZzcOrderInfoServiceImpl extends ServiceImpl<EcZzcOrderInfoMapper, EcZzcOrderInfo> implements IEcZzcOrderInfoService {

    @Resource
    private EcZzcOrderInfoMapper ecZzcOrderInfoMapper;


}
