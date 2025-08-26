package com.ruoyi.common.utils;

import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;
import java.nio.charset.Charset;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/4/19 11:41
 * @Return
 */
public class MD5Example {

    public static String toMD5(String originalString) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            md.update(originalString.getBytes());
            byte[] digest = md.digest();
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            e.printStackTrace();
            return null;
        }
    }

    public static void main(String[] args) throws UnsupportedEncodingException {
        String data = "{\"ShipperCode\": \"STO\",\"LogisticCode\": \"773279402851605\"}";
        String key = "4597fcc9-e48b-4d40-832a-b795cc3338bc";

        String originalString = data + key;
        String md5Hash = toMD5(originalString);
        System.out.println("MD5 Hash: " + md5Hash);

        byte[] bytes = md5Hash.getBytes(Charset.forName("UTF-8"));
        String encodedString = Base64.getEncoder().encodeToString(bytes);
        //String encodedString = Base64.getEncoder().encodeToString(originalString.getBytes());
        System.out.println("Encoded String: " + encodedString);

        String encodedString2 = URLEncoder.encode(encodedString, "UTF-8");
        //String decodedString2 = Base64.getUrlEncoder().encodeToString(encodedString.getBytes());
        System.out.println("Decoded string: " + encodedString2);

    }
}
