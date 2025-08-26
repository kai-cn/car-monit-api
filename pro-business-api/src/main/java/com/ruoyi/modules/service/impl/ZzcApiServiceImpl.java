package com.ruoyi.modules.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.common.util.DateUtils;
import com.ruoyi.modules.config.enums.CostTypeEnum;
import com.ruoyi.modules.config.enums.ZzcOrderStatusEnum;
import com.ruoyi.modules.config.enums.ZzcStatusEnum;
import com.ruoyi.modules.config.enums.ZzcTypeEnum;
import com.ruoyi.modules.entity.*;
import com.ruoyi.modules.service.*;
import com.ruoyi.modules.service.forest.HttpZzcRequestService;
import com.ruoyi.modules.vo.zzc.FindDifficultLogistics;
import com.ruoyi.modules.vo.zzc.FindDifficultLogisticsResult;
import com.ruoyi.modules.vo.zzc.ZzcOrderInfoCallBack;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.collections.CollectionUtils;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.math.BigDecimal;
import java.util.*;

/**
 * @Description: 中转仓回调接口
 * @Author: ret-boot
 * @Date: 2024-04-28
 * @Version: V1.0
 */
@Slf4j
@Service
public class ZzcApiServiceImpl implements IZzcApiService {

    @Autowired
    private IEcZzcOrderInfoService ecZzcOrderInfoService;
    @Autowired
    private IEcZzcOrderReturnInfoService ecZzcOrderReturnInfoService;
    @Resource
    private HttpZzcRequestService httpZzcRequestService;
    @Autowired
    private IEcShopAccountService ecShopAccountService;
    @Autowired
    private IEcZzcDifficultService zzcDifficultService;

    /**
     * 回调接口处理业务逻辑：
     * 1、反改中转仓订单表信息
     * 2、扣费
     * 业务类型：
     * type=1 重量扣费
     * type=2 包裹状态
     * type=3退回件的超重扣费
     * type=4提前揽件仓库已打包礼品发出 -- 中转仓暂时不用
     * type=5 提前揽件仓库已打包礼品发出 -- 中转仓暂时不用
     * type=6 推送疑难件的信息
     * type=7 推送不取单号下单，然后更新新的中转单号
     * type=8 推送超重退回费用， price正数是退回，负数是扣除
     *    todo:礼品单逻辑不处理，中转仓取消了礼品单业务
     */
    @Override
    public String callBackByZzcOrder(ZzcOrderInfoCallBack zzcOrderInfoCallBack) {
        String type = zzcOrderInfoCallBack.getType();
        if (Objects.equals(ZzcTypeEnum.重量扣费1.getZzcTypeEnum(), type)) {
            //重量扣费反改及扣费逻辑处理
            this.handleWeightDeductionsFee(zzcOrderInfoCallBack);

        } else if (Objects.equals(ZzcTypeEnum.包裹状态2.getZzcTypeEnum(), type)) {
            //根据中转仓单据id或者中转仓运单号 反改中转仓订单表中的状态
            this.handleUpdateOrderStatus(zzcOrderInfoCallBack);

        } else if (Objects.equals(ZzcTypeEnum.退回件的超重扣费3.getZzcTypeEnum(), type)) {
            this.handleReturnWeightDeductionsFee(zzcOrderInfoCallBack);
        } else if (Objects.equals(ZzcTypeEnum.提前揽件仓库已打包礼品发出4.getZzcTypeEnum(), type)) {
            //中转仓停止了礼品单业务，无需处理

        } else if (Objects.equals(ZzcTypeEnum.提前揽件仓库已打包礼品发出5.getZzcTypeEnum(), type)) {
            //中转仓停止了礼品单业务，无需处理

        } else if (Objects.equals(ZzcTypeEnum.推送疑难件的信息6.getZzcTypeEnum(), type)) {
            //处理新增数据到疑难件表中的逻辑
            this.handleDifficultLogistics(zzcOrderInfoCallBack);

        } else if (Objects.equals(ZzcTypeEnum.推送不取单号下单7.getZzcTypeEnum(), type)) {
            //处理反改中转仓运单号到中转仓表中的逻辑
            this.handleSetExpressageNo(zzcOrderInfoCallBack);

        } else if (Objects.equals(ZzcTypeEnum.推送超重退回费用8.getZzcTypeEnum(), type)) {
            this.handleReturnWeightDeductionsFee2(zzcOrderInfoCallBack);
        }

        return "success";
    }

    /**
     * @Description: 重量扣费反改及扣费逻辑处理
     * @Param zzcOrderInfoCallBack
     * @Return ZzcTypeEnum.重量扣费1.getZzcTypeEnum()
     * todo:已测试
     */
    private void handleWeightDeductionsFee(ZzcOrderInfoCallBack zzcOrderInfoCallBack) {
        BigDecimal weight = zzcOrderInfoCallBack.getWeight();
        BigDecimal price = zzcOrderInfoCallBack.getPrice();

        List<EcZzcOrderInfo> zzcOrderInfos = ecZzcOrderInfoService.list(
                new LambdaQueryWrapper<EcZzcOrderInfo>()
                        .eq(EcZzcOrderInfo::getZzcId, zzcOrderInfoCallBack.getZzcId())
                        .orderByDesc(EcZzcOrderInfo::getCreateTime)
        );
        if (CollectionUtils.isNotEmpty(zzcOrderInfos)) {
            EcZzcOrderInfo ecZzcOrderInfo = zzcOrderInfos.get(0);
            LambdaUpdateWrapper<EcZzcOrderInfo> updateWrapper = new LambdaUpdateWrapper<>();
            //无重量但是存在费用，非超重扣费
            if (price != null && price.compareTo(BigDecimal.ZERO) > 0) {
                String kfType = "发货扣费";
                if (weight != null && weight.compareTo(BigDecimal.ZERO) > 0) {
                    kfType = "超重扣费";
                    //1、设置超重扣费
                    updateWrapper.set(EcZzcOrderInfo::getIsOverWeight, "1");
                    updateWrapper.set(EcZzcOrderInfo::getOverWeightFee, price);
                    updateWrapper.set(EcZzcOrderInfo::getTsfOverWeightFee, price);
                    updateWrapper.set(EcZzcOrderInfo::getWeight, weight);
                } else {
                    //设置包装扣费
                    updateWrapper.set(EcZzcOrderInfo::getPackPrice, price);
                }

                //核算实际扣费
                BigDecimal actualFee = BigDecimal.ZERO;
                if (ecZzcOrderInfo.getActualFee() != null && ecZzcOrderInfo.getActualFee().compareTo(BigDecimal.ZERO) > 0) {
                    actualFee = price.add(ecZzcOrderInfo.getActualFee() == null?BigDecimal.ZERO:ecZzcOrderInfo.getActualFee());
                } else {
                    actualFee = price.add(ecZzcOrderInfo.getHoldingFee() == null?BigDecimal.ZERO:ecZzcOrderInfo.getHoldingFee());
                }
                updateWrapper.set(EcZzcOrderInfo::getActualFee, actualFee);

                BigDecimal tsfActualFee = BigDecimal.ZERO;
                if (ecZzcOrderInfo.getTsfActualFee() != null && ecZzcOrderInfo.getTsfActualFee().compareTo(BigDecimal.ZERO) > 0) {
                    tsfActualFee = price.add(ecZzcOrderInfo.getTsfActualFee() == null?BigDecimal.ZERO:ecZzcOrderInfo.getTsfActualFee());
                } else {
                    tsfActualFee = price.add(ecZzcOrderInfo.getTsfHoldingFee() == null?BigDecimal.ZERO:ecZzcOrderInfo.getTsfHoldingFee());
                }
                updateWrapper.set(EcZzcOrderInfo::getTsfActualFee, tsfActualFee);

                //反改信息
                if (StringUtils.isNotEmpty(zzcOrderInfoCallBack.getSendLogisticsNumber())) {
                    updateWrapper.eq(EcZzcOrderInfo::getExpressageNo, zzcOrderInfoCallBack.getSendLogisticsNumber());
                }
                updateWrapper.eq(EcZzcOrderInfo::getZzcId, zzcOrderInfoCallBack.getZzcId());
                //todo:处理超重和包装扣费逻辑
                Result result = this.doS(zzcOrderInfoCallBack, CostTypeEnum.中转仓实际扣费.getCode(), kfType,ecZzcOrderInfo);
                if(result.isSuccess()){
                    ecZzcOrderInfoService.update(updateWrapper);
                }
            } else {
                if (weight != null && weight.compareTo(BigDecimal.ZERO) > 0) {
                    //1、反改中转仓订单表信息
                    updateWrapper.set(EcZzcOrderInfo::getWeight, weight);
                    if (StringUtils.isNotEmpty(zzcOrderInfoCallBack.getSendLogisticsNumber())) {
                        updateWrapper.eq(EcZzcOrderInfo::getExpressageNo, zzcOrderInfoCallBack.getSendLogisticsNumber());
                    }
                    updateWrapper.eq(EcZzcOrderInfo::getZzcId, zzcOrderInfoCallBack.getZzcId());
                    ecZzcOrderInfoService.update(updateWrapper);
                }
            }
        }
    }

    /**
     * @Description: 根据中转仓单据id或者中转仓运单号 反改中转仓订单表中的状态
     * @Param zzcOrderInfoCallBack
     * @Return ZzcTypeEnum.包裹状态2.getZzcTypeEnum()
     *  todo:已测试
     */
    @Transactional(rollbackFor = Exception.class)
    public void handleUpdateOrderStatus(ZzcOrderInfoCallBack zzcOrderInfoCallBack) {
        List<EcZzcOrderInfo> zzcOrderInfos = ecZzcOrderInfoService.list(
                new LambdaQueryWrapper<EcZzcOrderInfo>()
                        .eq(EcZzcOrderInfo::getZzcId, zzcOrderInfoCallBack.getZzcId())
                        .orderByDesc(EcZzcOrderInfo::getCreateTime)
        );
        if (CollectionUtils.isNotEmpty(zzcOrderInfos)) {
            EcZzcOrderInfo ecZzcOrderInfo = zzcOrderInfos.get(0);
            LambdaUpdateWrapper<EcZzcOrderInfo> updateWrapper = new LambdaUpdateWrapper<>();
            switch (zzcOrderInfoCallBack.getPackState()) {
                case 1:
                    updateWrapper.set(EcZzcOrderInfo::getStatus, ZzcStatusEnum.NOTARRIVED.getCodeString());
                    updateWrapper.set(EcZzcOrderInfo::getOrderStatus, ZzcOrderStatusEnum.NOTARRIVED.getCodeString());
                    break;
                case 2:
                    updateWrapper.set(EcZzcOrderInfo::getStatus, ZzcStatusEnum.ARRIVED.getCodeString());
                    break;
                case 3:
                    updateWrapper.set(EcZzcOrderInfo::getOrderStatus, ZzcOrderStatusEnum.EMIT.getCodeString());
                    updateWrapper.set(EcZzcOrderInfo::getStatus, ZzcStatusEnum.FORWARDED.getCodeString());
                    //先执行预扣费退回在扣除实际扣费
                    Result result = this.doF(zzcOrderInfoCallBack, CostTypeEnum.中转仓预扣费用.getCode(), "中转仓预扣费");
                    if (result.isSuccess()) {
                        //获取单据中的实际扣费
                        zzcOrderInfoCallBack.setPrice(ecZzcOrderInfo.getHoldingFee());
                        Result result2 = this.doS(zzcOrderInfoCallBack, CostTypeEnum.中转仓实际扣费.getCode(), "中转仓实际扣费",ecZzcOrderInfo);
                        log.info("实际扣费操作：{}，msg：{}", result2.isSuccess(), result2.getMessage());
                    }
                    break;
            }
            if (StringUtils.isNotEmpty(zzcOrderInfoCallBack.getSendLogisticsNumber())) {
                updateWrapper.eq(EcZzcOrderInfo::getExpressageNo, zzcOrderInfoCallBack.getSendLogisticsNumber());
            }
            updateWrapper.eq(EcZzcOrderInfo::getZzcId, zzcOrderInfoCallBack.getZzcId());
            ecZzcOrderInfoService.update(updateWrapper);
        }
    }

    /**
     * @Description: 退回件的超重扣费3逻辑处理
     * @Param zzcOrderInfoCallBack
     * @Return ZzcTypeEnum.退回件的超重扣费3.getZzcTypeEnum()
     *
     */
    private Result handleReturnWeightDeductionsFee(ZzcOrderInfoCallBack zzcOrderInfoCallBack) {
        BigDecimal weight = zzcOrderInfoCallBack.getWeight();
        BigDecimal price = zzcOrderInfoCallBack.getPrice();
        //这里处理退回件的信息
        List<EcZzcOrderReturnInfo> zzcOrderReturnInfos = ecZzcOrderReturnInfoService.list(
                new LambdaQueryWrapper<EcZzcOrderReturnInfo>()
                        .eq(EcZzcOrderReturnInfo::getExpressageNo, zzcOrderInfoCallBack.getSendLogisticsNumber())
                        .orderByDesc(EcZzcOrderReturnInfo::getCreateTime)
        );

        LambdaUpdateWrapper<EcZzcOrderReturnInfo> updateWrapper = new LambdaUpdateWrapper<>();
        if (CollectionUtils.isNotEmpty(zzcOrderReturnInfos)) {
            EcZzcOrderReturnInfo zzcOrderReturnInfo = zzcOrderReturnInfos.get(0);
            if (price != null && price.compareTo(BigDecimal.ZERO) > 0) {
                String kfType = "退回件发货扣费";
                if (weight != null && weight.compareTo(BigDecimal.ZERO) > 0) {
                    kfType = "退回件超重扣费";
                    //1、设置超重扣费
                    updateWrapper.set(EcZzcOrderReturnInfo::getIsOverWeight, "1");
                    updateWrapper.set(EcZzcOrderReturnInfo::getOverWeightFee, price);
                    updateWrapper.set(EcZzcOrderReturnInfo::getTsfOverWeightFee, price);
                    updateWrapper.set(EcZzcOrderReturnInfo::getWeight, weight);
                } else {
                    //设置包装扣费
                    updateWrapper.set(EcZzcOrderReturnInfo::getPackPrice, price);
                }

                //核算实际扣费
                BigDecimal actualFee = BigDecimal.ZERO;
                if (zzcOrderReturnInfo.getActualFee() != null && zzcOrderReturnInfo.getActualFee().compareTo(BigDecimal.ZERO) > 0) {
                    actualFee = price.add(zzcOrderReturnInfo.getActualFee() == null?BigDecimal.ZERO:zzcOrderReturnInfo.getActualFee());
                } else {
                    actualFee = price.add(zzcOrderReturnInfo.getHoldingFee() == null?BigDecimal.ZERO:zzcOrderReturnInfo.getHoldingFee());
                }
                updateWrapper.set(EcZzcOrderReturnInfo::getActualFee, actualFee);

                BigDecimal tsfActualFee = BigDecimal.ZERO;
                if (zzcOrderReturnInfo.getTsfActualFee() != null && zzcOrderReturnInfo.getTsfActualFee().compareTo(BigDecimal.ZERO) > 0) {
                    tsfActualFee = price.add(zzcOrderReturnInfo.getTsfActualFee() == null?BigDecimal.ZERO:zzcOrderReturnInfo.getTsfActualFee());
                } else {
                    tsfActualFee = price.add(zzcOrderReturnInfo.getTsfHoldingFee() == null?BigDecimal.ZERO:zzcOrderReturnInfo.getTsfHoldingFee());
                }
                updateWrapper.set(EcZzcOrderReturnInfo::getTsfActualFee, tsfActualFee);
                //反改信息
                updateWrapper.eq(EcZzcOrderReturnInfo::getExpressageNo, zzcOrderInfoCallBack.getSendLogisticsNumber());
                //todo:处理超重和包装扣费逻辑
                EcZzcOrderInfo zzcOrderInfo = new EcZzcOrderInfo();
                zzcOrderInfo.setShopId(zzcOrderReturnInfo.getShopId() + "");
                zzcOrderInfo.setShopName(zzcOrderReturnInfo.getShopName());
                zzcOrderInfo.setOrderId(zzcOrderReturnInfo.getOrderId());
                Result result = this.doS(zzcOrderInfoCallBack, CostTypeEnum.中转仓实际扣费.getCode(), kfType,zzcOrderInfo);
                if(result.isSuccess()){
                    ecZzcOrderReturnInfoService.update(updateWrapper);
                }
            } else {
                if (weight != null && weight.compareTo(BigDecimal.ZERO) > 0) {
                    //1、反改中转仓订单表信息
                    updateWrapper.set(EcZzcOrderReturnInfo::getWeight, weight);
                    updateWrapper.eq(EcZzcOrderReturnInfo::getExpressageNo, zzcOrderInfoCallBack.getSendLogisticsNumber());
                    ecZzcOrderReturnInfoService.update(updateWrapper);
                }
            }
        }else{
            return Result.error("该订单不存在，请确认！");
        }
        return Result.OK("success");
    }

    /**
     * @Description: 处理反改中转仓运单号到中转仓表中的逻辑
     * @Param zzcOrderInfoCallBack
     * @Return ZzcTypeEnum.推送不取单号下单7.getZzcTypeEnum()
     * todo:已测试
     */
    private void handleSetExpressageNo(ZzcOrderInfoCallBack zzcOrderInfoCallBack) {
        //处理反改中转仓运单号到中转仓表中的逻辑
        ecZzcOrderInfoService.update(
                new LambdaUpdateWrapper<EcZzcOrderInfo>()
                        .eq(EcZzcOrderInfo::getZzcId, zzcOrderInfoCallBack.getZzcId())
                        .set(EcZzcOrderInfo::getExpressageNo, zzcOrderInfoCallBack.getSendLogisticsNumber())
        );
    }

    /**
     * @Description: 处理新增数据到疑难件表中的逻辑
     * @Param zzcOrderInfoCallBack
     * @Return ZzcTypeEnum.推送疑难件的信息6.getZzcTypeEnum()
     * todo:已测试
     */
    private void handleDifficultLogistics(ZzcOrderInfoCallBack zzcOrderInfoCallBack) {
        //这个接口返回的字段zzcOrderInfoCallBack.getZzcId() 是疑难件记录的主键  不是真正的zzcId
        //这个接口返回的字段zzcOrderInfoCallBack.getSendLogisticsNumber() 是货源物流号，不是中转物流运单号
        Result<List<FindDifficultLogisticsResult>> result = httpZzcRequestService.findDifficultLogistics(
                new FindDifficultLogistics().setDifficultId(zzcOrderInfoCallBack.getZzcId()), "anno-yes");
        if (result.isSuccess()) {
            List<FindDifficultLogisticsResult> difficultLogisticsResults = result.getResult();
            if (CollectionUtils.isNotEmpty(difficultLogisticsResults)) {
                FindDifficultLogisticsResult difficultLogisticsResult = difficultLogisticsResults.get(0);
                EcZzcDifficult zzcDifficult = new EcZzcDifficult();
                List<EcZzcOrderInfo> zzcOrderInfos = ecZzcOrderInfoService.list(
                        new LambdaQueryWrapper<EcZzcOrderInfo>()
                                .eq(EcZzcOrderInfo::getOrderId, difficultLogisticsResult.getSaleOrderId())
                                .orderByDesc(EcZzcOrderInfo::getCreateTime)
                );

                if (CollectionUtils.isNotEmpty(zzcOrderInfos)) {
                    EcZzcOrderInfo ecZzcOrderInfo = zzcOrderInfos.get(0);
                    zzcDifficult.setZzcId(Long.valueOf(ecZzcOrderInfo.getZzcId()));
                    zzcDifficult.setShopId(ecZzcOrderInfo.getShopId());
                    zzcDifficult.setSaleShopName(ecZzcOrderInfo.getShopName());
                    zzcDifficult.setStoreType(ecZzcOrderInfo.getStoreType());
                    zzcDifficult.setCreateBy(ecZzcOrderInfo.getUserId());
                    zzcDifficult.setUpdateBy(ecZzcOrderInfo.getUserId());
                    if (!Objects.isNull(difficultLogisticsResult.getUserId())) {
                        zzcDifficult.setUserId(difficultLogisticsResult.getUserId());
                    } else {
                        if (StringUtils.isNotEmpty(ecZzcOrderInfo.getUserId())) {
                            zzcDifficult.setUserId(Long.valueOf(ecZzcOrderInfo.getUserId()));
                        }
                    }
                }
                zzcDifficult.setDifficultId(zzcOrderInfoCallBack.getZzcId());
                zzcDifficult.setCangId(difficultLogisticsResult.getCangId());
                zzcDifficult.setCangName(difficultLogisticsResult.getCangName());
                zzcDifficult.setSaleOrderId(difficultLogisticsResult.getSaleOrderId());
                zzcDifficult.setHuoyuanLogisticsNumber(difficultLogisticsResult.getHuoyuanLogisticsNumber());
                zzcDifficult.setState(difficultLogisticsResult.getState());
                zzcDifficult.setPackState(difficultLogisticsResult.getPackState());
                zzcDifficult.setReason(difficultLogisticsResult.getReason());
                zzcDifficult.setSendPhone(difficultLogisticsResult.getSendPhone());
                zzcDifficult.setUserState(difficultLogisticsResult.getUserState());
                zzcDifficult.setKefuState(difficultLogisticsResult.getKefuState());
                zzcDifficult.setIndexRemark(difficultLogisticsResult.getIndexRemark());
                zzcDifficult.setUserRemark(difficultLogisticsResult.getUserRemark());
                if (difficultLogisticsResult.getLists().length > 0) {
                    zzcDifficult.setImage(difficultLogisticsResult.getLists()[0]);
                }
                zzcDifficult.setDifficultTime(difficultLogisticsResult.getInsertTime());
                zzcDifficult.setRemark(difficultLogisticsResult.getRemark());
                zzcDifficult.setId(com.ruoyi.common.util.StringUtils.getUUID());
                zzcDifficult.setDelFlag(0);
                zzcDifficult.setCreateTime(DateUtils.getTimestamp());
                zzcDifficult.setUpdateTime(DateUtils.getTimestamp());
                zzcDifficultService.save(zzcDifficult);
            }
        }
    }

    /**
     * @Description: 推送超重退回费用
     * @Param zzcOrderInfoCallBack
     * @Return ZzcTypeEnum.推送超重退回费用8.getZzcTypeEnum()
     */
    private void handleReturnWeightDeductionsFee2(ZzcOrderInfoCallBack zzcOrderInfoCallBack) {
        BigDecimal price = zzcOrderInfoCallBack.getPrice();
        String zzcId = zzcOrderInfoCallBack.getZzcId();

        List<EcZzcOrderInfo> zzcOrderInfos = ecZzcOrderInfoService.list(
                new LambdaQueryWrapper<EcZzcOrderInfo>()
                        .eq(EcZzcOrderInfo::getZzcId, zzcId).orderByDesc(EcZzcOrderInfo::getCreateTime)
        );

        if (CollectionUtils.isNotEmpty(zzcOrderInfos)) {
            EcZzcOrderInfo ecZzcOrderInfo = zzcOrderInfos.get(0);
            //这里处理退回件的信息
            LambdaUpdateWrapper<EcZzcOrderInfo> updateWrapper = new LambdaUpdateWrapper<>();
            updateWrapper.eq(EcZzcOrderInfo::getZzcId, zzcId);
            //金额大于0   退回费用
            if (price != null && price.compareTo(BigDecimal.ZERO) > 0) {
                BigDecimal overWeightFee = Objects.isNull(zzcOrderInfos.get(0).getOverWeightFee()) ? BigDecimal.ZERO : zzcOrderInfos.get(0).getOverWeightFee();
                BigDecimal subOverWeightFee = overWeightFee.subtract(price);
                updateWrapper.set(EcZzcOrderInfo::getOverWeightFee, subOverWeightFee);
                updateWrapper.set(EcZzcOrderInfo::getTsfOverWeightFee, subOverWeightFee);
                if (subOverWeightFee.compareTo(BigDecimal.ZERO) <= 0) {
                    updateWrapper.set(EcZzcOrderInfo::getIsOverWeight, "0");
                }

                //核算实际扣费
                BigDecimal actualFee = BigDecimal.ZERO;
                if (ecZzcOrderInfo.getActualFee() != null && ecZzcOrderInfo.getActualFee().compareTo(BigDecimal.ZERO) > 0) {
                    actualFee = ecZzcOrderInfo.getActualFee().subtract(price);
                } else {
                    actualFee = ecZzcOrderInfo.getHoldingFee().subtract(price);
                }
                updateWrapper.set(EcZzcOrderInfo::getActualFee, actualFee);

                BigDecimal tsfActualFee = BigDecimal.ZERO;
                if (ecZzcOrderInfo.getTsfActualFee() != null && ecZzcOrderInfo.getTsfActualFee().compareTo(BigDecimal.ZERO) > 0) {
                    tsfActualFee = ecZzcOrderInfo.getTsfActualFee().subtract(price);
                } else {
                    tsfActualFee = ecZzcOrderInfo.getTsfHoldingFee().subtract(price);
                }
                updateWrapper.set(EcZzcOrderInfo::getTsfActualFee, tsfActualFee);

                Result result = this.doNoDetailF(zzcOrderInfoCallBack, CostTypeEnum.中转仓退回扣费.getCode(), "超重退回费用", "超重退回费用",ecZzcOrderInfo);
                if(result.isSuccess()){
                    ecZzcOrderInfoService.update(updateWrapper);
                }
            }//金额小于0   扣除费用
            else if (price != null && price.compareTo(BigDecimal.ZERO) < 0) {
                //负数转正数
                price = price.abs();
                zzcOrderInfoCallBack.setPrice(price);
                //超重扣费费用
                BigDecimal overWeightFee = Objects.isNull(zzcOrderInfos.get(0).getOverWeightFee()) ? BigDecimal.ZERO : zzcOrderInfos.get(0).getOverWeightFee();
                BigDecimal addOverWeightFee = overWeightFee.add(price);
                updateWrapper.set(EcZzcOrderInfo::getOverWeightFee, addOverWeightFee);
                updateWrapper.set(EcZzcOrderInfo::getTsfOverWeightFee, addOverWeightFee);
                if (addOverWeightFee.compareTo(BigDecimal.ZERO) > 0) {
                    updateWrapper.set(EcZzcOrderInfo::getIsOverWeight, "1");
                }

                //核算实际扣费
                BigDecimal actualFee = BigDecimal.ZERO;
                if (ecZzcOrderInfo.getActualFee() != null && ecZzcOrderInfo.getActualFee().compareTo(BigDecimal.ZERO) > 0) {
                    actualFee = price.add(ecZzcOrderInfo.getActualFee() == null?BigDecimal.ZERO:ecZzcOrderInfo.getActualFee());
                } else {
                    actualFee = price.add(ecZzcOrderInfo.getHoldingFee() == null?BigDecimal.ZERO:ecZzcOrderInfo.getHoldingFee());
                }
                updateWrapper.set(EcZzcOrderInfo::getActualFee, actualFee);

                BigDecimal tsfActualFee = BigDecimal.ZERO;
                if (ecZzcOrderInfo.getTsfActualFee() != null && ecZzcOrderInfo.getTsfActualFee().compareTo(BigDecimal.ZERO) > 0) {
                    tsfActualFee = price.add(ecZzcOrderInfo.getTsfActualFee() == null?BigDecimal.ZERO:ecZzcOrderInfo.getTsfActualFee());
                } else {
                    tsfActualFee = price.add(ecZzcOrderInfo.getTsfHoldingFee() == null?BigDecimal.ZERO:ecZzcOrderInfo.getTsfHoldingFee());
                }
                updateWrapper.set(EcZzcOrderInfo::getTsfActualFee, tsfActualFee);

                Result result = this.doS(zzcOrderInfoCallBack, CostTypeEnum.中转仓实际扣费.getCode(), "超重扣除费用",ecZzcOrderInfo);
                if(result.isSuccess()){
                    ecZzcOrderInfoService.update(updateWrapper);
                }
            }
        }
    }

    /**
     * @Description: 扣款
     * @Author HuangJun
     * @Date 2024/7/23 15:23
     * @Return
     */
    @Transactional(rollbackFor = Exception.class)
    public Result doS(ZzcOrderInfoCallBack zzcOrderInfoCallBack, String costType, String kfType,EcZzcOrderInfo zzcOrderInfo) {
        if (zzcOrderInfo != null) {
            Map<String, BigDecimal> map = new HashMap<>(8);
            map.put("logisticsPrice", zzcOrderInfoCallBack.getPrice());
            Result result = ecShopAccountService.checkPrePay(costType, zzcOrderInfo.getShopId(),"2", zzcOrderInfo.getTenantId(), 1, map);
            EcShopAccount ecShopAccount = null;
            if (result.isSuccess()) {
                ecShopAccount = (EcShopAccount) result.getResult();
            } else {
                return result;
            }
            //执行扣款逻辑
            String msg = kfType + ":";
            if (StringUtils.isNotEmpty(zzcOrderInfoCallBack.getPackDetail())) {
                msg += zzcOrderInfoCallBack.getPackDetail() + " ";
            }
            if (!Objects.isNull(ecShopAccount.getPayTotalMoney())) {
                msg += ecShopAccount.getPayTotalMoney();
            }
            Map<String, String> doPayMap = new HashMap<>(8);
            doPayMap.put("kfType", kfType);
            return ecShopAccountService.doPay(costType, zzcOrderInfo.getOrderId(), zzcOrderInfo.getShopId(), zzcOrderInfo.getShopName(), msg, ecShopAccount, doPayMap);
        }
        return Result.error("订单不存在，请确认！");
    }

    /**
     * @Description: 按明细退款
     * @Author HuangJun
     * @Date 2024/7/23 15:23
     * @Return
     */
    public Result doF(ZzcOrderInfoCallBack zzcOrderInfoCallBack, String costType, String kfType) {
        LambdaQueryWrapper<EcZzcOrderInfo> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(EcZzcOrderInfo::getZzcId, zzcOrderInfoCallBack.getZzcId())
                .orderByDesc(EcZzcOrderInfo::getCreateTime);
        //获取扣款业务类型对应的费用标准
        List<EcZzcOrderInfo> list = ecZzcOrderInfoService.list(queryWrapper);
        if (CollectionUtils.isNotEmpty(list)) {
            EcZzcOrderInfo zzcOrderInfo = list.get(0);
            // 查询账号余额度
            EcShopAccount ecShopAccount = ecShopAccountService.selectEcShopAccountBO(zzcOrderInfo.getShopId(), "2");
            //这里传的是预扣费的类型，否则查不到数据
            ecShopAccount.setCostType(costType);
            ecShopAccount.setOrderId(zzcOrderInfo.getOrderId());
            ecShopAccount.setKfType(kfType);
            //执行退款逻辑
            return ecShopAccountService.doRefund(ecShopAccount, CostTypeEnum.中转仓退回扣费);
        }
        return Result.error("订单不存在，请确认！");
    }

    /**
     * @Description: 退款
     * @Author HuangJun
     * @Date 2024/7/23 15:23
     * @Return
     */
    public Result doNoDetailF(ZzcOrderInfoCallBack zzcOrderInfoCallBack, String costType, String kfType, String title,EcZzcOrderInfo zzcOrderInfo) {
        LambdaQueryWrapper<EcZzcOrderInfo> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(EcZzcOrderInfo::getZzcId, zzcOrderInfoCallBack.getZzcId()).orderByDesc(EcZzcOrderInfo::getCreateTime);
        // 查询账号余额度
        EcShopAccount ecShopAccount = ecShopAccountService.selectEcShopAccountBO(zzcOrderInfo.getShopId(), "2");
        //这里传的是预扣费的类型，否则查不到数据
        ecShopAccount.setCostType(costType);
        ecShopAccount.setOrderId(zzcOrderInfo.getOrderId());
        ecShopAccount.setKfType(kfType);
        ecShopAccount.setShopId(zzcOrderInfo.getShopId());
        ecShopAccount.setShopName(zzcOrderInfo.getShopName());
        ecShopAccount.setPayTotalMoney(zzcOrderInfoCallBack.getPrice());
        //执行扣款逻辑
        String msg = title + ":" + zzcOrderInfoCallBack.getPackDetail() + ecShopAccount.getPayTotalMoney();
        //执行退款逻辑
        return ecShopAccountService.doRefundNoDetail(ecShopAccount, CostTypeEnum.中转仓退回扣费, zzcOrderInfoCallBack.getPrice(), msg);
    }
}
