package com.ruoyi.modules.config.enums;


import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * 中转仓状态1
 */
@Getter
@AllArgsConstructor
public enum ZzcOrderStatusEnum {
    NOTARRIVED(1, "1", "未到达"),
    EMIT(2, "2", "发出"),
    ABNORMAL(3, "3", "异常"),
    REJECTION(4, "4", "拒收"),
    COMPLETE(5, "5", "完成");

    private final int code;
    private final String codeString;
    private final String info;

}
