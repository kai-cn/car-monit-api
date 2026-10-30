package com.ruoyi.base;

/**
 * @Author: zhukai
 * @Date: 2026/09/15/18:27
 * @Description:
 */
public class Test {
    public static void main(String[] args) {
        String s1 = "Hello";
        String s2 = new String("Hello");
        String s3 = s2.intern();
        System.out.println(s1 == s2); // Line 1
        System.out.println(s1 == s3); // Line 2
    }
}
