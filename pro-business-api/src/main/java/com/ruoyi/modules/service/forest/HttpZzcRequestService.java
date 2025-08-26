package com.ruoyi.modules.service.forest;

import com.dtflys.forest.annotation.*;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.vo.zzc.FindDifficultLogistics;
import com.ruoyi.modules.vo.zzc.FindDifficultLogisticsResult;

import java.util.List;

/**
 * @Description: 单号宝接口
 * @Author: HuangJun
 * @Date: 2022-08-10 10:16:41
 * @Return
 */
@BaseRequest(baseURL = "#{ret.zzc.baseUrl}")
public interface HttpZzcRequestService {

    /**
     * 29 查询疑难件
     */
    @Post(url = "/api/zzc/findDifficultLogistics")
    Result<List<FindDifficultLogisticsResult>> findDifficultLogistics(@JSONBody FindDifficultLogistics findDifficultLogistics, @Header("d-anno") String anno);
}
