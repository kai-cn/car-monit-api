package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.ZdataTrailTracks;
import com.ruoyi.base.mapper.ZdataTrailTracksMapper;
import com.ruoyi.base.service.IZdataTrailTracksService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 轨迹数据Service业务层处理
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Service
public class ZdataTrailTracksServiceImpl extends ServiceImpl<ZdataTrailTracksMapper, ZdataTrailTracks> implements IZdataTrailTracksService {

    @Autowired
    private ZdataTrailTracksMapper zdataTrailTracksMapper;


    /**
     * 查询轨迹数据
     *
     * @param uuid 轨迹数据ID
     * @return 轨迹数据
     */
    @Override
    public ZdataTrailTracks selectZdataTrailTracksById(String uuid) {
        return zdataTrailTracksMapper.selectZdataTrailTracksById(uuid);
    }

    /**
     * 查询轨迹数据列表
     *
     * @param zdataTrailTracks 轨迹数据
     * @return 轨迹数据
     */
    @Override
    public List<ZdataTrailTracks> selectZdataTrailTracksList(ZdataTrailTracks zdataTrailTracks) {
        return zdataTrailTracksMapper.selectZdataTrailTracksList(zdataTrailTracks);
    }

    /**
     * 同步可疑车俩
     * @param carParaVO
     * @return
     */
    @Override
    public List<ZdataTrailTracks> getLatestTrail(CarParaVO carParaVO) {
        return zdataTrailTracksMapper.getLatestTrail(carParaVO);
    }

    /**
     * 轨迹查询
     */
    @Override
    public List<ZdataTrailTracks> getHistoryTrail(CarParaVO carParaVO) {
        return zdataTrailTracksMapper.getHistoryTrail(carParaVO);
    }

    /**
     * 同步可疑车俩：不在轨迹点
     * @param carParaVO
     * @return
     */
    @Override
    public List<ZdataTrailTracks> getUnFitting(CarParaVO carParaVO){
        return zdataTrailTracksMapper.getUnFitting(carParaVO);
    }

    /**
     * 使用游标分页查询轨迹数据（高性能版本）
     */
    @Override
    public List<ZdataTrailTracks> getLatestTrailByCursor(CarParaVO carParaVO) {
        return zdataTrailTracksMapper.getLatestTrailByCursor(carParaVO);
    }

}
