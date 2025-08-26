package com.ruoyi.modules.config.enums;


import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * 中转仓状态1
 */
@Getter
@AllArgsConstructor
public enum ZzcStatusEnum {
    NOTARRIVED(1, "1","未到仓库"),
    ARRIVED(2, "2", "已到仓库"),
    RETURN(3, "3", "订单退货"),
    FORWARDED(4, "4", "已转运");

    private final int code;
    private final String codeString;
    private final String info;

}
