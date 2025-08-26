package com.ruoyi.common.utils;

import java.util.stream.Collectors;
import java.util.stream.IntStream;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/5/14 15:06
 * @Return
 */
public class RepeatUtil {

    /**
     * @Description: 重复生成一个字符串
     * @Author HuangJun
     * @Date 2024/5/14 15:15
     * @Return
     */
    public static String repeat(String s, int n) {
        return IntStream.range(0, n)
                .mapToObj(i -> s)
                .collect(Collectors.joining());
    }

    public static void main(String[] args) {
        String mess = "jd_vdccfwrfeppe";
        int len = mess.length();
        if(len % 8 != 0){
            mess += RepeatUtil.repeat("X", 8 - len % 8);
        };

        System.out.println(mess);
    }
}
