package com.ruoyi.modules.controller.api;

import com.alibaba.fastjson.JSONObject;
import com.ruoyi.common.config.annotation.ValidHeader;
import com.ruoyi.common.config.base.Result;

import com.github.xiaoymin.knife4j.annotations.ApiOperationSupport;
import com.ruoyi.common.util.MD5Example;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiImplicitParam;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.apache.http.Header;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.utils.URIBuilder;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.impl.cookie.BasicClientCookie;
import org.apache.http.message.BasicHeader;
import org.apache.http.util.EntityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.io.UnsupportedEncodingException;
import java.net.HttpCookie;
import java.net.URLEncoder;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import com.ruoyi.common.util.RedisUtil;
/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/6/28 9:03
 * @Return
 */
@Slf4j
@Api(tags = {"淘宝相关接口"})
@RestController
@RequestMapping(value = "/api/taobao")
public class TaoBaoTestController {

    @Autowired
    private RedisUtil redisUtil;

    static final String PREFIX_USER_COOKIE  = "prefix_user_cookie:api";

    @GetMapping(value = "/getPCode")
    @ApiOperation(value = "查询淘宝取件码", notes = "查询淘宝取件码")
    @ApiOperationSupport(order = 1)
    @ApiImplicitParam(name = "d-cookie", dataType = "string", paramType = "header")
    @ValidHeader(value = {"d-cookie"}, message = "Header:[d-cookie] 不能为空！")
    public Result<?> getPCode(@RequestParam("orderId") String orderId,
                              @RequestHeader("d-cookie") String cookie,
                              @RequestParam("isSetCookie") Boolean isSetCookie
    ) throws UnsupportedEncodingException {
        if(isSetCookie){
            redisUtil.set(PREFIX_USER_COOKIE, cookie);
        }
        List<HttpCookie> cookies = HttpCookie.parse(cookie);
        //https://h5api.m.taobao.com/h5/mtop.taobao.logistics.detailorlist.query/1.0/?jsv=2.6.1&appKey=12574478&t=1719543916910&sign=62a7e766fad068e6d59485c0923f7079&api=mtop.taobao.logistics.detailorlist.query&v=1.0&needLogin=true&LoginRequest=true&type=jsonp&dataType=jsonp&timeout=20000&ttid=%23t%23ip%23%23_h5_web_default&preventFallback=true&callback=mtopjsonp2&data=%7B%22orderId%22%3A%222206738165522022974%22%7D
        //Path=/;Domain=taobao.com;Max-Age=0;SameSite=None;Secure
        if(redisUtil.hasKey(PREFIX_USER_COOKIE)){
            cookie = (String) redisUtil.get(PREFIX_USER_COOKIE);
        }
        Map<String, String> cookieMap = extractCookies(cookie);
        String token = cookieMap.get("_m_h5_tk");
        token = token.substring(0,token.indexOf("_"));
        System.out.println("token====" + token);
        String _appKey = "12574478";
        String _t = String.valueOf(System.currentTimeMillis());
        System.out.println(_t);
        Map<String, String> map = Collections.singletonMap("orderId",orderId);
        String _data = URLEncoder.encode(JSONObject.toJSONString(map),"UTF-8");
        String str = token + "&" + _t + "&" + _appKey + "&" + JSONObject.toJSONString(map);
        String _sign = MD5Example.toMD5(str);
        System.out.println(_sign);
        HttpGet httpGet = null;
        try (CloseableHttpClient httpClient = HttpClients.createDefault()){
            // 定义请求的参数
            String url = "https://h5api.m.taobao.com/h5/mtop.taobao.logistics.detailorlist.query/1.0/";
            URIBuilder uriBuilder = new URIBuilder(url);
            //构建get请求参数
            this.getGetParams(_appKey,_t,_data,_sign,uriBuilder);
            httpGet = new HttpGet(uriBuilder.build());
            String refererUrl =httpGet.getURI().getScheme() + ":" + httpGet.getURI().getSchemeSpecificPart();
            //构建Header
            this.getGetHeader(cookieMap,refererUrl,httpGet);

            Header[] allHeaders = httpGet.getAllHeaders();
            for (Header header : allHeaders) {
                System.out.println("GET|" + header.getName() + ": " + header.getValue());
            }

            //设置请求头
            CloseableHttpResponse response = httpClient.execute(httpGet);
            String entity = EntityUtils.toString(response.getEntity());
            if(entity.indexOf("令牌过期") > -1 || entity.indexOf("非法请求") > -1){
                System.out.println("令牌过期>>>>>>>>>>>>>开始");
                Header[] headers = response.getHeaders("Set-Cookie");
                for (Header header : headers) {
                    System.out.println(header.getName() + ": " + header.getValue());
                    String[] split = header.getValue().split(";")[0].split("=");
                    cookieMap.put(split[0],split[1]);
                }
                System.out.println("令牌过期>>>>>>>>>>>>>结束");
                System.out.println(JSONObject.toJSONString(cookieMap));
                return this.getPCode2(orderId,cookieMap);
            }

            System.out.println("entity>>>>>>>>>" + entity);
            Header[] headers = response.getAllHeaders();
            for (Header header : headers) {
                System.out.println(header.getName() + ": " + header.getValue());
            }
            return Result.OK(entity);
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            httpGet.releaseConnection();
        }

        return Result.error500("查询失败！");
    }


    public Result<?> getPCode2(String orderId, Map<String, String> cookieMap) throws UnsupportedEncodingException {
        String token = cookieMap.get("_m_h5_tk");
        token = token.substring(0,token.indexOf("_"));
        String _appKey = "12574478";
        String _t = String.valueOf(System.currentTimeMillis());
        System.out.println(_t);
        Map<String, String> map = Collections.singletonMap("orderId",orderId);
        String _data = URLEncoder.encode(JSONObject.toJSONString(map),"UTF-8");
        String str = token + "&" + _t + "&" + _appKey + "&" + JSONObject.toJSONString(map);
        String _sign = MD5Example.toMD5(str);
        System.out.println(_sign);
        HttpGet httpGet = null;
        try (CloseableHttpClient httpClient = HttpClients.createDefault()){
            // 定义请求的参数
            String url = "https://h5api.m.taobao.com/h5/mtop.taobao.logistics.detailorlist.query/1.0/";
            URIBuilder uriBuilder = new URIBuilder(url);
            //构建get请求参数
            this.getGetParams(_appKey,_t,_data,_sign,uriBuilder);
            httpGet = new HttpGet(uriBuilder.build());
            String refererUrl =httpGet.getURI().getScheme() + ":" + httpGet.getURI().getSchemeSpecificPart();
            //构建Header
            this.getGetHeader(cookieMap,refererUrl,httpGet);

            Header[] allHeaders = httpGet.getAllHeaders();
            for (Header header : allHeaders) {
                System.out.println("GET|" + header.getName() + ": " + header.getValue());
            }

            //设置请求头
            CloseableHttpResponse response = httpClient.execute(httpGet);
            String entity = EntityUtils.toString(response.getEntity());
            System.out.println("entity>>>>>>>>>" + entity);
            Header[] headers = response.getAllHeaders();
            for (Header header : headers) {
                System.out.println(header.getName() + ": " + header.getValue());
            }
            return Result.OK(entity);
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            httpGet.releaseConnection();
        }

        return Result.error500("查询失败！");
    }

    public static Map<String, String> extractCookies(String cookieHeader) {
        Map<String, String> cookies = new HashMap<>();
        if (cookieHeader == null || cookieHeader.isEmpty()) {
            return cookies;
        }

        // 正则表达式，匹配cookie的键值对
        String regex = "(?:^|;)\\s*([^=]+)=([^;]*?)(?=;|$)";
        Pattern pattern = Pattern.compile(regex);
        Matcher matcher = pattern.matcher(cookieHeader);

        while (matcher.find()) {
            cookies.put(matcher.group(1), matcher.group(2));
        }

        return cookies;
    }

    /**
     * @Description: 获取post请求参数
     * @Author HuangJun
     * @Date 2024/4/16 15:28
     * @Return
     */
    private void getGetParams(String _appKey, String _t, String _data,String _sign, URIBuilder uriBuilder) throws UnsupportedEncodingException {
        uriBuilder.setParameter("jsv","2.6.1");
        uriBuilder.setParameter("appKey",_appKey);
        uriBuilder.setParameter("t",_t);
        uriBuilder.setParameter("sign",_sign);
        uriBuilder.setParameter("api","mtop.taobao.logistics.detailorlist.query");
        uriBuilder.setParameter("v","1.0");
        uriBuilder.setParameter("needLogin", "true");
        uriBuilder.setParameter("LoginRequest","true");
        uriBuilder.setParameter("type","jsonp");
        uriBuilder.setParameter("dataType","jsonp");
        uriBuilder.setParameter("timeout","20000");
        uriBuilder.setParameter("ttid","%23t%23ip%23%23_h5_web_default");
        uriBuilder.setParameter("preventFallback","true");
        uriBuilder.setParameter("callback","mtopjsonp2");
        uriBuilder.setParameter("data",_data);
    }

    /**
     * @Description: 获取post请求参数
     * @Author HuangJun
     * @Date 2024/4/16 15:28
     * @Return
     */
    public void getGetHeader(Map<String,String> cookieMap ,String refererUrl,HttpGet httpGet){
        httpGet.setHeader("host","h5api.m.taobao.com");
        httpGet.setHeader("origin","https://h5api.m.taobao.com");
        httpGet.setHeader("referer",refererUrl);
        httpGet.setHeader("accept-encoding","gzip, deflate, br");
        httpGet.setHeader("accept-language","zh-CN,zh;q=0.9");
        httpGet.setHeader("user-agent","Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36");
        httpGet.setHeader("accept","*/*");
        httpGet.setHeader("sec-fetch-site","same-site");
        httpGet.setHeader("sec-fetch-mode","cors");
        httpGet.setHeader("sec-fetch-dest","script");
        httpGet.setHeader("content-type","application/json;charset=UTF-8");

        for(String key:cookieMap.keySet()){//keySet获取map集合key的集合 然后在遍历key即可
            String value = cookieMap.get(key).toString();//
            BasicClientCookie clientCookie = new BasicClientCookie(key, value);
            clientCookie.setDomain("taobao.com");
            clientCookie.setPath("/");
            // 添加cookie到请求对象
            httpGet.addHeader(new BasicHeader("Cookie", clientCookie.getName() + "=" + clientCookie.getValue()));
        }

        /*String[] cookies = _cookie.split(";");
        for (String cookie:cookies) {
            String[] split = cookie.split("=");
            if(split.length == 1){
                BasicClientCookie clientCookie = new BasicClientCookie(split[0], "");
                clientCookie.setDomain("taobao.com");
                clientCookie.setPath("/");
                // 添加cookie到请求对象
                httpGet.addHeader(new BasicHeader("Cookie", clientCookie.getName() + "=" + clientCookie.getValue()));
            }else if(split.length == 2){
                BasicClientCookie clientCookie = new BasicClientCookie(split[0], split[1]);
                clientCookie.setDomain("taobao.com");
                clientCookie.setPath("/");
                // 添加cookie到请求对象
                httpGet.addHeader(new BasicHeader("Cookie", clientCookie.getName() + "=" + clientCookie.getValue()));
            }
        }*/
        //httpGet.setHeader("cookie",_cookie);

    }
}
