package com.ruoyi.base.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.base.domain.OdsCxztFwqclls;

import java.util.List;
import java.util.Map;

/**
 * 服务区车辆流水Service接口
 *
 * @author ruoyi
 * @date 2025-10-20
 */
public interface IOdsCxztFwqcllsService extends IService<OdsCxztFwqclls> {
    /**
     * 查询服务区车辆流水
     *
     * @param bigId 服务区车辆流水ID
     * @return 服务区车辆流水
     */
    OdsCxztFwqclls selectOdsCxztFwqcllsById(Long bigId);

    /**
     * 查询服务区车辆流水列表
     *
     * @param odsCxztFwqclls 服务区车辆流水
     * @return 服务区车辆流水集合
     */
    List<OdsCxztFwqclls> selectOdsCxztFwqcllsList(OdsCxztFwqclls odsCxztFwqclls);


    Map<String, OdsCxztFwqclls> selectOdsCxztFwqcllsByQueryUuids(String provCaptureUUids);
}
