package com.ruoyi.modules.vo.jd.query;

import lombok.Data;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/6/21 9:04
 * @Return
 */
@Data
public class CategoryQueryParamModel {

    private AccessContext accessContext = new AccessContext();

    private CategoryQueryParam categoryQueryParam = new CategoryQueryParam();


    @Data
    public static class AccessContext {
        private String source = "web";
    }

    @Data
    public static class CategoryQueryParam {
        private Long categoryId = 0L;
        private int catState = 1;
        private boolean zeroYuanTrialOperation = false;
    }
}
