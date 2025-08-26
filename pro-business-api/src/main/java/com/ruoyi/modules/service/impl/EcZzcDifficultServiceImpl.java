package com.ruoyi.modules.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.modules.entity.EcZzcDifficult;
import com.ruoyi.modules.mapper.EcZzcDifficultMapper;
import com.ruoyi.modules.service.IEcZzcDifficultService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/**
 * 中转仓疑难件Service业务层处理
 *
 * @author ruoyi
 * @date 2024-11-01
 */
@Service
public class EcZzcDifficultServiceImpl extends ServiceImpl<EcZzcDifficultMapper, EcZzcDifficult> implements IEcZzcDifficultService {

    @Autowired
    private EcZzcDifficultMapper ecZzcDifficultMapper;


}
