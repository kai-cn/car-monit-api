package com.ruoyi.modules.controller.api;

import com.alibaba.fastjson.JSONObject;
import com.ruoyi.common.config.annotation.ValidHeader;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.service.forest.HttpKdnRequestService;
import com.ruoyi.modules.vo.kdn.KdnRequestModel;
import com.ruoyi.modules.vo.kdn.KdnResponseModel;
import com.ruoyi.common.util.MD5Example;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiImplicitParam;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;
import java.nio.charset.Charset;
import java.util.Base64;

@Slf4j
@Api(tags = {"快递鸟相关接口"})
@RestController
@RequestMapping(value = "/api/kdn")
public class KdnRequestController {

    @Value(value = "${ret.kdn.appKey}")
    private String appKey;

    @Value(value = "${ret.kdn.userId}")
    private String userId;

    @Value(value = "${ret.kdn.dataType}")
    private String dataType;

    @Value(value = "${ret.kdn.requestType}")
    private String requestType;

    @Resource
    private HttpKdnRequestService httpKdnRequestService;

    @PostMapping(value = "/getKdnOrderTrack")
    @ApiOperation(value = "快递鸟查询物流信息", notes = "快递鸟查询物流信息")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public Result<KdnResponseModel> getKdnOrderTrack(@RequestBody KdnRequestModel kdnRequestModel) {
        try {
            String requestData = JSONObject.toJSONString(kdnRequestModel);
            String dataSign = this.getSignStr(requestData);
            KdnResponseModel kdnResponseModel = httpKdnRequestService.getKdnOrderTrack(requestData, this.dataType, this.userId, dataSign, this.requestType);
            return Result.OK(kdnResponseModel);
        } catch (UnsupportedEncodingException e) {
            e.printStackTrace();
        }
       return Result.error500("查询失败");
    }

    public String getSignStr(String data) throws UnsupportedEncodingException {
        String originalString = data + this.appKey;
        String md5Hash = MD5Example.toMD5(originalString);
        byte[] bytes = md5Hash.getBytes(Charset.forName("UTF-8"));
        String encodedString = Base64.getEncoder().encodeToString(bytes);
        String sign = URLEncoder.encode(encodedString, "UTF-8");
        return sign;
    }
}
