package com.ruoyi.modules.service.impl;

import com.ruoyi.common.util.StringUtils;
import com.ruoyi.modules.service.IComplaintFormService;
import com.ruoyi.modules.service.IDhbApiService;
import com.ruoyi.modules.service.IEcShopAccountService;
import com.ruoyi.modules.service.IOrderFormService;
import com.ruoyi.modules.service.forest.HttpDhbRequestService;
import com.alibaba.fastjson.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.config.enums.CostTypeEnum;
import com.ruoyi.modules.util.DhbRequestUtil;

import com.ruoyi.modules.entity.ComplaintForm;
import com.ruoyi.modules.entity.EcShopAccount;
import com.ruoyi.modules.entity.OrderForm;
import com.ruoyi.modules.vo.dhb.*;
import com.ruoyi.rabbitmq.client.RabbitMqClient;
import com.ruoyi.rabbitmq.config.MqConstant;
import com.ruoyi.rabbitmq.config.base.BaseMap;
import org.apache.commons.collections.CollectionUtils;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.util.*;

/**
 * @Description: 京东京麦接口
 * @Author: ret-boot
 * @Date:   2024-04-28
 * @Version: V1.0
 */
@Service
public class DhbApiServiceImpl implements IDhbApiService {
    @Resource
    private HttpDhbRequestService httpDhbRequestService;
    @Autowired
    private IComplaintFormService complaintFormService;
    @Autowired
    private IEcShopAccountService ecShopAccountService;
    @Autowired
    private IOrderFormService orderFormService;
    @Resource
    private DhbRequestUtil dhbRequestUtil;
    @Autowired
    private RabbitMqClient rabbitMqClient;
    @Value("${spring.rabbitmq.is-send-message}")
    private boolean isSendMessage;


    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result placeAnOrder(DhbPlaceAnOrdersModel dhbPlaceAnOrdersModel) {
        //2、再调用单号宝接口
        dhbRequestUtil.getPlaceAnOrdersModel(dhbPlaceAnOrdersModel);
        JSONObject jsonObject = httpDhbRequestService.placeAnOrder(dhbPlaceAnOrdersModel);
        if("success".equals(jsonObject.getString("data"))){
            List<Order> orders = dhbPlaceAnOrdersModel.getOrders();
            if (this.isSendMessage && CollectionUtils.isNotEmpty(orders)) {
                for (Order order:orders) {
                    //发送消息到MQ，等待5分钟执行
                    this.sendMessagesToMq(order.getShopOrderNo(), 300000);
                }
            }
            return Result.OK("下单成功！");
        }
        return Result.error("下单失败！",jsonObject);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result updateAnOrder(DhbUpdateAnOrdersModel dhbUpdateAnOrdersModel) {
        dhbRequestUtil.getUpdateAnOrderModel(dhbUpdateAnOrdersModel);
        JSONObject jsonObject = httpDhbRequestService.updateAnOrder(dhbUpdateAnOrdersModel);
        if("success".equals(jsonObject.getString("data"))){
            return Result.OK("更新成功！");
        }
        return Result.error("更新失败："+jsonObject.getString("msg"));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public String callBackByOrder(DhbOrderCallBack orderCallBack) {
        System.out.println("orderCallBack" + JSONObject.toJSONString(orderCallBack));
        String dataStr = orderCallBack.getShopOrderNo() + orderCallBack.getExpressNo();
        if(dhbRequestUtil.verifySign(dataStr,orderCallBack.getSign())){
            if(Objects.equals(0,orderCallBack.getCode())){
                DhbSearchModel dhbSearchModel = new DhbSearchModel();
                dhbSearchModel.setShopOrderNo(orderCallBack.getShopOrderNo());
                dhbRequestUtil.getSearchModel(dhbSearchModel);
                JSONObject jsonObject = httpDhbRequestService.selectOrder(dhbSearchModel);
                System.out.println("jsonObject" + JSONObject.toJSONString(jsonObject));
                JSONObject data = jsonObject.getJSONObject("data");

                LambdaUpdateWrapper<OrderForm> lambdaUpdateWrapper = new LambdaUpdateWrapper();
                if(data != null){
                    String message = data.getString("message");
                    Integer status = data.getInteger("status")!= null?data.getInteger("status"):0;
                    Integer setpStatus = data.getInteger("setpStatus")!= null?data.getInteger("setpStatus"):0;

                    if(status == 1){
                        //1待处理

                    }else if(status == 2 || status == 4){
                        //2出单失败 -- 同步物流出单退回预扣费
                        this.doF(orderCallBack,CostTypeEnum.tbwl_cdykf.getCode());
                    }else if(status == 3 && setpStatus == 2 && StringUtils.isNotBlank(orderCallBack.getExpressNo())){
                        //todo: 回调的时候还是待推送状态，只有推送完了setpStatus才会等于3，所以这个判断2就行了
                        //关联成功 -- 先同步物流出单退回预扣费，再同步物流出单实际扣费
                        status = 5;
                        setpStatus = 3;
                        //同步物流出单退回预扣费
                        Result result = this.doF(orderCallBack,CostTypeEnum.tbwl_cdykf.getCode());
                        //同步物流出单实际扣费
                        if(result.isSuccess()){
                            //同步物流出单实际扣费
                            this.doS(orderCallBack,CostTypeEnum.tbwl_cdshkf.getCode());
                        }
                        //快递单号
                        lambdaUpdateWrapper.set(OrderForm::getExpressNo,orderCallBack.getExpressNo());
                        lambdaUpdateWrapper.set(OrderForm::getMessage,"韵达快递：" + data.getString("expressNo"));
                    }else if(status == 3 && Objects.equals(message,"success")){
                        //出单成功
                        status = 3;
                    }else if(!Objects.equals(message,"success")){
                        //关联失败
                        status = 6;
                        //同步物流出单退回预扣费
                        this.doF(orderCallBack,CostTypeEnum.tbwl_cdykf.getCode());
                    }
                    lambdaUpdateWrapper.set(OrderForm::getStatus, status);
                    lambdaUpdateWrapper.set(OrderForm::getSetpStatus, setpStatus);
                    lambdaUpdateWrapper.set(OrderForm::getBalance,data.getString("balance"));
                    if(!"success".equals(message)){
                        lambdaUpdateWrapper.set(OrderForm::getMessage, message);
                    }
                }
                lambdaUpdateWrapper.eq(OrderForm::getShopOrderNo,orderCallBack.getShopOrderNo());
                orderFormService.update(lambdaUpdateWrapper);
                return "success";
            }else{
                /*
                * {
                    "code": 1,
                    "expressNo": "",
                    "message": "由于您未及时推送取件码，您被暂时禁止使用韵达延迟单",
                    "shopOrderNo": "298836148385",
                    "sign": "15f1b22b1c62747a3e9d2502b590a9b4"
                }*/
                //同步物流出单退回预扣费
                this.doF(orderCallBack,CostTypeEnum.tbwl_cdykf.getCode());
                LambdaUpdateWrapper<OrderForm> lambdaUpdateWrapper = new LambdaUpdateWrapper();
                lambdaUpdateWrapper.set(OrderForm::getStatus,6);
                lambdaUpdateWrapper.set(OrderForm::getExpressNo,orderCallBack.getExpressNo());
                lambdaUpdateWrapper.set(OrderForm::getMessage,orderCallBack.getMessage());
                lambdaUpdateWrapper.eq(OrderForm::getShopOrderNo,orderCallBack.getShopOrderNo());
                orderFormService.update(lambdaUpdateWrapper);
                return "success";
            }
        }
        return "fail";
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void syngOrderStatus(String orderId){
        LambdaQueryWrapper<OrderForm> queryWrapper = new LambdaQueryWrapper<>();
        if(StringUtils.isNotBlank(orderId)){
            queryWrapper.eq(OrderForm::getShopOrderNo,orderId);
        }
        queryWrapper.nested(wrapper -> wrapper.eq(OrderForm::getStatus, 1)
                .or(i -> i.eq(OrderForm::getStatus, 3).and(b -> b.lt(OrderForm::getSetpStatus, 3))));
        List<OrderForm> list = orderFormService.list(queryWrapper);

        for (OrderForm orderForm:list) {
            DhbSearchModel dhbSearchModel = new DhbSearchModel();
            dhbSearchModel.setShopOrderNo(orderForm.getShopOrderNo());
            dhbRequestUtil.getSearchModel(dhbSearchModel);
            JSONObject jsonObject = httpDhbRequestService.selectOrder(dhbSearchModel);
            System.out.println("jsonObject" + JSONObject.toJSONString(jsonObject));
            JSONObject data = jsonObject.getJSONObject("data");

            DhbOrderCallBack orderCallBack = new DhbOrderCallBack().setShopOrderNo(orderForm.getShopOrderNo());
            LambdaUpdateWrapper<OrderForm> lambdaUpdateWrapper = new LambdaUpdateWrapper();
                if(data != null){
                    String message = data.getString("message");
                    Integer status = data.getInteger("status")!= null?data.getInteger("status"):0;
                    Integer setpStatus = data.getInteger("setpStatus")!= null?data.getInteger("setpStatus"):0;

                    if(status == 1){
                        //1待处理
                        if(StringUtils.isNotBlank(orderId)){
                            //还没出单号，重新放入MQ中，等待下次执行
                            this.sendMessagesToMq(orderId, 300000);
                        }
                    }else if(status == 2 || status == 4){
                        //2出单失败 -- 同步物流出单退回预扣费
                        this.doF(orderCallBack,CostTypeEnum.tbwl_cdykf.getCode());
                    }else if(status == 3 && setpStatus == 3){
                        //关联成功 -- 先同步物流出单退回预扣费，再同步物流出单实际扣费
                        status = 5;
                        //同步物流出单退回预扣费
                        Result result = this.doF(orderCallBack,CostTypeEnum.tbwl_cdykf.getCode());
                        //同步物流出单实际扣费
                        if(result.isSuccess()){
                            this.doS(orderCallBack,CostTypeEnum.tbwl_cdshkf.getCode());
                        }
                        //快递单号
                        lambdaUpdateWrapper.set(OrderForm::getExpressNo,data.getString("expressNo"));
                        lambdaUpdateWrapper.set(OrderForm::getMessage,"韵达快递：" + data.getString("expressNo"));

                    }else if(status == 3 && Objects.equals(message,"success")){
                        //出单成功
                        status = 3;
                        //还没出单号，重新放入MQ中，等待下次执行
                        if(StringUtils.isNotBlank(orderId)){
                            //还没出单号，重新放入MQ中，等待下次执行
                            this.sendMessagesToMq(orderId, 300000);
                        }
                    }else if(!Objects.equals(message,"success")){
                        //关联失败
                        status = 6;
                        //同步物流出单退回预扣费
                        this.doF(orderCallBack,CostTypeEnum.tbwl_cdykf.getCode());
                    }
                    lambdaUpdateWrapper.set(OrderForm::getStatus, status);
                    lambdaUpdateWrapper.set(OrderForm::getSetpStatus, setpStatus);
                    lambdaUpdateWrapper.set(OrderForm::getBalance,data.getString("balance"));
                    if(!"success".equals(message)){
                        lambdaUpdateWrapper.set(OrderForm::getMessage, message);
                    }
                }
                lambdaUpdateWrapper.eq(OrderForm::getShopOrderNo,orderCallBack.getShopOrderNo());
                orderFormService.update(lambdaUpdateWrapper);
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public String callBackByRefund(DhbOrderCallBack orderCallBack) {
        String dataStr = String.valueOf(orderCallBack.getCode() + Long.valueOf(orderCallBack.getShopOrderNo()));
        if(dhbRequestUtil.verifySign(dataStr,orderCallBack.getSign())){
            if(Objects.equals(0,orderCallBack.getCode())){
                DhbSearchModel dhbSearchModel = new DhbSearchModel();
                dhbSearchModel.setShopOrderNo(orderCallBack.getShopOrderNo());
                dhbRequestUtil.getSearchModel(dhbSearchModel);
                JSONObject jsonObject = httpDhbRequestService.selectOrder(dhbSearchModel);
                JSONObject data = jsonObject.getJSONObject("data");
                LambdaUpdateWrapper<OrderForm> lambdaUpdateWrapper = new LambdaUpdateWrapper();
                if(data != null){
                    lambdaUpdateWrapper.set(OrderForm::getStatus, data.getInteger("status"));
                    lambdaUpdateWrapper.set(OrderForm::getBalance,data.getString("balance"));
                    lambdaUpdateWrapper.set(OrderForm::getMessage,data.getString("message"));
                }
                //快递单号
                lambdaUpdateWrapper.set(OrderForm::getMessage,orderCallBack.getMessage());
                lambdaUpdateWrapper.set(OrderForm::getExpressNo,orderCallBack.getExpressNo());
                lambdaUpdateWrapper.eq(OrderForm::getShopOrderNo,orderCallBack.getShopOrderNo());

                //同步物流出单退回预扣费
                this.doF(orderCallBack,CostTypeEnum.tbwl_cdykf.getCode());

                orderFormService.update(lambdaUpdateWrapper);
                return "success";
            }
        }
        return "fail";
    }

    /**
     * @Description: 扣款
     * @Author HuangJun
     * @Date 2024/7/23 15:23
     * @Return
     */
    public Result doS(DhbOrderCallBack orderCallBack,String costType){
        //获取扣款业务类型对应的费用标准
        List<OrderForm> list = orderFormService.list(new LambdaQueryWrapper<OrderForm>().eq(OrderForm::getShopOrderNo, orderCallBack.getShopOrderNo()));
        if(list != null && !list.isEmpty()){
            OrderForm orderForm = list.get(0);
            Result result = ecShopAccountService.checkPrePay(costType, orderForm.getStoreId(), "2", orderForm.getTenantId(),1, null);
            EcShopAccount ecShopAccount = null;
            if (result.isSuccess()) {
                // 成功
                ecShopAccount = (EcShopAccount) result.getResult();
            }else{
                return result;
            }

            //执行扣款
            String msg = CostTypeEnum.getNameByCode(costType) + ":" + ecShopAccount.getPayTotalMoney();
            //执行扣款逻辑
            ecShopAccountService.doPay(costType,orderCallBack.getShopOrderNo(), orderForm.getStoreId(),orderForm.getStoreName(),msg,ecShopAccount,null);
        }
        return Result.OK();
    }

    /**
     * @Description: 退款
     * @Author HuangJun
     * @Date 2024/7/23 15:23
     * @Return
     */
    public Result doF(DhbOrderCallBack orderCallBack,String costType){
        //获取扣款业务类型对应的费用标准
        List<OrderForm> list = orderFormService.list(new LambdaQueryWrapper<OrderForm>().eq(OrderForm::getShopOrderNo, orderCallBack.getShopOrderNo()));
        if(list != null && !list.isEmpty()){
            OrderForm orderForm = list.get(0);
            // 查询账号余额度
            EcShopAccount ecShopAccount = ecShopAccountService.selectEcShopAccountBO(orderForm.getStoreId(),"2");
            //这里传的是预扣费的类型，否则查不到数据
            ecShopAccount.setCostType(costType);
            ecShopAccount.setOrderId(orderCallBack.getShopOrderNo());
            //执行退款逻辑
            return ecShopAccountService.doRefund(ecShopAccount,CostTypeEnum.tbwl_cdthykf);
        }
        return Result.error("订单"+orderCallBack.getShopOrderNo()+"不存在，请确认！");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public String syncComplaintForm(DhbFormCallBack formCallBack) {
        ComplaintFormModel data = formCallBack.getData();
        String dataStr = data.getShopOrderNo() + data.getExpressNo();
        if(dhbRequestUtil.verifySign(dataStr, formCallBack.getSign())){
            LambdaQueryWrapper<OrderForm> queryWrapper = new LambdaQueryWrapper<OrderForm>()
                    .eq(OrderForm::getShopOrderNo, data.getShopOrderNo())
                    .eq(OrderForm::getExpressNo,data.getExpressNo());
            List<OrderForm> list = orderFormService.list(queryWrapper);
            //todo:处理完成投诉，本地标记处理就行，不用调用接口
            ComplaintForm complaintForm = new ComplaintForm();
            if(list != null && !list.isEmpty()){
                OrderForm orderForm = list.get(0);
                complaintForm.setStoreId(orderForm.getStoreId());
                complaintForm.setStoreName(orderForm.getStoreName());
                complaintForm.setEpsId(orderForm.getEpsId());
                complaintForm.setTenantId(orderForm.getTenantId());
            }
            complaintForm.setId(UUID.randomUUID().toString().toLowerCase());
            complaintForm.setCreateBy("999999");
            complaintForm.setCreateTime(new Date());
            BeanUtils.copyProperties(data, complaintForm);
            complaintForm.setStatus(1);
            complaintFormService.save(complaintForm);
            return "success";
        }else{
            return "fail";
        }
    }

    /**
     * @description: 发送消息到mq
     * @param: orderId  订单id
     * @param: expiration 延迟时间 毫秒
     * @return: void
     * @date
    */
    public void sendMessagesToMq(String orderId, Integer expiration){
        BaseMap map = new BaseMap();
        map.put("orderId", orderId);
        //五分钟执行
        rabbitMqClient.sendMessage(MqConstant.MQ_DHB_ORDER_TIME, map, expiration);
    }

    @Override
    public Result selectOrder(DhbSearchModel dhbSearchModel) {
        dhbRequestUtil.getSearchModel(dhbSearchModel);
        JSONObject jsonObject = httpDhbRequestService.selectOrder(dhbSearchModel);
        if(Objects.equals("0",jsonObject.getString("code"))){
            return Result.OK(jsonObject.getJSONObject("data"));
        }
        return Result.error500("查询失败！");
    }

    @Override
    public JSONObject selectUser(DhbUserModel dhbUserModel) {
        dhbUserModel.setSt(System.currentTimeMillis()/1000);
        dhbRequestUtil.getDhbUserModel(dhbUserModel);
        JSONObject jsonObject = httpDhbRequestService.selectUser(dhbUserModel);
        return jsonObject;
    }

    @Override
    public Result sendPickup(DhbPickupModel dhbPickupModel) {
        dhbRequestUtil.getDhbPickupModel(dhbPickupModel);
        JSONObject jsonObject = httpDhbRequestService.sendPickup(dhbPickupModel);
        if(Objects.equals("0",jsonObject.getString("code"))){
            return Result.OK(jsonObject.getString("msg"), jsonObject.getJSONObject("data"));
        }
        return Result.error500(jsonObject.getString("msg"));
    }
}
