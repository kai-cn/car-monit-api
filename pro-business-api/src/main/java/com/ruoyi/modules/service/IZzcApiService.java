package com.ruoyi.modules.service;

import com.ruoyi.modules.vo.zzc.ZzcOrderInfoCallBack;

/**
 * @Description: 京东京麦接口
 * @Author: ret-boot
 * @Date:   2024-04-28
 * @Version: V1.0
 */
public interface IZzcApiService {

    /**
     * 中转仓回调接口
     */
    String callBackByZzcOrder(ZzcOrderInfoCallBack zzcOrderInfoCallBack);
}
