package com.ruoyi.base.domain;

import lombok.Data;

import java.util.List;

@Data
public class CarParaVO {

    /**
     * 车俩列表
     */
    private List<CarVO> carlist;

    //车牌号
    private String carNo;

    // 时间查询
    private String applyTime1;

    private String applyTime2;

    /**
     * 车俩编号数组
     */
    private List<String> carNoList;

}
