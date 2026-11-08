package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import com.ruoyi.common.utils.DateUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 收费站抓拍Service业务层处理
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Service
public class OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl extends ServiceImpl<OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper, OdsRtSzdnSnapshotFlowStationcaptureAddcode> implements IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService {

    @Autowired
    private OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询收费站抓拍
     *
     * @param bigId 收费站抓拍ID
     * @return 收费站抓拍
     */
    @Override
    public OdsRtSzdnSnapshotFlowStationcaptureAddcode selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(Long bigId) {
        return odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(bigId);
    }

    /**
     * 查询收费站抓拍列表
     *
     * @param odsRtSzdnSnapshotFlowStationcaptureAddcode 收费站抓拍
     * @return 收费站抓拍
     */
    @Override
    public List<OdsRtSzdnSnapshotFlowStationcaptureAddcode> selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(OdsRtSzdnSnapshotFlowStationcaptureAddcode odsRtSzdnSnapshotFlowStationcaptureAddcode) {
        return odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(odsRtSzdnSnapshotFlowStationcaptureAddcode);
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
     * 根据UUID 查询
     *
     * 优化：先批量读缓存，未命中的 UUID 合并为 IN 查询（每批 1000），
     * 命中结果回写并设置 TTL；不写入负缓存，避免数据入库后永久读不到。
     *
     * @param queryUuids 逗号分隔的 UUID 列表
     * @param applyTime1 抓拍时间下界（yyyy-MM-dd HH:mm:ss）
     * @param applyTime2 抓拍时间上界（yyyy-MM-dd HH:mm:ss）
     * @return UUID -> 收费站抓拍流水
     */
    @Override
    public Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(String queryUuids,String applyTime1,String applyTime2) {
        Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> map = new HashMap<>();
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

        List<String> missList = new ArrayList<>();
        for (String uuid : uuidList) {
            String key = Constants.DATE_STATION_CAPTURE + uuid;
            Object obj = redisCache.getCacheObject(key);
            if (null != obj) {
                map.put(uuid, (OdsRtSzdnSnapshotFlowStationcaptureAddcode) obj);
            } else {
                missList.add(uuid);
            }
        }
        if (missList.isEmpty()) {
            return map;
        }

        Date lowerBound = DateUtils.parseDate(applyTime1);
        Date upperBound = DateUtils.parseDate(applyTime2);
        for (int i = 0; i < missList.size(); i += UUID_BATCH_SIZE) {
            List<String> chunk = missList.subList(i, Math.min(i + UUID_BATCH_SIZE, missList.size()));
            List<OdsRtSzdnSnapshotFlowStationcaptureAddcode> list =
                    odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByUuidList(chunk);
            Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> loaded = new HashMap<>();
            if (list != null) {
                for (OdsRtSzdnSnapshotFlowStationcaptureAddcode row : list) {
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
                    loaded.putIfAbsent(uuid, row);
                }
            }
            for (String uuid : chunk) {
                OdsRtSzdnSnapshotFlowStationcaptureAddcode row = loaded.get(uuid);
                if (row != null) {
                    map.put(uuid, row);
                    redisCache.setCacheObject(Constants.DATE_STATION_CAPTURE + uuid, row, DETAIL_CACHE_MINUTES, TimeUnit.MINUTES);
                }
            }
        }
        return map;
    }
}
