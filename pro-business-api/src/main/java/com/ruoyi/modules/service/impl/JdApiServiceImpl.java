package com.ruoyi.modules.service.impl;

import com.alibaba.fastjson.JSONArray;
import com.ruoyi.modules.service.IJdApiService;
import com.ruoyi.modules.service.forest.HttpJdRequestService;
import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import com.alibaba.fastjson.TypeReference;
import com.ruoyi.modules.config.enums.JdApiFunctionEnum;
import com.ruoyi.modules.mapper.JdCategoryMapper;
import com.ruoyi.modules.util.JdRequestUtil;
import com.ruoyi.modules.vo.jd.ChildCategory;
import com.ruoyi.modules.vo.jd.JdApiRequest;
import com.ruoyi.modules.vo.jd.query.CategoryQueryParamModel;
import lombok.extern.slf4j.Slf4j;
import org.apache.ibatis.session.ExecutorType;
import org.apache.ibatis.session.SqlSession;
import org.mybatis.spring.SqlSessionTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.*;
import java.util.stream.Collectors;

/**
 * @Description: 京东京麦接口
 * @Author: ret-boot
 * @Date:   2024-04-28
 * @Version: V1.0
 */
@Slf4j
@Service
public class JdApiServiceImpl implements IJdApiService {
    @Resource
    private HttpJdRequestService jdRequestService;
    @Autowired
    private SqlSessionTemplate sqlSessionTemplate;

    @Override
    public JSONObject commonApiRequest(String api, JSONObject jsonObject,String cookie) {

        List<String> skuids = Arrays.asList(
                "10090524642542", "10089480541115", "10092813717336", "10094597786214", "10099751883064", "10099911196651",
                "10091545366642", "10090509306851", "10089948453002", "10091307822785", "10091116833564", "10091545182932",
                "10091246688373", "10091518571630", "10090216627509", "10086982278000", "10090752563145", "10088698791495",
                "10088597296974", "10088597296981", "10091307816154", "10088698791498", "10086974189632", "10088730048732",
                "10086974189634", "10091315085021", "10090216737816", "10090828729886", "10090243521389", "10091160961795",
                "10092739427309", "10094704376291", "10090322249863", "10100026477626", "10090098929190", "10090818626449",
                "10088533125067", "10090047471396", "10089909794430", "10091616556507", "10089477985360", "10092798559993",
                "10088698791498", "10089896440432", "10100706876149", "10087113416314", "10091455203287", "10091616556504",
                "10090836648302", "10099785923281", "10091510648780", "10091318006826", "10090736069454", "10090736069454",
                "10091411456996", "10099785923279", "10088726486294", "10088553302380", "10088443554238", "10088555092755",
                "10091116911241", "10092739427305", "10088597296975", "10088088256605", "10088726486286", "10090736419995",
                "10093016302448", "10088597296986", "10089463042793", "10090097282344", "10093042358250", "10093047464766",
                "10099748646606", "10091410493741", "10090098929192", "10099785923279", "10088421000893", "10091410745533",
                "10091551358352", "10090526332683", "10094588258822", "10090529493477", "10087112641592", "10088555092755",
                "10091160546091", "10089351185266", "10090216737816", "10091149936967", "10091400887401", "10093194548085",
                "10086974189633", "10099911903708", "10091439453929", "10090528710189", "10092810732231",
                "10090309625880", "10088552685857", "10090530997007", "10091218421003", "10092739427308");

        for (String skuid:skuids) {
            try {
                Thread.sleep(1000);
                jsonObject.getJSONObject("wareListQuery").put("skuId",skuid);
                Map<String, Object> params = this.getPostParams(api,jsonObject);
                JSONObject json = jdRequestService.jdPostRequest(new JdApiRequest(api,"JOLCHU4FPZVMUIHUK9MQ"), params, cookie);
                System.out.println(json.getString("msg"));
                if("200".equals(json.getString("code"))){
                    JSONArray jsonArray = json.getJSONObject("data").getJSONArray("data");
                    if(jsonArray.size() > 0){
                        JSONObject obj = (JSONObject)jsonArray.get(0);
                        System.out.println("测试循环查询商品编号 》》》skuId:"+ skuid + " productId:" + obj.getLongValue("productId"));
                    }
                }
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
        return jsonObject;
    }

    @Override
    public boolean syncChildCategory(String api, String cookie) {
        CategoryQueryParamModel paramModel = new CategoryQueryParamModel();
        Map<String, Object> params = JSON.parseObject(JSON.toJSONString(paramModel), new TypeReference<Map<String, Object>>(){});
        JdApiRequest jdApiRequest = new JdApiRequest(api, "JOLCHU4FPZVMUIHUK9MQ");
        JSONObject object = jdRequestService.jdPostRequest(jdApiRequest, params, cookie);
        if(object !=null && Objects.equals("200",object.getString("code"))){
            ChildCategory childCategory = JSONObject.toJavaObject(object.getJSONObject("data"), ChildCategory.class);
            List<ChildCategory> categoryList = new ArrayList<>();
            if(childCategory.getLevel() == 0){
                List<ChildCategory> collect = childCategory.getChild().stream().peek(item -> {
                    item.setOneCategoryId(item.getId());
                    item.setOneCategoryName(item.getName());
                }).collect(Collectors.toList());
                categoryList.addAll(collect);
                this.getChildCategory(categoryList,jdApiRequest,paramModel,cookie);
                System.out.println("这是一个阶段方法");
                java.sql.Timestamp curDate = JdRequestUtil.getTimestamp();
                //获取sql会话
                SqlSession session = sqlSessionTemplate.getSqlSessionFactory().openSession(ExecutorType.BATCH, false);
                try{
                    if (categoryList != null && !categoryList.isEmpty()) {
                        JdCategoryMapper categoryMapper = session.getMapper(JdCategoryMapper.class);
                        int batchCount = 3000;
                        int i = 0;
                        for (ChildCategory category : categoryList) {
                            i++;
                            log.info("categoryList index：{}",i);
                            category.setCreateTime(curDate);
                            categoryMapper.insertCategoryInfo(category);
                            boolean isTrue = i != 0 && i % batchCount == 0;
                            if (isTrue || i == categoryList.size()) {
                                session.commit();
                                session.clearCache();
                            }
                        }
                    }
                }catch (Exception e){
                    e.printStackTrace();
                }finally {
                    session.close();
                }
            }
        }
        return true;
    }

    public void getChildCategory(List<ChildCategory> categoryList,JdApiRequest jdApiRequest,CategoryQueryParamModel paramModel,String cookie){
        //循环类目 -- 只查询到3级
        for (int i = 0; i < categoryList.size(); i++) {
            System.out.println("categoryList.size()=====" + categoryList.size());
            ChildCategory category = categoryList.get(i);
            if(category.getLevel() < 4 && !category.isLeaf()){
                paramModel.getCategoryQueryParam().setCategoryId(category.getId());
                Map<String, Object> params = JSON.parseObject(JSON.toJSONString(paramModel), new TypeReference<Map<String, Object>>(){});
                JSONObject object = jdRequestService.jdPostRequest(jdApiRequest, params, cookie);
                if(object !=null && Objects.equals("200",object.getString("code"))){
                    ChildCategory childCategory = JSONObject.toJavaObject(object.getJSONObject("data"), ChildCategory.class);
                    if(childCategory.getChild() != null && !childCategory.getChild().isEmpty()){
                        List<ChildCategory> collect = new ArrayList<>();
                        if(category.getLevel() == 1){
                            collect = childCategory.getChild().stream().peek(item -> {
                                item.setParentId(category.getId());
                                item.setOneCategoryId(category.getId());
                                item.setOneCategoryName(category.getName());
                                item.setTwoCategoryId(item.getId());
                                item.setTwoCategoryName(item.getName());
                            }).collect(Collectors.toList());
                        }else if(category.getLevel() == 2){
                            collect = childCategory.getChild().stream().peek(item -> {
                                item.setParentId(category.getId());
                                item.setOneCategoryId(category.getOneCategoryId());
                                item.setOneCategoryName(category.getOneCategoryName());
                                item.setTwoCategoryId(category.getId());
                                item.setTwoCategoryName(category.getName());
                                item.setThreeCategoryId(item.getId());
                                item.setThreeCategoryName(item.getName());
                            }).collect(Collectors.toList());
                        }else if(category.getLevel() == 3){
                            collect = childCategory.getChild().stream().peek(item -> {
                                item.setParentId(category.getId());
                                item.setOneCategoryId(category.getOneCategoryId());
                                item.setOneCategoryName(category.getOneCategoryName());
                                item.setTwoCategoryId(category.getTwoCategoryId());
                                item.setTwoCategoryName(category.getTwoCategoryName());
                                item.setThreeCategoryId(category.getThreeCategoryId());
                                item.setThreeCategoryName(category.getThreeCategoryName());
                            }).collect(Collectors.toList());
                        }
                        categoryList.addAll(collect);
                    }
                }
            }
        }
    }

    /**
     * @Description: 获取post请求参数
     * @Author HuangJun
     * @Date 2024/4/16 15:28
     * @Return
     */
    private Map<String, Object> getPostParams(String type,JSONObject data){
        if(type.equals(JdApiFunctionEnum.获取订单列表信息.getJdApiFunction())){
            Map<String, Object> params = new HashMap<>();
            params.put("source","2000");
            params.put("data",data);
            Map<String, Object> paramters = new HashMap<>();
            paramters.put("request",params);
            return paramters;
        }
        else if(type.equals(JdApiFunctionEnum.获取订单物流信息.getJdApiFunction())){
            Map<String, Object> params = new HashMap<>();
            params.put("param",data);
            return params;
        }
        else if(type.equals(JdApiFunctionEnum.设置及修改商家备注.getJdApiFunction())){
            //添加备注接口参数：{param: {orderId: "291487503195", level: 0, remark: "-"}}
            Map<String, Object> params = new HashMap<>();
            params.put("param",data);
            return params;
        }
        else if(type.equals(JdApiFunctionEnum.批量设置及修改商家备注.getJdApiFunction())){
            //批量添加备注接口参数：{"param": {"level": 1,"orderIds": ["289766716527"],"remark": "缺货"}}
            Map<String, Object> params = new HashMap<>();
            params.put("param",data);
            return params;
        }
        else if(type.equals(JdApiFunctionEnum.普通发货.getJdApiFunction())){
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
            params.put("data", Arrays.asList(data));
            Map<String, Object> paramters = new HashMap<>();
            paramters.put("request",params);
            return paramters;
        } else if(type.equals(JdApiFunctionEnum.电子面单发货.getJdApiFunction())){
            //电子面单发货
            //{"request":{"source":"2000","data":[{"venderTaskAddressId":21318561,"deliveryType":203,"deliveryNumber":{"deliveryId":"2170","deliveryName":"邮政快递包裹","packageNum":1,"guaranteeValue":"0","epsOutShip":{"operationType":1,"branchCode":"1100099447061","insureValue":"0"}},"orderIds":[289651098551]}]}}
            Map<String, Object> params = new HashMap<>();
            params.put("source","2000");
            params.put("data",Arrays.asList(data));
            Map<String, Object> paramters = new HashMap<>();
            paramters.put("request",params);
            return paramters;
        }
        else if(type.equals(JdApiFunctionEnum.获取商品信息.getJdApiFunction())){
            return data;
        }
        else if(type.equals(JdApiFunctionEnum.获取隐藏的地址及电话.getJdApiFunction())){
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
}
