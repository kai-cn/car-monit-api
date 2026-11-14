package com.ruoyi.base.service;

import com.baomidou.mybatisplus.spring.service.IService;
import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.ZdataTrailTracks;

import java.util.List;

/**
 * 轨迹数据Service接口
 *
 * @author ruoyi
 * @date 2025-09-18
 */
public interface IZdataTrailTracksService extends IService<ZdataTrailTracks> {
    /**
     * 查询轨迹数据
     *
     * @param uuid 轨迹数据ID
     * @return 轨迹数据
     */
    ZdataTrailTracks selectZdataTrailTracksById(String uuid);

    /**
     * 查询轨迹数据列表
     *
     * @param zdataTrailTracks 轨迹数据
     * @return 轨迹数据集合
     */
    List<ZdataTrailTracks> selectZdataTrailTracksList(ZdataTrailTracks zdataTrailTracks);

    /**
     * 同步可疑车俩
     * @param carParaVO
     * @return
     */
    List<ZdataTrailTracks> getLatestTrail(CarParaVO carParaVO);

    /**
     * 查询车俩历史记录
     * @param carParaVO
     * @return
     */
    List<ZdataTrailTracks> getHistoryTrail(CarParaVO carParaVO);

    /**
     * 同步可疑车俩：不在轨迹点
     * @param carParaVO
     * @return
     */
    List<ZdataTrailTracks> getUnFitting(CarParaVO carParaVO);

    /**
     * 使用游标分页查询轨迹数据（高性能版本）
     * <p>
     * 相比offset分页，游标分页的优势：
     * 1. 避免大offset导致的全表扫描
     * 2. 性能更稳定，不受数据量影响
     * 3. 适合大数据量场景的分批处理
     * </p>
     * @param carParaVO 包含 lastId（游标）、pageSize、applyTime1、applyTime2 等参数
     * @return 轨迹数据列表
     */
    List<ZdataTrailTracks> getLatestTrailByCursor(CarParaVO carParaVO);
}
