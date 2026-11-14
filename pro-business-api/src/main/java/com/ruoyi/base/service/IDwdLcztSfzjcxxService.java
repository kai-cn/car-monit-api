package com.ruoyi.base.service;

import com.baomidou.mybatisplus.spring.service.IService;
import com.ruoyi.base.domain.DwdLcztSfzjcxx;
import com.ruoyi.common.core.domain.AjaxResult;

import java.util.List;

/**
 * 收费站基础信息Service接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
public interface IDwdLcztSfzjcxxService extends IService<DwdLcztSfzjcxx> {
    /**
     * 查询收费站基础信息
     *
     * @param agentPk 收费站基础信息ID
     * @return 收费站基础信息
     */
    DwdLcztSfzjcxx selectDwdLcztSfzjcxxById(String agentPk);

    /**
     * 查询收费站基础信息列表
     *
     * @param dwdLcztSfzjcxx 收费站基础信息
     * @return 收费站基础信息集合
     */
    List<DwdLcztSfzjcxx> selectDwdLcztSfzjcxxList(DwdLcztSfzjcxx dwdLcztSfzjcxx);

}
