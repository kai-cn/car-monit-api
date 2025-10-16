package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.ZdataTrailTracks;
import com.ruoyi.base.mapper.ZdataTrailTracksMapper;
import com.ruoyi.base.service.IZdataTrailTracksService;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
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

    @Value("${isLocalhost}")
    private String isLocalhost;

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
        carParaVO.setFlag(CommonUtil.isNull(isLocalhost));
        return zdataTrailTracksMapper.getLatestTrail(carParaVO);
    }

    /**
     * 轨迹查询
     */
    @Override
    public List<ZdataTrailTracks> getHistoryTrail(CarParaVO carParaVO) {
        carParaVO.setFlag(CommonUtil.isNull(isLocalhost));
        return zdataTrailTracksMapper.getHistoryTrail(carParaVO);
    }
}
