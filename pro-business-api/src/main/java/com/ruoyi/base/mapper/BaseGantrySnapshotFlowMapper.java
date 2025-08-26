package com.ruoyi.base.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.base.domain.BaseGantrySnapshotFlow;
import org.springframework.stereotype.Repository;
import java.util.List;

/**
 * 门架抓拍流水Mapper接口
 *
 * @author ruoyi
 * @date 2025-08-25
 */
@Repository
public interface BaseGantrySnapshotFlowMapper extends BaseMapper<BaseGantrySnapshotFlow> {
    /**
     * 查询门架抓拍流水
     *
     * @param bigId 门架抓拍流水ID
     * @return 门架抓拍流水
     */
    BaseGantrySnapshotFlow selectBaseGantrySnapshotFlowById(String bigId);

    /**
     * 查询门架抓拍流水列表
     *
     * @param baseGantrySnapshotFlow 门架抓拍流水
     * @return 门架抓拍流水集合
     */
    List<BaseGantrySnapshotFlow> selectBaseGantrySnapshotFlowList(BaseGantrySnapshotFlow baseGantrySnapshotFlow);



}
