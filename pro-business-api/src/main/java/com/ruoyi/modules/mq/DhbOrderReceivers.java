package com.ruoyi.modules.mq;

import com.alibaba.fastjson.JSONArray;
import com.rabbitmq.client.Channel;
import com.ruoyi.modules.service.*;
import com.ruoyi.rabbitmq.config.MqConstant;
import com.ruoyi.rabbitmq.config.annotation.RabbitComponent;
import com.ruoyi.rabbitmq.config.base.BaseMap;
import com.ruoyi.rabbitmq.core.BaseRabbiMqHandler;
import com.ruoyi.rabbitmq.listenter.MqListener;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitHandler;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.handler.annotation.Header;

import java.util.Objects;

/**
 * RabbitMq接受者
 * （@RabbitListener声明类上，一个类只能监听一个队列）
 */
@Slf4j
@RabbitListener(queues = MqConstant.MQ_DHB_ORDER_TIME)
@RabbitComponent(value = "dhbOrderReceivers")
public class DhbOrderReceivers extends BaseRabbiMqHandler<BaseMap> {

    @Autowired
    private IDhbApiService dhbApiService;

    @RabbitHandler
    public void onMessage(BaseMap baseMap, Channel channel, @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) {
        super.onMessage(baseMap, deliveryTag, channel, new MqListener<BaseMap>() {
            @Override
            public void handler(BaseMap map, Channel channel) {
                //业务处理
                String orderId = map.get("orderId");
                if(orderId != null){
                    dhbApiService.syngOrderStatus(orderId);
                }
            }
        });
    }
}
