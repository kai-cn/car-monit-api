package com.ruoyi.modules.controller.api;

import com.ruoyi.common.config.annotation.ValidHeader;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.service.forest.HttpRequestService;
import com.ruoyi.modules.util.EmsRequestUtil;
import com.ruoyi.modules.vo.ems.EmsRequestModel;
import com.ruoyi.modules.vo.ems.EmsResponseModel;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiImplicitParam;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.Objects;

@Slf4j
@Api(tags = {"畅邮宝相关接口"})
@RestController
@RequestMapping(value = "/api/ems")
public class EmsRequestController {

    @Resource
    private HttpRequestService httpRequestService;
    @Resource
    private EmsRequestUtil emsRequestUtil;

    @GetMapping(value = "/getUserInfo")
    @ApiOperation(value = "获取用户信息", notes = "获取用户信息")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public Result<?> getUserInfo(@RequestParam("userName") String userName,
                                        @RequestParam("password") String password) {
        EmsRequestModel emsRequestModel = new EmsRequestModel();
        emsRequestModel.setAppKey(userName);
        emsRequestModel.setAppSecret(password);
        emsRequestUtil.getRequestModel(emsRequestModel);
        EmsResponseModel emsResponseModel = httpRequestService.getUserInfo(emsRequestModel);
        if(emsResponseModel == null){
            return Result.error500("未查询到该用户信息，请确认！");
        }
        if(Objects.equals("10000",emsResponseModel.getCode())){
            return Result.OK(emsResponseModel.getData());
        }else {
            return Result.error500(emsResponseModel.getMsg());
        }
    }

    @PostMapping(value = "/importOrder")
    @ApiOperation(value = "畅邮宝订单导入", notes = "畅邮宝订单导入")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public Result<?> importOrder(@RequestBody EmsRequestModel requestModel) {
        emsRequestUtil.getRequestModel(requestModel);
        EmsResponseModel emsResponseModel = httpRequestService.importOrder(requestModel);
        if(Objects.equals("10000",emsResponseModel.getCode())){
            //提交成功
            return Result.OK(emsResponseModel.getMsg());
        }else if(Objects.equals("10001",emsResponseModel.getCode())){
            //部分提交成功
            return Result.OK(emsResponseModel.getMsg(),emsResponseModel.getData());
        }else{
            //提交失败
            return Result.error(emsResponseModel.getMsg(),emsResponseModel.getData());
        }
    }
}
