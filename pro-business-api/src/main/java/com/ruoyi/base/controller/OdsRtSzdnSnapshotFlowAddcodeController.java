package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import com.ruoyi.common.utils.DateUtils;
import com.ruoyi.common.utils.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 门架抓拍流水Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/snapshotflow")
public class OdsRtSzdnSnapshotFlowAddcodeController extends BaseController {

    @Autowired
    private IOdsRtSzdnSnapshotFlowAddcodeService odsRtSzdnSnapshotFlowAddcodeService;

    @Autowired
    private RedisCache redisCache;

    /**
     * 查询门架抓拍流水列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsRtSzdnSnapshotFlowAddcode odsRtSzdnSnapshotFlowAddcode) {
        startPage();

        String queryQx = "noall";
        String dataQuery = CommonUtil.isNull(redisCache.getCacheObject("data_query")); // 查询范围
        if (CommonUtil.isNotBlank(dataQuery)){
            queryQx = dataQuery;
        }

        if (!queryQx.equals("queryall")) {
            String platenumber = odsRtSzdnSnapshotFlowAddcode.getPlatenumber();
            if (CommonUtil.isBlank(platenumber)) {
                odsRtSzdnSnapshotFlowAddcode.setFlag("JiAnDong");
            }
        }


        // 路段
        String sectionCodeStr = odsRtSzdnSnapshotFlowAddcode.getSectionCodeStr();
        if (CommonUtil.isNotBlank(sectionCodeStr)){
            odsRtSzdnSnapshotFlowAddcode.setSectionList(Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList()));
            odsRtSzdnSnapshotFlowAddcode.setSectioncode("");
        }

        // 门架
        String code = CommonUtil.deleteEnd(odsRtSzdnSnapshotFlowAddcode.getCode());
        if (CommonUtil.isNotBlank(code)){
            // 服务区 收费站
            odsRtSzdnSnapshotFlowAddcode.setCodeList(Arrays.stream(code.split(",")).collect(Collectors.toList()));
            odsRtSzdnSnapshotFlowAddcode.setCode(""); // 查询范围
        }



        List<OdsRtSzdnSnapshotFlowAddcode> list = odsRtSzdnSnapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode);
        if (null !=list && list.size() > 0){
            for (OdsRtSzdnSnapshotFlowAddcode rtn :list){
                rtn.setId(StringUtils.getUUID());
                // 抓拍时间格式化
                if (null != rtn.getSnapshottime()) {
                    rtn.setSnapshottimeStr(DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, rtn.getSnapshottime()));
                }
                // 图片路径替换
                String imagesArry = CommonUtil.deleteEnd(rtn.getSnappicturepath());
                rtn.setSnappicturepath(CommonUtil.repalacePicUrl(imagesArry));
            }
        }
        return getDataTable(list);
    }

    @GetMapping("/listToExport")
    public List<OdsRtSzdnSnapshotFlowAddcode> listToExport(OdsRtSzdnSnapshotFlowAddcode odsRtSzdnSnapshotFlowAddcode) {
        startPage();

        String queryQx = "noall";
        String dataQuery = CommonUtil.isNull(redisCache.getCacheObject("data_query")); // 查询范围
        if (CommonUtil.isNotBlank(dataQuery)){
            queryQx = dataQuery;
        }

        if (!queryQx.equals("queryall")) {
            String platenumber = odsRtSzdnSnapshotFlowAddcode.getPlatenumber();
            if (CommonUtil.isBlank(platenumber)) {
                odsRtSzdnSnapshotFlowAddcode.setFlag("JiAnDong");
            }
        }

        // 路段
        String sectionCodeStr = odsRtSzdnSnapshotFlowAddcode.getSectionCodeStr();
        if (CommonUtil.isNotBlank(sectionCodeStr)){
            odsRtSzdnSnapshotFlowAddcode.setSectionList(Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList()));
            odsRtSzdnSnapshotFlowAddcode.setSectioncode("");
        }

        // 门架
        String code = CommonUtil.deleteEnd(odsRtSzdnSnapshotFlowAddcode.getCode());
        if (CommonUtil.isNotBlank(code)){
            // 服务区 收费站
            odsRtSzdnSnapshotFlowAddcode.setCodeList(Arrays.stream(code.split(",")).collect(Collectors.toList()));
            odsRtSzdnSnapshotFlowAddcode.setCode(""); // 查询范围
        }

        List<OdsRtSzdnSnapshotFlowAddcode> list = odsRtSzdnSnapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode);
        if (null !=list && list.size() > 0){
            for (OdsRtSzdnSnapshotFlowAddcode rtn :list){
                rtn.setId(StringUtils.getUUID());
                // 抓拍时间格式化
                if (null != rtn.getSnapshottime()) {
                    rtn.setSnapshottimeStr(DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, rtn.getSnapshottime()));
                }
            }
        }
        return list;
    }

    /**
     * 获取门架抓拍流水详细信息
     */
    @GetMapping(value = "/{bigId}")
    public OdsRtSzdnSnapshotFlowAddcode getInfo(@PathVariable("bigId") String bigId) {
        return  odsRtSzdnSnapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeById(bigId);
    }



}
