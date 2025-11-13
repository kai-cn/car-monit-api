package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
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
}
