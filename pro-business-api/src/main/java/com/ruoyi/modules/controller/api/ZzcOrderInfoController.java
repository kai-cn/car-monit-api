package com.ruoyi.modules.controller.api;

import com.alibaba.fastjson.JSONObject;
import com.ruoyi.common.config.annotation.PermissionAnon;
import com.ruoyi.modules.service.IZzcApiService;
import com.ruoyi.modules.vo.zzc.ZzcOrderInfoCallBack;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;

@Slf4j
@Api(tags = {"中转仓接口"})
@RestController
@RequestMapping(value = "/api/zzc")
public class ZzcOrderInfoController {

    @Autowired
    private IZzcApiService zzcApiService;

    @ApiOperation(value = "中转仓回调接口", notes = "中转仓回调接口")
    @PostMapping(value = "/callBackByZzcOrder")
    @PermissionAnon
    public String callBackByZzcOrder(@RequestBody @Valid ZzcOrderInfoCallBack zzcOrderInfoCallBack) {
        log.info("中转仓回调接口返回信息：{}", JSONObject.toJSONString(zzcOrderInfoCallBack));
        return zzcApiService.callBackByZzcOrder(zzcOrderInfoCallBack);
    }
}
