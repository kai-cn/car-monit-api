package com.ruoyi.base.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import org.apache.ibatis.annotations.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 基础-收费流水Mapper接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Repository
public interface OdsLwzxsfsjFeeRecords01Mapper extends BaseMapper<OdsLwzxsfsjFeeRecords01> {
    /**
     * 查询基础-收费流水
     *
     * @param bigId 基础-收费流水ID
     * @return 基础-收费流水
     */
    OdsLwzxsfsjFeeRecords01 selectOdsLwzxsfsjFeeRecords01ById(String bigId);

    /**
     * 查询基础-收费流水列表
     *
     * @param odsLwzxsfsjFeeRecords01 基础-收费流水
     * @return 基础-收费流水集合
     */
    List<OdsLwzxsfsjFeeRecords01> selectOdsLwzxsfsjFeeRecords01List(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01);

    /**
     * 查询门架数量
     * @param odsLwzxsfsjFeeRecords01
     * @return
     */
    public int selectGantryNum(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01);

    List<OdsLwzxsfsjFeeRecords01> selectOdsLwzxsfsjFeeRecords01ListNew(OdsLwzxsfsjFeeRecords01 bo);

    /**
     * 游标分页按时间分片查询（用于大规模数据同步到 ES）
     * Keyset-paginated cursor query by time shard (for large-scale sync to ES).
     *
     * @param startTime  分片起始时间 (yyyy-MM-dd HH:mm:ss)
     * @param endTime    分片结束时间
     * @param cursorTime 上批最后一条的 transtime（首次传 null）
     * @param cursorUuid 上批最后一条的 big_id（首次传 null）
     * @param limit      本次拉取条数
     * @return 本批收费流水
     */
    List<OdsLwzxsfsjFeeRecords01> selectByCursorShard(
            @Param("startTime") String startTime,
            @Param("endTime") String endTime,
            @Param("cursorTime") String cursorTime,
            @Param("cursorUuid") String cursorUuid,
            @Param("limit") int limit
    );
}
