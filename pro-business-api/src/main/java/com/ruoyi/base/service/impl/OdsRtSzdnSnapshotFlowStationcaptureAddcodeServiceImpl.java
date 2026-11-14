package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
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
     * 根据UUID 查询
     * @param queryUuids
     * @return
     */
    @Override
    public Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(String queryUuids,String applyTime1,String applyTime2) {
        Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> map = new HashMap<>();
        if(CommonUtil.isNotBlank(queryUuids)) {
            String[] split = queryUuids.split(",");
            List<String> uuidList = Arrays.stream(split).collect(Collectors.toList());
            for (String uuid : uuidList) {
                if(CommonUtil.isNotBlank(uuid)) {
                    // redis查找
                    String key = Constants.DATE_STATION_CAPTURE + uuid;
                    Object obj = redisCache.getCacheObject(key);
                    if (null != obj) {
                        map.put(uuid, (OdsRtSzdnSnapshotFlowStationcaptureAddcode) obj);
                    } else {
                        OdsRtSzdnSnapshotFlowStationcaptureAddcode querybo = new OdsRtSzdnSnapshotFlowStationcaptureAddcode();
                        querybo.setDatauuid(uuid);
                        querybo.setApplyTime1(applyTime1);
                        querybo.setApplyTime2(applyTime2);
                        List<OdsRtSzdnSnapshotFlowStationcaptureAddcode> list = odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(querybo);
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
}
