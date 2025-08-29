package com.ruoyi.base.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.base.domain.DwdLcztFwqjcxx;
import com.ruoyi.common.core.domain.AjaxResult;

import java.util.List;

/**
 * 服务区基础信息Service接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
public interface IDwdLcztFwqjcxxService extends IService<DwdLcztFwqjcxx> {
    /**
     * 查询服务区基础信息
     *
     * @param agentPk 服务区基础信息ID
     * @return 服务区基础信息
     */
    DwdLcztFwqjcxx selectDwdLcztFwqjcxxById(String agentPk);

    /**
     * 查询服务区基础信息列表
     *
     * @param dwdLcztFwqjcxx 服务区基础信息
     * @return 服务区基础信息集合
     */
    List<DwdLcztFwqjcxx> selectDwdLcztFwqjcxxList(DwdLcztFwqjcxx dwdLcztFwqjcxx);
}
