package com.ruoyi.modules.mq;

import com.alibaba.fastjson.JSONArray;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ruoyi.modules.service.ICategoryPointsInfoService;
import com.ruoyi.modules.service.IEcGoodsInfoService;
import com.ruoyi.modules.service.IEcJdOrderInfoService;
import com.ruoyi.modules.service.IEcOrderGoodsService;
import com.ruoyi.modules.vo.orders.OrderInfoVO;
import com.ruoyi.modules.vo.orders.OrderItems;
import com.rabbitmq.client.Channel;

import com.ruoyi.common.util.DateUtils;
import com.ruoyi.common.util.StringUtils;
import com.ruoyi.modules.entity.*;
import com.ruoyi.rabbitmq.config.MqConstant;
import com.ruoyi.rabbitmq.config.annotation.RabbitComponent;
import com.ruoyi.rabbitmq.config.base.BaseMap;
import com.ruoyi.rabbitmq.core.BaseRabbiMqHandler;
import com.ruoyi.rabbitmq.listenter.MqListener;
import lombok.extern.slf4j.Slf4j;
import ma.glasnost.orika.MapperFacade;
import org.apache.commons.collections.CollectionUtils;
import org.springframework.amqp.rabbit.annotation.RabbitHandler;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.handler.annotation.Header;

import java.util.*;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * RabbitMq接受者
 * （@RabbitListener声明类上，一个类只能监听一个队列）
 */
@Slf4j
@RabbitListener(queues = MqConstant.MQ_ORDER)
@RabbitComponent(value = "jdOrderReceivers")
public class JdOrderReceivers extends BaseRabbiMqHandler<BaseMap> {

    @Autowired
    private IEcJdOrderInfoService jdOrderInfoService;
    @Autowired
    private IEcOrderGoodsService orderGoodsService;
    @Autowired
    private IEcGoodsInfoService goodsInfoService;
    @Autowired
    private ICategoryPointsInfoService categoryPointsInfoService;
    @Autowired
    private MapperFacade mapperFacade;

    @RabbitHandler
    public void onMessage(BaseMap baseMap, Channel channel, @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) {
        super.onMessage(baseMap, deliveryTag, channel, new MqListener<BaseMap>() {
            @Override
            public void handler(BaseMap map, Channel channel) {
                //业务处理
                String userId = String.valueOf(map.getLong("userId") != null ? map.getLong("userId") : 999999L);
                Long tenantId = map.containsKey("tenantId")? map.getLong("tenantId") : null;
                JSONArray results = map.get("orderInfoList");
                if(results != null){
                    List<OrderInfoVO> orderInfoList = results.toJavaList(OrderInfoVO.class);
                    List<String> orderIds = orderInfoList.stream().map(OrderInfoVO::getOrderId).collect(Collectors.toList());
                    //这个可能为null
                    List<EcJdOrderInfo> orderInfos = jdOrderInfoService.getJdOrderInfoList(orderIds);
                    Map<String, EcJdOrderInfo> orderInfoMap = new HashMap<>(1);
                    orderInfoMap.put("dsuiahdnjaidbkjadjldsjalmda",null);
                    if(CollectionUtils.isNotEmpty(orderInfos)){
                        orderInfoMap = orderInfos.stream().collect(Collectors.toMap(item -> item.getOrderId(), a -> a, (k1, k2) -> k1));
                    }
                    //获取店铺id集合
                    List<String> shopIds = orderInfoList.stream().map(OrderInfoVO::getShopId).distinct().collect(Collectors.toList());
                    //获取店铺信息
                    List<ShopInfo> shopInfoList = goodsInfoService.getShopInfoList(shopIds);
                    Map<String,ShopInfo> shopMap = shopInfoList.stream().collect(Collectors.toMap(ShopInfo::getShopId, Function.identity(), (key1, key2) -> key2));

                    //存新增的数据
                    List<EcJdOrderInfo> addJdOrderInfos = new ArrayList<>();
                    //存修改的数据
                    List<EcJdOrderInfo> updateJdOrderInfos = new ArrayList<>();
                    //存商品数据
                    List<OrderItems> orderItems = new ArrayList<>();
                    List<EcOrderGoods> orderGoodss = new ArrayList<>();
                    for (OrderInfoVO orderInfoVO :orderInfoList) {
                        EcJdOrderInfo newJdOrderInfo = mapperFacade.map(orderInfoVO, EcJdOrderInfo.class);
                        //商品信息存入集合统一处理
                        List<OrderItems> goodsList = newJdOrderInfo.getOrderItems().stream()
                            .peek(item -> {
                                item.setPlatformId("5");
                                item.setShopId(orderInfoVO.getShopId());
                                item.setOrderId(orderInfoVO.getOrderId());
                                if(shopMap.containsKey(orderInfoVO.getShopId())){
                                    item.setShopName(shopMap.get(orderInfoVO.getShopId()).getShopName());
                                }
                                if(item.getWareInfo() != null && StringUtils.isNotEmpty(item.getWareInfo().getProductId())){
                                    item.setProductId(item.getWareInfo().getProductId());
                                    item.setProductName(item.getWareInfo().getProductName());
                                }
                            }).collect(Collectors.toList());
                        //将商品数据抽离存储
                        orderItems.addAll(goodsList);

                        if(shopMap.containsKey(orderInfoVO.getShopId())){
                            newJdOrderInfo.setShopName(shopMap.get(orderInfoVO.getShopId()).getShopName());
                            newJdOrderInfo.setMerchantType(shopMap.get(orderInfoVO.getShopId()).getMerchantType());
                        }

                        //已存在 -- 判断是否需要修改
                        if(orderInfoMap.containsKey(newJdOrderInfo.getOrderId())){
                            EcJdOrderInfo oldJdOrderInfo = orderInfoMap.get(newJdOrderInfo.getOrderId());
                            //两个对象中存在内容不相等
                            if(!newJdOrderInfo.pEquals(oldJdOrderInfo)){
                                oldJdOrderInfo.setOrderRemark(newJdOrderInfo.getOrderRemark());
                                oldJdOrderInfo.setOrderCompleteTime(newJdOrderInfo.getOrderCompleteTime());
                                oldJdOrderInfo.setPaymentConfirmTime(newJdOrderInfo.getPaymentConfirmTime());
                                oldJdOrderInfo.setOrderStatusVo(newJdOrderInfo.getOrderStatusVo());
                                oldJdOrderInfo.setUpdateBy(userId);
                                oldJdOrderInfo.setTenantId(tenantId);
                                oldJdOrderInfo.setUpdateTime(DateUtils.getTimestamp());
                                updateJdOrderInfos.add(oldJdOrderInfo);
                            }
                        }else{
                            List<EcOrderGoods> ecOrderGoods = mapperFacade.mapAsList(goodsList, EcOrderGoods.class);
                            ecOrderGoods.stream().forEach(item -> {
                                item.setShopId(newJdOrderInfo.getShopId());
                                item.setShopName(newJdOrderInfo.getShopName());
                            });

                            orderGoodss.addAll(ecOrderGoods);
                            //未存在 -- 新增
                            newJdOrderInfo.setCreateBy(userId);
                            newJdOrderInfo.setTenantId(tenantId);
                            newJdOrderInfo.setCreateTime(DateUtils.getTimestamp());
                            addJdOrderInfos.add(newJdOrderInfo);
                        }
                    }
                    //新增或修改订单数据
                    if(addJdOrderInfos != null && !addJdOrderInfos.isEmpty()){
                        jdOrderInfoService.saveBatch(addJdOrderInfos);
                        //新增的时候同时新增订单商品信息
                        List<EcOrderGoods> orderGoodsList = orderGoodss.stream()
                                .peek(item -> {
                                    item.setTenantId(tenantId)
                                            .setId(StringUtils.getUUID())
                                            .setDelFlag(0)
                                            .setCreateBy(userId)
                                            .setCreateTime(DateUtils.getTimestamp())
                                            .setUpdateBy(userId)
                                            .setUpdateTime(DateUtils.getTimestamp());
                                }).collect(Collectors.toList());
                        orderGoodsService.saveBatch(orderGoodsList);
                    }
                    if(updateJdOrderInfos != null && !updateJdOrderInfos.isEmpty()){
                        jdOrderInfoService.updateBatchById(updateJdOrderInfos);
                    }
                    //多线程处理商品数据
                    orderItems.parallelStream().forEach(item -> this.saveGoodsInfo(item,shopMap,userId,tenantId));
                }
            }

            /**
             * @Description: ec_goods_info 商品信息处理
             * @Author HuangJun
             * @Date 2024/9/3 15:02
             * @Return
             */
            public void saveGoodsInfo(OrderItems goods, Map<String,ShopInfo> shopMap, String userId,Long tenantId){
                if(goods.getWareInfo() != null && StringUtils.isNotEmpty(goods.getWareInfo().getProductId())){
                    List<EcGoodsInfo> list = goodsInfoService.list(
                            new LambdaQueryWrapper<EcGoodsInfo>().eq(EcGoodsInfo::getStoreId,goods.getShopId())
                                    .eq(EcGoodsInfo::getGoodsNo,goods.getWareInfo().getProductId())
                    );

                    if(list == null || list.isEmpty()){
                        String categoryId = goods.getCategoryId();
                        EcGoodsInfo goodsInfo = new EcGoodsInfo();
                        goodsInfo.setOutsideSource("5")
                        .setStoreId(goods.getShopId())
                        .setStoreName(goods.getShopName())
                        .setGoodsName(goods.getProductName())
                        .setGoodsNo(goods.getProductId())
                        .setItemNo(goods.getItemId())
                        .setJdMoney(goods.getJdPrice())
                        .setGoodStatus("上架")
                        .setGoodsCategory(categoryId)
                        .setPicUrl(goods.getImgUrl())
                        .setTenantId(tenantId)
                        .setId(StringUtils.getUUID())
                        .setDelFlag(0)
                        .setCreateBy(userId)
                        .setCreateTime(DateUtils.getTimestamp())
                        .setUpdateBy(userId)
                        .setUpdateTime(DateUtils.getTimestamp());

                        String merchantType = "";
                        if(shopMap.containsKey(goods.getShopId())){
                            merchantType = shopMap.get(goods.getShopId()).getMerchantType();
                        }
                        if(StringUtils.isNotEmpty(categoryId) && StringUtils.isNotEmpty(merchantType)){
                            List<CategoryPointsInfo> categoryPointsInfoList = categoryPointsInfoService.selectCategoryPointsInfoList(
                                    new CategoryPointsInfo().setCategoryId(categoryId).setStoreType(merchantType));
                            if(CollectionUtils.isNotEmpty(categoryPointsInfoList)){
                                CategoryPointsInfo categoryPointsInfo = categoryPointsInfoList.get(0);
                                goodsInfo.setOneCategoryName(categoryPointsInfo.getOneCategoryName());
                                goodsInfo.setTwoCategoryName(categoryPointsInfo.getTwoCategoryName());
                                goodsInfo.setThreeCategoryName(categoryPointsInfo.getThreeCategoryName());
                                goodsInfo.setFourCategoryName("--");
                            }
                        }
                        goodsInfoService.save(goodsInfo);
                    }
                }
            }
        });
    }
}
