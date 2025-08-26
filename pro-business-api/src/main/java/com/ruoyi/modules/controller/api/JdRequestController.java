package com.ruoyi.modules.controller.api;

import com.alibaba.fastjson.JSONObject;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.common.config.annotation.ValidHeader;
import com.ruoyi.modules.config.enums.JdApiFunctionEnum;
import com.ruoyi.modules.service.IJdApiService;
import com.ruoyi.modules.service.forest.HttpDdRequestService;
import com.ruoyi.modules.vo.dd.DdApiRequest;
import com.ruoyi.modules.vo.dd.ImCustomer;
import com.ruoyi.modules.vo.dd.ImDecrypt;
import com.github.xiaoymin.knife4j.annotations.ApiOperationSupport;
import com.ruoyi.common.util.CryptoJSTools;
import com.ruoyi.modules.vo.jd.*;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiImplicitParam;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import javax.validation.Valid;
import java.net.URLEncoder;
import java.util.Arrays;
import java.util.Objects;

@Slf4j
@Api(tags = {"京麦相关接口"})
@RestController
@RequestMapping(value = "/api/jd")
public class JdRequestController {

    @Resource
    private IJdApiService jdApiService;

    @Resource
    private HttpDdRequestService ddRequestService;

    //{"current": "1","orderTab": "waitOut","pageSize": "10","sortMode": "orderDateAsc"}
    @PostMapping(value = "/queryOrderPage")
    @ApiOperation(value = "获取订单列表信息", notes = "获取订单列表信息",hidden = true)
    @ApiOperationSupport(order = 1)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public JSONObject queryOrderPage(@RequestBody @Valid OrderPage orderPage,
                                     @RequestHeader("d-cookie") String cookie) {
        JSONObject jsonObject = JSONObject.parseObject(JSONObject.toJSONString(orderPage));
        return jdApiService.commonApiRequest(JdApiFunctionEnum.获取订单列表信息.getJdApiFunction(),jsonObject,cookie);
    }

    @PostMapping(value = "/getOrderTrack")
    @ApiOperation(value = "获取订单物流信息", notes = "获取订单物流信息",hidden = true)
    @ApiOperationSupport(order = 2)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public JSONObject getOrderTrack(@RequestParam("orderId") String orderId,
                                    @RequestHeader("d-cookie") String cookie) {
        JSONObject jsonObject = new JSONObject();
        jsonObject.put("orderId", orderId);
        return jdApiService.commonApiRequest(JdApiFunctionEnum.获取订单物流信息.getJdApiFunction(),jsonObject,cookie);
    }


    @PostMapping(value = "/queryWareList")
    @ApiOperation(value = "获取商品信息", notes = "获取商品信息",hidden = false)
    @ApiOperationSupport(order = 2)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public JSONObject queryWareList(@RequestBody JSONObject jsonObject,@RequestHeader("d-cookie") String cookie) {
        return jdApiService.commonApiRequest(JdApiFunctionEnum.获取商品信息.getJdApiFunction(),jsonObject,cookie);
    }

    //{"level": 0,"orderId": "292226329824","remark": "1"}
    @PostMapping(value = "/submitVenderRemark")
    @ApiOperation(value = "设置及修改商家备注", notes = "设置及修改商家备注",hidden = true)
    @ApiOperationSupport(order = 3)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public JSONObject submitVenderRemark(@RequestBody @Valid VenderRemark venderRemark,
                                         @RequestHeader("d-cookie") String cookie) {
        JSONObject jsonObject = JSONObject.parseObject(JSONObject.toJSONString(venderRemark));
        return jdApiService.commonApiRequest(JdApiFunctionEnum.设置及修改商家备注.getJdApiFunction(),jsonObject,cookie);
    }

    //{"param": {"level": 1,"orderIds": ["289766716527"],"remark": "缺货"}}
    @PostMapping(value = "/batchSubmitVenderRemark")
    @ApiOperation(value = "批量设置及修改商家备注", notes = "批量设置及修改商家备注",hidden = true)
    @ApiOperationSupport(order = 4)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public JSONObject batchSubmitVenderRemark(@RequestBody @Valid VenderRemarkBatch venderRemarkBatch,
                                              @RequestHeader("d-cookie") String cookie) {
        JSONObject jsonObject = JSONObject.parseObject(JSONObject.toJSONString(venderRemarkBatch));
        return jdApiService.commonApiRequest(JdApiFunctionEnum.批量设置及修改商家备注.getJdApiFunction(),jsonObject,cookie);
    }

    //物流配送：{"request":{"data":[{"orderId":291538681243,"checkType":1,"deliveryCompanyList":[{"deliveryId":"1327","deliveryNums":["4281219978909251"]}]}]}}
    //厂家自送：{"request":{"data":[{"orderId":"289766716527","deliveryCompanyList":[{"deliveryId":"1274","deliveryNums":[]}]}]}}
    //用户自提：{"request":{"data":[{"orderId":"289766716527","deliveryCompanyList":[{"deliveryId":"332098","deliveryNums":[]}]}]}}
    @PostMapping(value = "/maliciousResellingCheck")
    @ApiOperation(value = "普通发货", notes = "普通发货",hidden = true)
    @ApiOperationSupport(order = 5)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public JSONObject maliciousResellingCheck(@RequestBody @Valid Delivery delivery,
                                              @RequestHeader("d-cookie") String cookie) {
        JSONObject jsonObject = JSONObject.parseObject(JSONObject.toJSONString(delivery));
        return jdApiService.commonApiRequest(JdApiFunctionEnum.普通发货.getJdApiFunction(),jsonObject,cookie);
    }

    //{"request":{"source":"2000","data":[{"venderTaskAddressId":21318561,"deliveryType":203,"deliveryNumber":{"deliveryId":"2170","deliveryName":"邮政快递包裹","packageNum":1,"guaranteeValue":"0","epsOutShip":{"operationType":1,"branchCode":"1100099447061","insureValue":"0"}},"orderIds":[289651098551]}]}}
    @PostMapping(value = "/batchOutShip")
    @ApiOperation(value = "电子面单发货", notes = "电子面单发货",hidden = true)
    @ApiOperationSupport(order = 6)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public JSONObject batchOutShip(@RequestBody @Valid Ship ship,
                                   @RequestHeader("d-cookie") String cookie) {
        JSONObject jsonObject = JSONObject.parseObject(JSONObject.toJSONString(ship));
        return jdApiService.commonApiRequest(JdApiFunctionEnum.电子面单发货.getJdApiFunction(),jsonObject,cookie);
    }

    @PostMapping(value = "/getDesensitizationInfo")
    @ApiOperation(value = "获取隐藏的地址及电话", notes = "获取隐藏的地址及电话",hidden = true)
    @ApiOperationSupport(order = 7)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public JSONObject getDesensitizationInfo(@RequestParam("orderId") Long orderId,
                                             @RequestHeader("d-cookie") String cookie) {
        JSONObject jsonObject = new JSONObject();
        jsonObject.put("orderId", orderId);
        return jdApiService.commonApiRequest(JdApiFunctionEnum.获取隐藏的地址及电话.getJdApiFunction(),jsonObject,cookie);
    }

    @GetMapping(value = "/getAuthenticInfo")
    @ApiOperation(value = "获取真实的地址及电话", notes = "获取真实的地址及电话")
    @ApiOperationSupport(order = 8)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public Result<String> getAuthenticInfo(@RequestParam("orderId") String orderId,
                                           @RequestParam("customer") String customer,
                                           @RequestHeader("d-cookie") String cookie) {
        try {
            ImCustomer imCustomer = new ImCustomer();
            imCustomer.setCustomer(CryptoJSTools.encryptDES(customer));
            imCustomer.setOrderId(orderId);
            String boby = URLEncoder.encode(JSONObject.toJSONString(imCustomer), "UTF-8");
            DdApiRequest apiDdRequest = new DdApiRequest();
            apiDdRequest.setFunctionId("halleyOrderDetail");
            apiDdRequest.setBody(boby);
            JSONObject jsonObject = ddRequestService.baseGetRequest(apiDdRequest, cookie);
            System.out.println(jsonObject.toJSONString());
            if (Objects.equals(jsonObject.getString("code"), "0")) {
                JSONObject data = jsonObject.getJSONObject("data");
                String addressKey = data.getString("addressEncryptKey");
                String customerKey = data.getString("customerEncryptKey");
                String telKey = data.getString("telEncryptKey");

                ImDecrypt imDecrypt = new ImDecrypt();
                imDecrypt.setEncryKeys(Arrays.asList(addressKey, customerKey, telKey));
                boby = URLEncoder.encode(JSONObject.toJSONString(imDecrypt), "UTF-8");
                apiDdRequest = new DdApiRequest();
                apiDdRequest.setFunctionId("batchDecrypt");
                apiDdRequest.setBody(boby);
                JSONObject object = ddRequestService.baseGetRequest(apiDdRequest, cookie);
                System.out.println(object.toJSONString());
                if (Objects.equals(object.getString("code"), "0")) {
                    JSONObject data1 = object.getJSONObject("data");
                    return Result.OK("查询成功！",data1.getString(customerKey) + " " + data1.getString(telKey) + " " + data1.getString(addressKey));
                } else {
                    return Result.error500(jsonObject.getString("message"));
                }
            } else {
                return Result.error500(jsonObject.getString("message"));
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return Result.error500("查询失败！");
    }

    @PostMapping(value = "/syncChildCategory")
    @ApiOperation(value = "同步京东类目信息", notes = "同步京东类目信息")
    @ApiOperationSupport(order = 9)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public Result<?> syncChildCategory(@RequestHeader("d-cookie") String cookie) {
        boolean b = jdApiService.syncChildCategory(JdApiFunctionEnum.查询京东类目信息.getJdApiFunction(), cookie);
        return Result.OK(b);
    }
}
