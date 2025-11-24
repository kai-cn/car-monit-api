package com.ruoyi.base.service;

import com.ruoyi.base.domain.*;
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
    void syncTrack(CarParaVO carParaVO);


    /**
     * 数据转换
     *
     * @param tracks
     * @return 结果
     */
    public TrailInfo changeData(ZdataTrailTracks tracks, List<TrailBo> josnList);

    /**
     * 同步可疑车俩
     * @param carParaVO
     * @return
     */
    Map<ZdataTrailTracks, List<TrailBo>> syncSuspiciousCar(CarParaVO carParaVO);


    /**
     * 同步可疑车俩：定时
     * startNum : 起始页面 1  最后页面 10
     *
     * @return
     */
    void syncSuspiciousCarQutaz(int startNum, int endNum);

    /**
     * 轨迹查询
     * @param carParaVO
     * @return
     */
    List<TrailInfo> carTrackQuery(CarParaVO carParaVO);


    /**
     * 轨迹查询
     * @param carParaVO
     * @return
     */
    List<ZdataTrailTracks> carTrackQueryNew(CarParaVO carParaVO);


    /**
     * 转josn对象
     * @param paraTrailPoints
     * @return
     */
    public List<TrailBo> getTrailBoList(String paraTrailPoints);


    /**
     * 获取抓拍对象
     * @param trailBo
     * @return
     */
    public TrailBo getByTrailBo(TrailBo trailBo);


    /**
     * 获取门架抓拍流水
     * @param snapshotFlow
     */
    void syncSnapshotFlow(OdsRtSzdnSnapshotFlowAddcode snapshotFlow);

    /**
     * 获取门架交易流水
     * @param feeRecords
     */
    void syncFeeRecords(OdsLwzxsfsjFeeRecords01 feeRecords);

    /**
     * 门架抓拍流水 和 获取门架交易流水 对比
     */
    void separateSnapshotFlowTimeList();

    /**
     * 是否存在
     */
    void isFeeRecordsExist();




}
