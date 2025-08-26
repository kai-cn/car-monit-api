package com.ruoyi.common.utils;

import org.apache.commons.codec.binary.Base64;

import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

/**
 * @Description: 等价前端CryptoJS加密
 * @Author HuangJun
 * @Date 2024/5/15 10:14
 * @Return
 */
public class CryptoJSTools {
    private static final String key = "#1*x3zp_"; // 注意：密钥应该足够长且随机

    public static String encryptDES(String message) throws Exception {
        int len = message.length();
        if(len % 8 != 0){
            message += RepeatUtil.repeat(" ", 8 - len % 8);
        };
        SecretKeySpec secretKeySpec = new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), "DES");
        Cipher cipher = Cipher.getInstance("DES/ECB/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, secretKeySpec);

        byte[] encryptedBytes = cipher.doFinal(message.getBytes(StandardCharsets.UTF_8));
        StringBuffer sb = new StringBuffer();
        for (byte item : encryptedBytes) {
            sb.append(Integer.toHexString((item & 0xFF) | 0x100), 1, 3);
        }
        String encrypted = Base64.encodeBase64String(sb.toString().toUpperCase().getBytes(StandardCharsets.UTF_8));
        System.out.println("encrypted===" + encrypted);
        return encrypted;
    }
    //https://api.m.jd.com/client.action?functionId=halleyOrderDetail&appid=customerAssistant&clientVersion=20230720&lang=zh_CN&body=%7B%22skuId%22%3A%220%22%2C%22customer%22%3A%22NkMyMTc2Q0JENDYxQTUzQkZBRTlDQ0U4RDg4MjMwRjA%3D%22%2C%22orderId%22%3A%22293378411369%22%2C%22params%22%3A%7B%22appid%22%3A%22im.customer%22%2C%22BPOPmpin%22%3A%22%22%2C%22BPOPvid%22%3A%22%22%2C%22BPOPcustomer%22%3A%22%22%2C%22BPOPstoreId%22%3A%22%22%7D%2C%22encryptNew%22%3A%22true%22%2C%22authType%22%3A4%7D
    public static void main(String[] args) {
        try {
            CryptoJSTools.encryptDES("jd_52c00cd62db8c");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
