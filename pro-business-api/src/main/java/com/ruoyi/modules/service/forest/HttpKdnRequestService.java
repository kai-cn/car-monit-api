package com.ruoyi.modules.service.forest;

import com.ruoyi.modules.vo.kdn.KdnResponseModel;
import com.dtflys.forest.annotation.*;

/**
 * @Description: 快递鸟接口
 * @Author: HuangJun
 * @Date: 2022-08-10 10:16:41
 * @Return
 */
@BaseRequest(baseURL = "#{ret.kdn.baseUrl}")
public interface HttpKdnRequestService {
    /**
     * 查询接口
     * @return
     */
    @Post(url = "/Ebusiness/EbusinessOrderHandle.aspx",
            contentType = "application/x-www-form-urlencoded;charset=utf-8")
    KdnResponseModel getKdnOrderTrack(@Body("RequestData") String RequestData,
                                      @Body("DataType") String DataType,
                                      @Body("EBusinessID") String EBusinessID,
                                      @Body("DataSign") String DataSign,
                                      @Body("RequestType") String RequestType
    );

}
