package com.ruoyi.base.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 门架抓拍流水Mapper接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Repository
public interface OdsRtSzdnSnapshotFlowAddcodeMapper extends BaseMapper<OdsRtSzdnSnapshotFlowAddcode> {
    /**
     * 查询门架抓拍流水
     *
     * @param bigId 门架抓拍流水ID
     * @return 门架抓拍流水
     */
    OdsRtSzdnSnapshotFlowAddcode selectOdsRtSzdnSnapshotFlowAddcodeById(String bigId);

    /**
     * 查询门架抓拍流水列表
     *
     * @param odsRtSzdnSnapshotFlowAddcode 门架抓拍流水
     * @return 门架抓拍流水集合
     */
    List<OdsRtSzdnSnapshotFlowAddcode> selectOdsRtSzdnSnapshotFlowAddcodeList(OdsRtSzdnSnapshotFlowAddcode odsRtSzdnSnapshotFlowAddcode);

    /**
     * 通过UUID 查询
     * @param uuidList
     * @return
     */
    List<OdsRtSzdnSnapshotFlowAddcode> selectOdsRtSzdnSnapshotFlowAddcodeByUuidList(@Param("uuidList") List<String> uuidList);

    List<OdsRtSzdnSnapshotFlowAddcode> selectOdsRtSzdnSnapshotFlowAddcodeListNew(OdsRtSzdnSnapshotFlowAddcode bo);

    /**
     * 游标分页按时间分片查询（用于大规模数据同步）
     *
     * @param startTime    分片起始时间
     * @param endTime      分片结束时间
     * @param cursorTime   上批最后一条的 snapshottime（首次传 null）
     * @param cursorUuid   上批最后一条的 datauuid（首次传 null）
     * @param limit        本次拉取条数
     * @return 本次批量数据
     */
    List<OdsRtSzdnSnapshotFlowAddcode> selectByCursorShard(
            @Param("startTime") String startTime,
            @Param("endTime") String endTime,
            @Param("cursorTime") String cursorTime,
            @Param("cursorUuid") String cursorUuid,
            @Param("limit") int limit
    );

    /**
     * 查询表中的最大快照时间（用于分页查询的边界）
     *
     * 设计思路：
     * - 用于游标分页时，需要知道数据的上界（最大时间）
     * - 返回最大快照时间作为分页查询的上界
     *
     * @return 最大快照时间字符串（yyyy-MM-dd HH:mm:ss 格式）
     */
    @Select("SELECT COALESCE(MAX(snapshottime), NOW()) FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode")
    java.util.Date getMaxSnapshotTime();
}
