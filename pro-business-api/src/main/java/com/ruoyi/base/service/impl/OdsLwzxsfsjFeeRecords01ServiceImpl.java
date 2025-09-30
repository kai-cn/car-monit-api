package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service;
import com.ruoyi.common.utils.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 基础-收费流水Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsLwzxsfsjFeeRecords01ServiceImpl extends ServiceImpl<OdsLwzxsfsjFeeRecords01Mapper, OdsLwzxsfsjFeeRecords01> implements IOdsLwzxsfsjFeeRecords01Service {

    @Autowired
    private OdsLwzxsfsjFeeRecords01Mapper odsLwzxsfsjFeeRecords01Mapper;

    /**
     * 查询基础-收费流水
     *
     * @param bigId 基础-收费流水ID
     * @return 基础-收费流水
     */
    @Override
    public OdsLwzxsfsjFeeRecords01 selectOdsLwzxsfsjFeeRecords01ById(String bigId) {
        return odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ById(bigId);
    }

    /**
     * 查询基础-收费流水列表
     *
     * @param odsLwzxsfsjFeeRecords01 基础-收费流水
     * @return 基础-收费流水
     */
    @Override
    public List<OdsLwzxsfsjFeeRecords01> selectOdsLwzxsfsjFeeRecords01List(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01) {
        return odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01);
    }

    @Override
    public Map<String, OdsLwzxsfsjFeeRecords01> selectOdsLwzxsfsjFeeRecords01ByQueryUuids(String queryUuids) {
        Map<String, OdsLwzxsfsjFeeRecords01> map = new HashMap<>();
        if(StringUtils.isNotBlank(queryUuids)) {
            String[] split = queryUuids.split(",");
            List<String> uuidList = Arrays.stream(split).collect(Collectors.toList());
            OdsLwzxsfsjFeeRecords01 feeRecords01 = new OdsLwzxsfsjFeeRecords01();
            feeRecords01.setCidList(uuidList);
            List<OdsLwzxsfsjFeeRecords01> list = odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01List(feeRecords01);
            for (OdsLwzxsfsjFeeRecords01 rtn :list) {
                map.put(rtn.getCid(), rtn);
            }
        }
        return map;
    }
}
