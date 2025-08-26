package com.ruoyi.modules.vo.jd;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.util.List;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/6/21 9:04
 * @Return
 */
@Data
public class ChildCategory {
    private int catState;
    private String tipContent;
    private String publishEnable;
    private String interpretation;
    //类目层级
    private int level;
    //类目名称
    private String name;
    private String zeroYuanTrialOperation;
    //类目id
    private Long id;
    private boolean isLeaf;

    //父Id
    private Long parentId = 0L;

    //一级类目Id
    private Long oneCategoryId;

    //二级类目Id
    private Long twoCategoryId;

    //三级类目Id
    private Long threeCategoryId;

    //一级类目名称
    private String oneCategoryName;

    //二级类目名称
    private String twoCategoryName;

    //三级类目名称
    private String threeCategoryName;

    //子类目集合
    private List<ChildCategory> child;

    //创建时间
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private java.sql.Timestamp createTime;
}
