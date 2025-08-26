package com.ruoyi.modules.vo.zzc;

import com.fasterxml.jackson.annotation.JsonFormat;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import java.util.Date;
import java.util.List;

/**
 * @Description: 疑难件返回的数据
 * @Author HuangJun
 * @Date 2024/4/22 14:02
 * @Return
 */
@Data
@Accessors(chain = true)
public class FindDifficultLogisticsResult {

    //中转仓id
    private Long id;
    //用户id
    private Long userId;
    //账号id
    private String accessId;
    //仓库id
    private String cangId;
    //仓库名称
    private String cangName;
    //中转仓id
    private String difficultId;
    //货源物流好
    private String huoyuanLogisticsNumber;
    //用户操作
    private String userIdea;
    //订单状态
    private String orderState;
    //状态
    private String state;
    //保存时间
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date insertTime;
    //备注
    private String remark;
    //包装状态
    private String packState;
    //备注
    private String reason;
    //短码
    private String sortIndex;
    //发送手机
    private String sendPhone;
    //用户状态
    private String userState;
    //客服状态
    private String kefuState;
    //索引备注
    private String indexRemark;
    //店铺id
    private String saleOrderId;
    //店铺名称
    private String saleShopName;
    //用户备注
    private String userRemark;
    //图片地址
    private String[] lists;
    //分页
    private String page;
    //页大小
    private String limit;
    //你们自己用户的Id
    private String saleUid;

}


