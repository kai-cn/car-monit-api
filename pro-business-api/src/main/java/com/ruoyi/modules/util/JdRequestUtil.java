package com.ruoyi.modules.util;

import com.alibaba.fastjson.JSONObject;
import org.apache.http.client.ResponseHandler;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.client.utils.URIBuilder;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.BasicResponseHandler;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;

import java.net.URI;
import java.sql.Timestamp;
import java.text.SimpleDateFormat;
import java.util.*;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/4/15 20:59
 * @Return
 */
public class JdRequestUtil {

    static String jd_cookie = "shshshfpa=3e538ca1-3bf5-7c77-138d-b3a3aed114e8-1612332028; shshshfp=25efebb424105a05855f74dbd9a4ae89; shshshfpx=3e538ca1-3bf5-7c77-138d-b3a3aed114e8-1612332028; ipLoc-djd=19-1601-50258-129167; user-key=3cefed58-461c-4793-82dc-158b485004b9; __jdu=1425616577; unpl=JF8EALBnNSttWEJVBU9XGhYUSFhQW1xYGEcKPTIDBAkIS1UFSVdMQUR7XlVdWBRKEh9vYRRUWFNJUg4bACsSEXteXVdZDEsWC2tXXAQDGhUQRENdUEtUGwI6Xw0BTRNWaGdXUAoMTlJQElFJFxlMW1xeXwtDFQA6ZAdkbVtLZAUaMhsXE09aVFlZDk0nAl9gNWRtWk9QBBkyGiIRex8AAlkKSxIDZioFUV5cTFQCHwQdIhF7Xg; pinId=r9iUM1NMJRe-d2tHs17Tkg; pin=%E6%B5%A6%E5%B0%98%E4%B8%AA%E6%8A%A4; unick=%E6%B5%A6%E5%B0%98%E4%B8%AA%E6%8A%A4; _tp=Z60aaDbPOtXmjniko6dzSQZXGYAgPWuQAbziMstlVGJrmr0za15odDZ61nf0xemV; _pst=%E6%B5%A6%E5%B0%98%E4%B8%AA%E6%8A%A4; PCSYCityID=CN_440000_440100_0; __jdv=76161171|haosou-pinzhuan|t_288551095_haosoupinzhuan|cpc|0a875d61c5fe47d8bc48679132932d23_0_1801ed05524540aba8cd7aea101cdfbe|1713947418447; ceshi3.com=000; 3AB9D23F7A4B3CSS=jdd03IPMSUVTC2ZOBA3ACENKDKN6RW4ABVRXMJBE5ON6LM4MODA7GHFFKM2MNVT4GMB5KMNDNKDCVMW4LUMD2ZQAQLLXRBIAAAAMPCL6I7GIAAAAACZZGFVDKL2VGPYX; shshshfpb=BApXcoA30EepApSKxybKSw6FE2tQVF6UyB1ByJwdj9xJ1Mp7XCYC2; TrackID=1yKa8SnGV2IuAQ-OJvsXPykY2lbp186ZJ_ko0MVOUwlbBjAmw2zvs6zUNZYXGPgugTAq_xL4qjaxfOH-D7eT43RWni_Xdh3BavVaAhIAaDPc; thor=523F36402A583B9237BB87A42521181674EABFA6A4CDC08A21BA245AF8F1C032E7A7118D5C8DE97EF72A715CA8ECD4C481B2461B3EEC159F47F41E61EFBE60432CFF2AEC43C5FA281AC0E36C9B7EB2AF9385CBF47F29C24B133501DBD71DBC0F47F9E98EF72D911CB62600603F316F41EC7C2FA107152A7785202F4159480E52; flash=2_hXPkKDe5f_5NeIIlDrih3qew5zeyKdD9TbaP4nVpllEOO4T2TFt_IwtozNZCIt40yvzszsDm9ylYucD-fTsVoh3yEEkQZcD6OA5d79ZxXTM*; language=zh_CN; __jdc=27966078; __USE_NEW_PAGEFRAME__=true; __USE_NEW_PAGEFRAME_VERSION__=v11; _s_vender_=GLOD7EBCFLYE7HHGI2EBRUSOGRZ7FDQ54EZVHBQHFRDZKUBEWL5YLEWEYCPJIE2ZCN6SUEEZFGLUW63DNZT4YBUDTFC7C7KJFMXBIJGPQHAXYKKRRQ46HSMY5FCX5WVREQLZD56GL7HG3T7UEEFFBE6XFBVWP4B7WJ7E6FAWDYWUHZ6KRVAFHDNDXO6J2Z6HP5GJEW7UXYS5EDVZLFU7KHZAPGBJZBOQ2CINUY75ZYV2ZBO5WOIXINKDTRI52PRSM56YI4OFU53O2ZJGSGP52EHPE32VG65IBQO7VBAQNA5TE67MI3DIYNLNOSYN7LS4WHKOVTEHTZPY7Q5IIMTKPKHMKVO5ZMR4KHSGE7Y; 3AB9D23F7A4B3C9B=IPMSUVTC2ZOBA3ACENKDKN6RW4ABVRXMJBE5ON6LM4MODA7GHFFKM2MNVT4GMB5KMNDNKDCVMW4LUMD2ZQAQLLXRBI; __jda=27966078.1425616577.1712647188.1712647188.1712647190.1; _s_base_=GLOD7EBCFLYE7BEGD2KJNDFMUPLJWYVY7WTVVDNT5BZ42OHICZ3YK6UV75APOY5WUT2VPU6GB75TVVF5JOAB3RMMMINDM7F267GQOPLDLNTVYGNYXCTSTDUFJZIJ6Q2IZTXDZRZ6DCCSM4XWV3ISQ5X3O4XI7AEZE2NGCVKMAQZ7GVUY7INA; _base_=YKH2KDFHMOZBLCUV7NSRBWQUJPBI7JIMU5R3EFJ5UDHJ5LCU7R2NILKK5UJ6GLA2RGYT464UKXAI5KK7PNC5B5UHJ2HVQ4ENFP57OC7USIUMPNEN5NXAA5GU37TUAR77TCNE6YVKRXISV2TTTPMIV5RYA3WDA4AEL7ZLXI2SG4SOQWCP5WPWO6EFS7HEHMRWVKBRVHB33TFD4ARIWYTORVCK2SP2IMM6D4KD6WAZ2VDEFMFIYD32GSZIV5CYGCSCNDLIMKUMBM7UJF2S7464SYZDFHH3ZRU7WA5GKJMYGGXIN62B2M7UBSRP2BADLWCZJKL4WIPDNO6DQO6YMJEQUDNGNUHPRJ5XYSHWDBVHRESKIUXV6DFZJ2W46ZG7UY2R; __jdb=27966078.10.1425616577|1.1712647190";

    public JSONObject httpGet(String type) {
         HttpGet httpGet = null;
        try (CloseableHttpClient httpClient = HttpClients.createDefault()) {
            // 定义请求的参数
            URIBuilder uriBuilder = new URIBuilder(this.getUrl(type));
            //构建get请求参数
            this.getGetParams(type,uriBuilder);
            URI uri = uriBuilder.build();
            httpGet = new HttpGet(uri);
            //构建Header
            this.getGetHeader(type,httpGet);
            ResponseHandler<String> responseHandler = new BasicResponseHandler();
            //设置请求头
            String execute = httpClient.execute(httpGet, responseHandler);
            JSONObject jsonObject = JSONObject.parseObject(execute);
            System.out.println(JSONObject.toJSONString(execute));
            return jsonObject;
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            httpGet.releaseConnection();
        }
        return null;
    }

    public JSONObject httpPost(String type,JSONObject obj) {
        Map<String, Object> params = getPostParams(type,obj);
        String url = this.getUrl(type);
        HttpPost httpPost = null;
        try (CloseableHttpClient httpClient = HttpClients.createDefault()) {
            ResponseHandler<String> responseHandler = new BasicResponseHandler();
            httpPost = new HttpPost(url);
            String jsonString = JSONObject.toJSONString(params);
            System.out.println(jsonString);
            StringEntity requestEntity = new StringEntity(jsonString, "utf-8");
            requestEntity.setContentEncoding("UTF-8");
            httpPost.setEntity(requestEntity);

            //设置请求头
            httpPost.setHeader("content-type","application/json;charset=UTF-8");
            /*------------Start 这里不能省略，否则报异常-----------------*/
            //httpPost.setHeader("dsm-eid",null);
            //httpPost.setHeader("dsm-lang","undefined");
            //httpPost.setHeader("dsm-site","undefined");
            //随便什么字符串都可以
            //httpPost.setHeader("dsm-trace-id","fd5ff8df-71ce-4ee0-9c42-2a12bfc1ff66");

            //不传会报错
            httpPost.setHeader("dsm-platform","pc");
            //京东京麦Cookie 均可以调通，直接获取Cookie即可
            httpPost.setHeader("Cookie", jd_cookie);
            /*------------End 这里不能省略，否则报异常-----------------*/


            String execute = httpClient.execute(httpPost, responseHandler);
            JSONObject jsonObject = JSONObject.parseObject(execute);
            System.out.println(JSONObject.toJSONString(jsonObject));
            return jsonObject;
        } catch (Exception e) {
            e.printStackTrace();
        }finally {
            httpPost.releaseConnection();
        }
        return null;
    }

    /**
     * @Description: 获取post请求参数
     * @Author HuangJun
     * @Date 2024/4/16 15:28
     * @Return
     */
    public void getGetHeader(String type,HttpGet httpGet){
        if(type.equals("kd_100_get_detail")){
            httpGet.setHeader("Cookie","BIDUPSID=CD0CD3F58B7E9E9B937C6FF9577E0632; PSTM=1610800906; BAIDUID=82351877B1D3E628D9FAAE2DC3E89EE1:FG=1; MCITY=-75%3A; H_WISE_SIDS_BFESS=40305_40367_40376_40415_40459_40439_40499_40511_40445_60045_60023_60048_40080; BDUSS=h4OGRrcTZkVkZ6U2R4bVJ5QS1iWnRWNzF1VmdIWHNHY1BnNWZFNmMycTBBRWhtSVFBQUFBJCQAAAAAAAAAAAEAAAAp2a1nwfm6z7DZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALRzIGa0cyBmZU; BDUSS_BFESS=h4OGRrcTZkVkZ6U2R4bVJ5QS1iWnRWNzF1VmdIWHNHY1BnNWZFNmMycTBBRWhtSVFBQUFBJCQAAAAAAAAAAAEAAAAp2a1nwfm6z7DZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALRzIGa0cyBmZU; BAIDUID_BFESS=82351877B1D3E628D9FAAE2DC3E89EE1:FG=1; BA_HECTOR=a4ak2hag242l8h2100ak858lvinqb71j2btpv1t; ZFY=B3Ahk7vRUOCi7MitK9GkT19Z:AWNms2xTS24iX88tpgM:C; H_WISE_SIDS=40305_40367_40376_40415_40459_40499_40511_40445_40080; BDRCVFR[mThyzN3q3CC]=mk3SLVN4HKm; PSINO=6; delPer=0; H_PS_PSSID=40305_40415_40459_40499_40445_40080; BDORZ=FFFB88E999055A3F8A630C64834BD6D0\n" +
                    "Host: alayn.baidu.com\n" +
                    "Referer: https://www.baidu.com/s?ie=utf-8&f=8&rsv_bp=1&rsv_idx=2&tn=57095150_5_oem_dg&wd=%E5%BF%AB%E9%80%92100&rsv_spt=1&oq=%25E5%25BF%25AB%25E9%2580%2592100&rsv_pq=b92e498000302f76&rsv_t=bfb6nIfNfVZOB%2BBwn8MdTGesBXjvgv%2FcklWXzQT6HJZI323fZDv2issxUj5q9D9NlMX1pYpPDIk&rqlang=cn&rsv_enter=0&rsv_dl=tb&rsv_btype=t");
        }
    }

    /**
     * @Description: 获取post请求参数
     * @Author HuangJun
     * @Date 2024/4/16 15:28
     * @Return
     */
    public void getGetParams(String type,URIBuilder uriBuilder){
        if(type.equals("kd_100_get_com")){
            uriBuilder.addParameter("nu","292464621295");
            uriBuilder.addParameter("cb",this.getJsonpCodeStr());
        }
        else if(type.equals("kd_100_get_detail")){
            uriBuilder.addParameter("query_from_srcid","51151");
            uriBuilder.addParameter("tokenV2","R6M8o504VKu/5mGQ1QVnyjj86QLhuspLvb6cEsFbvOxF/ZH/QSR5iiARroZTlMeF");
            uriBuilder.addParameter("appid","4001");
            uriBuilder.addParameter("nu","292464621295");
            uriBuilder.addParameter("com","yuantong");
            uriBuilder.addParameter("qid","4879176651996235000");
            uriBuilder.addParameter("cb",this.getJsonpCodeStr());
        }
    }

    /**
     * @Description: 获取post请求参数
     * @Author HuangJun
     * @Date 2024/4/16 15:28
     * @Return
     */
    public static Map<String, Object> getPostParams(String type,JSONObject data){
        if(type.equals("dsm.order.manage.orderlist.queryOrderPage")){
            Map<String, Object> params = new HashMap<>();
            params.put("source","2000");
            params.put("data",data);
            Map<String, Object> paramters = new HashMap<>();
            paramters.put("request",params);
            return paramters;
        }
        else if(type.equals("dsm.order.manage.orderdetail.getOrderTrack")){
            Map<String, Object> params = new HashMap<>();
            params.put("param",data);
            return params;
        }
        else if(type.equals("dsm.order.manage.orderdetail.submitVenderRemark")){
            //添加备注接口参数：{param: {orderId: "291487503195", level: 0, remark: "-"}}
            Map<String, Object> params = new HashMap<>();
            params.put("param",data);
            return params;
        }
        else if(type.equals("dsm.order.manage.orderlist.batchSubmitVenderRemark")){
            //批量添加备注接口参数：{"param": {"level": 1,"orderIds": ["289766716527"],"remark": "缺货"}}
            Map<String, Object> params = new HashMap<>();
            params.put("param",data);
            return params;
        }
        else if(type.equals("dsm.order.manage.OrderLogisticsReadService.maliciousResellingCheck")){
            //普通发货接口
            //{"request":{"data":[{"orderId":291538681243,"checkType":1,"deliveryCompanyList":[{"deliveryId":"1327","deliveryNums":["4281219978909251"]}]}]}}

            /*Delivery delivery = new Delivery();
            delivery.setOrderId(291538681243L);
            delivery.setCheckType(1);
            Delivery.DeliveryModel deliveryModel = new Delivery.DeliveryModel();
            deliveryModel.setDeliveryId("1327");//物流名称及编码.txt 文件中找
            deliveryModel.setDeliveryNums(Arrays.asList("4281219978909251"));
            delivery.setDeliveryCompanyList(Arrays.asList(deliveryModel));*/

            Map<String, Object> params = new HashMap<>();
            params.put("data",Arrays.asList(data));
            Map<String, Object> paramters = new HashMap<>();
            paramters.put("request",params);
            return paramters;
        } else if(type.equals("dsm.order.manage.orderOutShipService.batchOutShip")){
            //电子面单发货
            //{"request":{"source":"2000","data":[{"venderTaskAddressId":21318561,"deliveryType":203,"deliveryNumber":{"deliveryId":"2170","deliveryName":"邮政快递包裹","packageNum":1,"guaranteeValue":"0","epsOutShip":{"operationType":1,"branchCode":"1100099447061","insureValue":"0"}},"orderIds":[289651098551]}]}}
            Map<String, Object> params = new HashMap<>();
            params.put("source","2000");
            params.put("data",Arrays.asList(data));
            Map<String, Object> paramters = new HashMap<>();
            paramters.put("request",params);
            return paramters;
        }
        else if(type.equals("dsm.order.manage.PhoneVirtualNumberService.getDesensitizationInfo")){
            //{"request":{"source":"2000","data":289766716527}}
            Map<String, Object> params = new HashMap<>();
            params.put("source","2000");
            params.put("data",data.get("orderId"));
            Map<String, Object> paramters = new HashMap<>();
            paramters.put("request",params);
            return paramters;
        }
        else {
            return new HashMap<>();
        }
    }


    /**
     * 获取请求的URL
     * @param type
     * @return
     */
    public String getUrl(String type){
        String url = "";
        if(type.equals("dsm.order.manage.orderlist.queryOrderPage")){
            //获取订单列表
            url = "https://sff.jd.com/api?v=1.0&appId=COCX0HBWR4BA7RDVDBIQ&api=dsm.order.manage.orderlist.queryOrderPage";
        }
        if(type.equals("dsm.order.manage.orderdetail.getOrderTrack")){
            //获取订单物流详情
            url = "https://sff.jd.com/api?v=1.0&appId=COCX0HBWR4BA7RDVDBIQ&api=dsm.order.manage.orderdetail.getOrderTrack";
        }
        else if(type.equals("dsm.order.manage.orderdetail.submitVenderRemark")){
            //设置及修改商家备注
            url = "https://sff.jd.com/api?v=1.0&appId=COCX0HBWR4BA7RDVDBIQ&api=dsm.order.manage.orderdetail.submitVenderRemark";
        }
        else if(type.equals("dsm.order.manage.orderlist.batchSubmitVenderRemark")){
            //批量设置及修改商家备注
            url = "https://sff.jd.com/api?v=1.0&appId=COCX0HBWR4BA7RDVDBIQ&api=dsm.order.manage.orderlist.batchSubmitVenderRemark";
        }
        else if(type.equals("dsm.order.manage.OrderLogisticsReadService.maliciousResellingCheck")){
            //普通发货
            url = "https://sff.jd.com/api?v=1.0&appId=COCX0HBWR4BA7RDVDBIQ&api=dsm.order.manage.OrderLogisticsReadService.maliciousResellingCheck";
        }
        else if(type.equals("dsm.order.manage.orderOutShipService.batchOutShip")){
            //电子面单发货
            url = "https://sff.jd.com/api?v=1.0&appId=COCX0HBWR4BA7RDVDBIQ&api=dsm.order.manage.orderOutShipService.batchOutShip";
        }
        else if(type.equals("dsm.order.manage.PhoneVirtualNumberService.getDesensitizationInfo")){
            //获取隐藏的地址及电话
            url = "https://sff.jd.com/api?v=1.0&appId=COCX0HBWR4BA7RDVDBIQ&api=dsm.order.manage.PhoneVirtualNumberService.getDesensitizationInfo";
        }
        else if(type.equals("kd_100_get_com")){
            //快递100 查询快递单号来源
            url = "https://alayn.baidu.com/express/appdetail/get_com";
        }
        else if(type.equals("kd_100_get_detail")){
            //快递100 查询物流信息
            url = "https://alayn.baidu.com/express/appdetail/get_detail";
        }
        return url;
    }

    //获取JsonpCodeStr
    public String getJsonpCodeStr(){
        Random random = new Random();
        // 生成一个10000到99999之间的随机数
        int randomNumber = 10000 + random.nextInt(90000);
        String jsonpCodeStr = "jsonp_" + System.currentTimeMillis() + "_" + randomNumber;
        return jsonpCodeStr;
    }

    /**
     * 获取当前时间
     */
    public static Timestamp getTimestamp() {
        return Timestamp.valueOf(new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(new Date()));
    }
}
