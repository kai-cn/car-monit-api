package com.ruoyi.base.service;

import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.SysUtil;
import com.ruoyi.common.core.domain.AjaxResult;

/**
 * 共用类接口表
 *
 * @author ruoyi
 * @date 2025-08-29
 */
public interface ISysUtilService {

    /**
     * 存数据
     *
     * @param sysUtil 基础类
     * @return 结果
     */
    AjaxResult saveRedis(SysUtil sysUtil);


    /**
     * 同步轨迹
     *
     * @param carParaVO carParaVO 车俩列表
     * @return 结果
     */
    AjaxResult syncTrack(CarParaVO carParaVO);


}
