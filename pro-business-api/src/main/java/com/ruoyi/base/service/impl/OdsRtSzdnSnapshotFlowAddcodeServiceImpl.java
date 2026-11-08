package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import com.ruoyi.common.utils.DateUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 门架抓拍流水Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsRtSzdnSnapshotFlowAddcodeServiceImpl extends ServiceImpl<OdsRtSzdnSnapshotFlowAddcodeMapper, OdsRtSzdnSnapshotFlowAddcode> implements IOdsRtSzdnSnapshotFlowAddcodeService {

    @Autowired
    private OdsRtSzdnSnapshotFlowAddcodeMapper odsRtSzdnSnapshotFlowAddcodeMapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询门架抓拍流水
     *
     * @param bigId 门架抓拍流水ID
     * @return 门架抓拍流水
     */
    @Override
    public OdsRtSzdnSnapshotFlowAddcode selectOdsRtSzdnSnapshotFlowAddcodeById(String bigId) {
        return odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeById(bigId);
    }

    /**
     * 查询门架抓拍流水列表
     *
     * @param odsRtSzdnSnapshotFlowAddcode 门架抓拍流水
     * @return 门架抓拍流水
     */
    @Override
    public List<OdsRtSzdnSnapshotFlowAddcode> selectOdsRtSzdnSnapshotFlowAddcodeList(OdsRtSzdnSnapshotFlowAddcode odsRtSzdnSnapshotFlowAddcode) {
        return odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode);
    }

    /**
     * 单批查询的 UUID 数量上限
     */
    private static final int UUID_BATCH_SIZE = 1000;

    /**
     * 详情缓存时长（分钟）
     */
    private static final int DETAIL_CACHE_MINUTES = 10;

    /**
     * 通过UUID 查询
     *
     * 优化：先批量读缓存，未命中的 UUID 合并为 IN 查询（每批 1000），
     * 命中结果回写缓存并设置 TTL；不写入负缓存，避免数据入库后永久读不到。
     *
     * @param queryUuids 逗号分隔的 UUID 列表
     * @param applyTime1 抓拍时间下界（yyyy-MM-dd HH:mm:ss）
     * @param applyTime2 抓拍时间上界（yyyy-MM-dd HH:mm:ss）
     * @return UUID -> 门架抓拍流水
     */
    @Override
    public Map<String, OdsRtSzdnSnapshotFlowAddcode> selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(String queryUuids,String applyTime1,String applyTime2) {
        Map<String, OdsRtSzdnSnapshotFlowAddcode> map = new HashMap<>();
        if (CommonUtil.isBlank(queryUuids)) {
            return map;
        }
        List<String> uuidList = Arrays.stream(queryUuids.split(","))
                .filter(CommonUtil::isNotBlank)
                .distinct()
                .collect(Collectors.toList());
        if (uuidList.isEmpty()) {
            return map;
        }

        // 1. 先读缓存，收集未命中
        List<String> missList = new ArrayList<>();
        for (String uuid : uuidList) {
            String key = Constants.DATE_GANTRY_CAPTURE + uuid;
            Object obj = redisCache.getCacheObject(key);
            if (null != obj) {
                map.put(uuid, (OdsRtSzdnSnapshotFlowAddcode) obj);
            } else {
                missList.add(uuid);
            }
        }
        if (missList.isEmpty()) {
            return map;
        }

        // 2. 按批 IN 查询，避免逐条 SQL
        Date lowerBound = DateUtils.parseDate(applyTime1);
        Date upperBound = DateUtils.parseDate(applyTime2);
        for (int i = 0; i < missList.size(); i += UUID_BATCH_SIZE) {
            List<String> chunk = missList.subList(i, Math.min(i + UUID_BATCH_SIZE, missList.size()));
            List<OdsRtSzdnSnapshotFlowAddcode> list =
                    odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeByUuidList(chunk);
            Map<String, OdsRtSzdnSnapshotFlowAddcode> loaded = new HashMap<>();
            if (list != null) {
                for (OdsRtSzdnSnapshotFlowAddcode row : list) {
                    String uuid = row.getDatauuid();
                    if (uuid == null) {
                        continue;
                    }
                    // 保持与逐条查询一致的时间范围过滤
                    if (lowerBound != null && row.getSnapshottime() != null && row.getSnapshottime().before(lowerBound)) {
                        continue;
                    }
                    if (upperBound != null && row.getSnapshottime() != null && row.getSnapshottime().after(upperBound)) {
                        continue;
                    }
                    OdsRtSzdnSnapshotFlowAddcode exists = loaded.get(uuid);
                    if (exists == null || (row.getSnapshottime() != null
                            && (exists.getSnapshottime() == null || row.getSnapshottime().after(exists.getSnapshottime()))) ) {
                        loaded.put(uuid, row);
                    }
                }
            }
            for (String uuid : chunk) {
                OdsRtSzdnSnapshotFlowAddcode row = loaded.get(uuid);
                if (row != null) {
                    map.put(uuid, row);
                    redisCache.setCacheObject(Constants.DATE_GANTRY_CAPTURE + uuid, row, DETAIL_CACHE_MINUTES, TimeUnit.MINUTES);
                }
            }
        }
        return map;
    }

    @Override
    public List<OdsRtSzdnSnapshotFlowAddcode> selectOdsRtSzdnSnapshotFlowAddcodeListNew(OdsRtSzdnSnapshotFlowAddcode bo) {
        List<OdsRtSzdnSnapshotFlowAddcode> snapshotList = odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeListNew(bo);
        return snapshotList;
    }

    /**
     * 游标分页查询
     *
     * 设计思路：
     * - 基于游标（cursor）实现高效分页查询，避免 LIMIT OFFSET 的性能问题
     * - cursor 参数通常表示上次查询最后一条记录的时间戳或 UUID，
     *   本次查询从该游标位置向后扫描，保证分页性能稳定
     * - 适用于大表（亿级）分页查询，时间复杂度 O(log n) + O(pageSize)
     *
     * @param cursor          游标（起始位置，如 UUID 或时间戳字符串）
     * @param maxSnapshotTime 最大快照时间（分页查询的上界）
     * @param pageSize        每页大小
     * @return 查询结果列表
     */
    @Override
    public List<OdsRtSzdnSnapshotFlowAddcode> queryByCursor(String cursor, String maxSnapshotTime, int pageSize) {
        return odsRtSzdnSnapshotFlowAddcodeMapper.selectByCursorShard(
                null,
                maxSnapshotTime,
                cursor,
                null,
                pageSize
        );
    }

    /**
     * 查询表中的最大快照时间
     *
     * 调用 Mapper 层 SQL：SELECT MAX(snapshottime) FROM ...
     * 将返回的 java.util.Date 格式化为 "yyyy-MM-dd HH:mm:ss" 字符串
     */
    @Override
    public String getMaxSnapshotTime() {
        try {
            java.util.Date maxDate = odsRtSzdnSnapshotFlowAddcodeMapper.getMaxSnapshotTime();
            if (maxDate == null) {
                return null;
            }
            java.text.SimpleDateFormat sdf = new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
            return sdf.format(maxDate);
        } catch (Exception e) {
            return null;
        }
    }
}
