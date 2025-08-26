package com.ruoyi.modules.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.modules.entity.EcJdOrderInfo;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 京东订单信息Mapper接口
 *
 * @author huangjun
 * @date 2024-08-30
 */
@Repository
public interface EcJdOrderInfoMapper extends BaseMapper<EcJdOrderInfo> {
    /**
     * 查询京东订单信息
     *
     * @param id 京东订单信息ID
     * @return 京东订单信息
     */
    EcJdOrderInfo selectEcJdOrderInfoById(String id);

    /**
     * 查询京东订单信息列表
     *
     * @param orderIds
     * @return 京东订单信息集合
     */
    List<EcJdOrderInfo> getJdOrderInfoList(List<String> orderIds);

    /**
     * 查询京东订单信息列表
     *
     * @param ecJdOrderInfo 京东订单信息
     * @return 京东订单信息集合
     */
    List<EcJdOrderInfo> selectEcJdOrderInfoList(EcJdOrderInfo ecJdOrderInfo);

    /**
     * 新增京东订单信息
     *
     * @param ecJdOrderInfo 京东订单信息
     * @return 结果
     */
    int insertEcJdOrderInfo(EcJdOrderInfo ecJdOrderInfo);

    /**
     * 修改京东订单信息
     *
     * @param ecJdOrderInfo 京东订单信息
     * @return 结果
     */
    int updateEcJdOrderInfo(EcJdOrderInfo ecJdOrderInfo);

    /**
     * 删除京东订单信息
     *
     * @param id 京东订单信息ID
     * @return 结果
     */
    int deleteEcJdOrderInfoById(String id);

    /**
     * 批量删除京东订单信息
     *
     * @param ids 需要删除的数据ID
     * @return 结果
     */
    int deleteEcJdOrderInfoByIds(String[] ids);
}
