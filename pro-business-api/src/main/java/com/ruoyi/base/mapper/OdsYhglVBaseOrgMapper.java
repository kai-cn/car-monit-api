package com.ruoyi.base.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.base.domain.OdsYhglVBaseOrg;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 机构信息Mapper接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Repository
public interface OdsYhglVBaseOrgMapper extends BaseMapper<OdsYhglVBaseOrg> {
    /**
     * 查询机构信息
     *
     * @param bigId 机构信息ID
     * @return 机构信息
     */
    OdsYhglVBaseOrg selectOdsYhglVBaseOrgById(String bigId);

    /**
     * 查询机构信息列表
     *
     * @param odsYhglVBaseOrg 机构信息
     * @return 机构信息集合
     */
    List<OdsYhglVBaseOrg> selectOdsYhglVBaseOrgList(OdsYhglVBaseOrg odsYhglVBaseOrg);
}
