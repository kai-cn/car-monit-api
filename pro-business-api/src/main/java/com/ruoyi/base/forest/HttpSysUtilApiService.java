package com.ruoyi.base.forest;

import com.alibaba.fastjson2.JSONObject;
import com.dtflys.forest.annotation.BaseRequest;
import com.dtflys.forest.annotation.JSONBody;
import com.dtflys.forest.annotation.Post;
import com.ruoyi.base.domain.SuspiciousCarVO;


@BaseRequest(baseURL = "#{sysbaseUrl}/manager/suspicious")
public interface HttpSysUtilApiService {

    @Post("/syncSuspiciousCarTask")
    JSONObject syncSuspiciousCarTask(@JSONBody SuspiciousCarVO suspiciousCarVO);


}
