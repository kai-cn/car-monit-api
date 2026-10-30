package com.ruoyi.base.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.base.domain.ZdataTrailFitting;
import org.apache.ibatis.annotations.Param;
import org.springframework.stereotype.Repository;
import java.util.List;

/**
 * 车辆出入口拟合轨迹Mapper接口
 *
 * @author ruoyi
 * @date 2025-10-15
 */
@Repository
public interface ZdataTrailFittingMapper extends BaseMapper<ZdataTrailFitting> {
    /**
     * 查询车辆出入口拟合轨迹
     *
     * @param cid 车辆出入口拟合轨迹ID
     * @return 车辆出入口拟合轨迹
     */
    ZdataTrailFitting selectZdataTrailFittingById(String cid);

    /**
     * 查询车辆出入口拟合轨迹列表
     *
     * @param zdataTrailFitting 车辆出入口拟合轨迹
     * @return 车辆出入口拟合轨迹集合
     */
    List<ZdataTrailFitting> selectZdataTrailFittingList(ZdataTrailFitting zdataTrailFitting);

    /**
     * 游标分页按时间分片查询（用于大规模数据同步到 ES）
     * Keyset-paginated cursor query by time shard (for large-scale sync to ES).
     *
     * @param startTime  分片起始时间 (yyyy-MM-dd HH:mm:ss)
     * @param endTime    分片结束时间
     * @param cursorTime 上批最后一条的 extime（首次传 null）
     * @param cursorUuid 上批最后一条的 cid（首次传 null）
     * @param limit      本次拉取条数
     * @return 本批轨迹
     */
    List<ZdataTrailFitting> selectByCursorShard(
            @Param("startTime") String startTime,
            @Param("endTime") String endTime,
            @Param("cursorTime") String cursorTime,
            @Param("cursorUuid") String cursorUuid,
            @Param("limit") int limit
    );

}
