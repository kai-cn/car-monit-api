package com.ruoyi.modules.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.modules.entity.EcZzcOrderReturnInfo;
import com.ruoyi.modules.mapper.EcZzcOrderReturnInfoMapper;
import com.ruoyi.modules.service.IEcZzcOrderReturnInfoService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/**
 * 中转仓订单返回信息Service业务层处理
 *
 * @author ruoyi
 * @date 2024-09-30
 */
@Service
public class EcZzcOrderReturnInfoServiceImpl extends ServiceImpl<EcZzcOrderReturnInfoMapper, EcZzcOrderReturnInfo> implements IEcZzcOrderReturnInfoService {

    @Autowired
    private EcZzcOrderReturnInfoMapper ecZzcOrderReturnInfoMapper;

}
