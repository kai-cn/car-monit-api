package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
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
     * 通过UUID 查询
     * @param queryUuids
     * @return
     */
    @Override
    public Map<String, OdsRtSzdnSnapshotFlowAddcode> selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(String queryUuids,String applyTime1,String applyTime2) {
        Map<String, OdsRtSzdnSnapshotFlowAddcode> map = new HashMap<>();
        if(CommonUtil.isNotBlank(queryUuids)) {
            List<String> uuidList = Arrays.stream(queryUuids.split(",")).collect(Collectors.toList());
            for (String uuid : uuidList) {
                if (CommonUtil.isNotBlank(uuid)){
                    // redis查找
                    String key = Constants.DATE_GANTRY_CAPTURE + uuid;
                    Object obj = redisCache.getCacheObject(key);
                    if (null != obj) {
                        map.put(uuid, (OdsRtSzdnSnapshotFlowAddcode) obj);
                    } else {
                        OdsRtSzdnSnapshotFlowAddcode querybo = new OdsRtSzdnSnapshotFlowAddcode();
                        querybo.setDatauuid(uuid);
                        querybo.setApplyTime1(applyTime1);
                        querybo.setApplyTime2(applyTime2);
                        List<OdsRtSzdnSnapshotFlowAddcode> list = odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(querybo);
                        if (null!=list && list.size() > 0) {
                            map.put(uuid, list.get(0));
                            redisCache.setCacheObject(key, list.get(0));
                        }else{
                            redisCache.setCacheObject(key, querybo);
                        }
                    }
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
