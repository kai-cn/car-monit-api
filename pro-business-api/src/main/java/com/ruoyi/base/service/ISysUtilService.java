package com.ruoyi.base.service;

import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.SysUtil;
import com.ruoyi.base.domain.TrailBo;
import com.ruoyi.base.domain.ZdataTrailTracks;
import com.ruoyi.common.core.domain.AjaxResult;

import java.util.List;
import java.util.Map;

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
    Map<ZdataTrailTracks, List<TrailBo>> syncTrack(CarParaVO carParaVO);


    /**
     * 数据转换
     *
     * @param mapCar
     * @return 结果
     */
    Map<ZdataTrailTracks, List<TrailBo>> changeData(Map<ZdataTrailTracks, List<TrailBo>> mapCar);

    /**
     * 同步可疑车俩
     * @param carParaVO
     * @return
     */
    Map<ZdataTrailTracks, List<TrailBo>> syncSuspiciousCar(CarParaVO carParaVO);

    /**
     * 轨迹查询
     * @param carParaVO
     * @return
     */
    Map<ZdataTrailTracks, List<TrailBo>> carTrackQuery(CarParaVO carParaVO);
}
