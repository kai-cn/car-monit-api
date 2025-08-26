package com.ruoyi.modules.controller.api;

import com.alibaba.fastjson.JSONObject;
import com.ruoyi.common.config.annotation.PermissionAnon;
import com.ruoyi.common.config.annotation.ValidHeader;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.service.IDhbApiService;
import com.ruoyi.modules.vo.dhb.*;
import com.ruoyi.rabbitmq.client.RabbitMqClient;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiImplicitParam;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;

@Slf4j
@Api(tags = {"单号宝相关接口"})
@RestController
@RequestMapping(value = "/api/dhb")
public class DhbRequestController {

    @Autowired
    private IDhbApiService dhbApiService;

    @ApiOperation(value = "轨迹单下单接口", notes = "轨迹单下单接口")
    @PostMapping(value = "/placeAnOrder")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public Result<?> placeAnOrder(@RequestBody @Valid DhbPlaceAnOrdersModel dhbPlaceAnOrdersModel) {
        return dhbApiService.placeAnOrder(dhbPlaceAnOrdersModel);
    }

    @ApiOperation(value = "更新转寄快递单号(没出单号不要调这个接口，要不会出单)", notes = "更新转寄快递单号(没出单号不要调这个接口，要不会出单)")
    @PostMapping(value = "/updateAnOrder")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public Result<?> updateAnOrder(@RequestBody @Valid DhbUpdateAnOrdersModel dhbUpdateAnOrdersModel) {
        return dhbApiService.updateAnOrder(dhbUpdateAnOrdersModel);
    }

    @ApiOperation(value = "轨迹单下单查询", notes = "轨迹单下单查询")
    @PostMapping(value = "/selectOrder")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public Result<?> selectOrder(@RequestBody @Valid DhbSearchModel dhbSearchModel) {
        return dhbApiService.selectOrder(dhbSearchModel);
    }

    @ApiOperation(value = "下单回调接口", notes = "下单回调接口")
    @PostMapping(value = "/callBackByOrder")
    @PermissionAnon
    public String callBackByOrder(@RequestBody @Valid DhbOrderCallBack orderCallBack) {
        log.info("下单回调接口返回信息：{}",JSONObject.toJSONString(orderCallBack));
        return dhbApiService.callBackByOrder(orderCallBack);
    }

    @ApiOperation(value = "退款回调接口", notes = "退款回调接口")
    @PostMapping(value = "/callBackByRefund")
    @PermissionAnon
    public String callBackByRefund(@RequestBody @Valid DhbOrderCallBack orderCallBack) {
        log.info("退款回调接口返回信息：{}",JSONObject.toJSONString(orderCallBack));
        return dhbApiService.callBackByRefund(orderCallBack);
    }

    @ApiOperation(value = "投诉单回调接口", notes = "投诉单回调接口")
    @PostMapping(value = "/syncComplaintForm")
    @PermissionAnon
    public String syncComplaintForm(@RequestBody @Valid DhbFormCallBack formCallBack) {
        log.info("投诉单回调接口返回信息：{}",JSONObject.toJSONString(formCallBack));
        return dhbApiService.syncComplaintForm(formCallBack);
    }

    @ApiOperation(value = "查询用户信息", notes = "查询用户信息")
    @PostMapping(value = "/selectUser")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public JSONObject selectUser() {
        DhbUserModel dhbUserModel = new DhbUserModel();
        return dhbApiService.selectUser(dhbUserModel);
    }

    @ApiOperation(value = "取件码推送", notes = "取件码推送")
    @PostMapping(value = "/sendPickup")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public Result<?> sendPickup(@RequestBody @Valid DhbPickupModel dhbPickupModel) {
        return dhbApiService.sendPickup(dhbPickupModel);
    }

    @ApiOperation(value = "同步轨迹单状态", notes = "同步轨迹单状态")
    @GetMapping(value = "/syngOrderStatus")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public Result syngOrderStatus() {
        dhbApiService.syngOrderStatus(null);
        return Result.OK();
    }
}
