package com.ruoyi.modules.service.impl;

import com.ruoyi.modules.service.IEcCostSzService;
import com.ruoyi.modules.service.IEcShopAccountService;
import com.ruoyi.modules.service.IEcShopBindService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.config.enums.CostTypeEnum;
import com.ruoyi.modules.mapper.EcBillingStatementMapper;
import com.ruoyi.modules.mapper.EcCostSzDetailMapper;
import com.ruoyi.modules.mapper.EcShopAccountMapper;
import com.ruoyi.common.util.DateUtils;
import com.ruoyi.common.util.StringUtils;
import com.ruoyi.modules.entity.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;


@Service
@Slf4j
public class EcShopAccountServiceImpl extends ServiceImpl<EcShopAccountMapper, EcShopAccount> implements IEcShopAccountService {

    @Autowired
    private IEcCostSzService ecCostSzService;
    @Autowired
    private EcShopAccountMapper ecShopAccountMapper;
    @Autowired
    private IEcShopBindService ecShopBindService;

    @Autowired
    private EcCostSzDetailMapper ecCostSzDetailMapper;

    @Autowired
    private EcBillingStatementMapper ecBillingStatementMapper;

    /**
     * 根据业务类型和业务ID: 获取增值账号信息
     *
     * @param  bussId 业务ID 主键ID 或者 店铺ID
     * @param  bussType 1 账号ID  2是店铺ID
     * @return 增值账号
     */
    @Override
    public EcShopAccount selectEcShopAccountBO(String bussId, String bussType){
        EcShopAccount ecShopAccount = new EcShopAccount();
        ecShopAccount.setTotalMoney(BigDecimal.ZERO);
        if ("1".equals(bussType)){
            ecShopAccount = ecShopAccountMapper.selectEcShopAccountById(bussId);
        }else{
            // 根据绑定的店铺ID 查询账号
            EcShopBind ecShopBind = ecShopBindService.selectByShopId(bussId);
            if (null !=ecShopBind && StringUtils.isNotBlank(ecShopBind.getAccountId())){
                ecShopAccount.setId(ecShopBind.getAccountId());
                ecShopAccount.setAccount(ecShopBind.getAccountName());
                ecShopAccount.setTotalMoney(ecShopBind.getTotalMoney());
                ecShopAccount.setCzTotalMoney(ecShopBind.getCzTotalMoney());
                ecShopAccount.setEpsId(ecShopBind.getEpsId());
                ecShopAccount.setTenantId(ecShopBind.getTenantId());
            }
        }
        return ecShopAccount;
    }

    /**
     * 扣款之前校验：成功返回账号信息  失败返回错误信息
     *
     * @param costType 费用类型
     * @param bussId   业务ID 账号ID 或者 店铺ID
     * @param bussType 1账号 2是店铺
     * @param quantity 数量
     * @param map      其他参数
     * @return
     */
    @Override
    public Result checkPrePay(String costType, String bussId,String bussType, Long tenantId, int quantity, Map map) {
        // 费用标准
        EcCostSz ecCostSz = ecCostSzService.getByCostType(costType,tenantId);
        if (null == ecCostSz
                && !costType.equals(CostTypeEnum.中转仓预扣费用.getCode())
                && !costType.equals(CostTypeEnum.中转仓实际扣费.getCode())){
            return Result.error(CostTypeEnum.getNameByCode(costType)+"费用设置为空，请联系管理员！");
        }

        // 查询账号余额度
        EcShopAccount ecShopAccount = this.selectEcShopAccountBO(bussId,bussType);
        if(StringUtils.isBlank(ecShopAccount.getId())){
            return Result.error("店铺未绑定增值账号！");
        }

        if (ecShopAccount.getTotalMoney().compareTo(BigDecimal.ZERO) <= 0){
            return Result.error("增值账号余额不足，请充值！");
        }


        // 短信标准 :  0.05元/条，每条短信长度限定57字，超过57字按照实际长度收费；
        if (costType.equals(CostTypeEnum.dxxf.getCode())){
            // 短信标准
            BigDecimal conutZs = new BigDecimal(57);
            if (null != ecCostSz.getEndRange()) {
                conutZs = ecCostSz.getEndRange();
            }
            // 短信内容
            String smsContext = "";
            if (null != map){
                if (null != map.get("smsContext")){
                    smsContext = map.get("smsContext").toString();
                }
            }
            if ("".equals(smsContext)){
                return Result.error("发送短信内容不能为空");
            }
            log.info("短信标准" + conutZs + "---短信内容长度：" + smsContext.length() + "---短信内容:" + smsContext);
            BigDecimal smsLength = new BigDecimal(smsContext.length()).divide(conutZs, 2, RoundingMode.HALF_UP);
            int zsValue = smsLength.intValue();  // 取得整数
            BigDecimal remainder = smsLength.remainder(BigDecimal.ONE); // 取得余数
            if (remainder.compareTo(BigDecimal.ZERO) > 0){
                zsValue = zsValue + 1;
            }
            quantity = quantity * zsValue;

        }else if(costType.equals(CostTypeEnum.xnhkf.getCode())
                || costType.equals(CostTypeEnum.tbwl_cdykf.getCode())
                || costType.equals(CostTypeEnum.tbwl_cdshkf.getCode())){
            // 同步单号：0-1000元 0.98元/单；1000-5000元 0.95元/单；5000-10000元 0.85元/单
            // 虚拟号：0-500元 0.2元/单；500-1000元 0.15元/单；1000元以上 0.1元/单
            BigDecimal czTotalMoney = ecShopAccount.getCzTotalMoney();
            if (null == czTotalMoney){
                czTotalMoney = BigDecimal.ZERO;
            }
            EcCostSzDetail ecCostSzDetail = new EcCostSzDetail();
            ecCostSzDetail.setQueryRange(czTotalMoney);
            ecCostSzDetail.setCostSzId(ecCostSz.getId());
            List<EcCostSzDetail> ecCostSzDetails = ecCostSzDetailMapper.selectEcCostSzDetailList(ecCostSzDetail);
            if (null !=ecCostSzDetails && ecCostSzDetails.size() > 0){
                EcCostSzDetail ecCostSzDetailRtn = ecCostSzDetails.get(0);
                if (null != ecCostSzDetailRtn.getCostMoney()){
                    ecCostSz.setCostMoney(ecCostSzDetailRtn.getCostMoney());
                }
            }
        }else if (costType.equals(CostTypeEnum.中转仓预扣费用.getCode())
                || costType.equals(CostTypeEnum.中转仓实际扣费.getCode())){
            ecCostSz = new EcCostSz();
            ecCostSz.setCostMoney((BigDecimal) map.get("logisticsPrice"));
        }

        // 扣款费用：扣除标准 * 数量
        BigDecimal payTotalMoney = ecCostSz.getCostMoney().multiply(new BigDecimal(quantity));
        if (payTotalMoney.compareTo(BigDecimal.ZERO) <= 0){
            return Result.error("扣款费用不能小于0！");
        }

        if (ecShopAccount.getTotalMoney().compareTo(payTotalMoney) < 0){
            return Result.error("增值账号余额不足，请充值！");
        }

        ecShopAccount.setPayTotalMoney(payTotalMoney);
        return  Result.OK(ecShopAccount);
    }

    /**
     * 执行扣款
     *
     * @param costType  费用类型
     * @param orderId   订单ID
     * @param storeId   店铺id
     * @param storeName 店铺名称
     * @param remark   备注
     * @param account   店铺绑定的账号对象
     * @param map   其他参数
     * @return
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result doPay(String costType, String orderId, String storeId, String storeName,
                        String remark, EcShopAccount account, Map map){

        // 修改账号剩余金额
        BigDecimal syMoney = account.getTotalMoney().subtract(account.getPayTotalMoney());
        account.setTotalMoney(syMoney);
        account.setUpdateTime(DateUtils.getTimestamp());
        ecShopAccountMapper.updateEcShopAccountMonery(account);

        // 插入账号流水
        EcBillingStatement ecBillingStatement = new EcBillingStatement();
        java.sql.Timestamp curDate = DateUtils.getTimestamp();
        ecBillingStatement.setOrderId(orderId);
        ecBillingStatement.setStoreId(storeId);
        ecBillingStatement.setStoreName(storeName);
        ecBillingStatement.setAccountId(account.getId());
        ecBillingStatement.setAccountName(account.getAccount());
        ecBillingStatement.setCostType(costType);
        ecBillingStatement.setCostMoney(account.getPayTotalMoney());
        ecBillingStatement.setBussType("1");
        ecBillingStatement.setRemark(remark);
        ecBillingStatement.setCreateBy(account.getCreateBy());
        ecBillingStatement.setUpdateBy(account.getCreateBy());
        ecBillingStatement.setEpsId(account.getEpsId());
        ecBillingStatement.setTenantId(account.getTenantId());
        // 新增 主键
        ecBillingStatement.setId(StringUtils.getUUID());
        ecBillingStatement.setCreateTime(curDate);
        ecBillingStatement.setUpdateTime(curDate);

        //中转仓存在子类扣费 -- 特殊业务逻辑处理
        if(map != null && map.containsKey("kfType")){
            ecBillingStatement.setKfType(map.get("kfType").toString());
        }

        ecBillingStatementMapper.insertEcBillingStatement(ecBillingStatement);
        return  Result.OK();
    }

    /**
     * 退款 ：根据订单id和业务退款
     *
     * @param paraAccount 增值账号
     * @return 结果
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result doRefund(EcShopAccount paraAccount,CostTypeEnum costTypeEnum){
        if(StringUtils.isBlank(paraAccount.getOrderId())){
            return Result.error("订单ID不能为空！");
        }
        if(StringUtils.isBlank(paraAccount.getCostType())){
            return Result.error("费用明细不能为空！");
        }
        EcBillingStatement ecBillingStatement = new EcBillingStatement();
        ecBillingStatement.setOrderId(paraAccount.getOrderId());
        ecBillingStatement.setCostType(paraAccount.getCostType());
        ecBillingStatement.setBussType("1");
        //中转仓会传这个值 -- 附加小类进行查询
        if(StringUtils.isNotBlank(paraAccount.getKfType())){
            ecBillingStatement.setKfType(paraAccount.getKfType());
        }
        List<EcBillingStatement> detailList = ecBillingStatementMapper.selectEcBillingStatementList(ecBillingStatement);

        if (null !=detailList && detailList.size() > 0){
            // 按照时间降序排序
            List<EcBillingStatement> newList = detailList.stream().sorted(Comparator.comparing(EcBillingStatement::getCreateTime,Comparator.reverseOrder())).collect(Collectors.toList());
            EcBillingStatement addbo = newList.get(0);

            String tkOldId = addbo.getId();

            // 判断该流水已退款
            if("1".equals(StringUtils.trim(addbo.getBackCol1()))){
                log.error("该单据已办理退款！");
                return Result.error("该单据已办理退款！");
            }

            if(StringUtils.isBlank(addbo.getAccountId())){
                log.error("该单据已办理退款！");
                return Result.error("退款充值账号不能为空！");
            }

            EcShopAccount account = ecShopAccountMapper.selectEcShopAccountById(addbo.getAccountId());
            if (null != account && StringUtils.isNotBlank(account.getId())) {
            } else {
                log.error("退款充值账号不能为空！");
                return Result.error("退款充值账号不能为空！");
            }

            EcShopAccount ecShopAccountUpt = new EcShopAccount();
            ecShopAccountUpt.setId(account.getId());
            // 修改账号剩余金额
            BigDecimal syMoney = account.getTotalMoney().add(addbo.getCostMoney());
            ecShopAccountUpt.setTotalMoney(syMoney);

            ecShopAccountUpt.setUpdateTime(DateUtils.getTimestamp());
            ecShopAccountMapper.updateEcShopAccountMonery(ecShopAccountUpt);

            // 插入明细
            addbo.setId(StringUtils.getUUID());
            addbo.setBussType("3");
            addbo.setBackCol2(tkOldId);
            addbo.setCostType(costTypeEnum.getCode());
            String msg = costTypeEnum.getName() + ":" + addbo.getCostMoney();
            addbo.setRemark(msg);
            addbo.setCreateTime(DateUtils.getTimestamp());
            addbo.setUpdateTime(DateUtils.getTimestamp());
            ecBillingStatementMapper.insertEcBillingStatement(addbo);

            // 标记以前的已退款
            EcBillingStatement updataOldBo = new EcBillingStatement();
            updataOldBo.setId(tkOldId);
            // 已退款
            updataOldBo.setBackCol1("1");
            updataOldBo.setUpdateTime(DateUtils.getTimestamp());
            ecBillingStatementMapper.updateEcBillingStatement(updataOldBo);
            return Result.OK(addbo);
        }else{
            log.error("扣款费用明细不存在！");
            return Result.error("扣款费用明细不存在！");
        }
    }

    /**
     * 无明细退款
     *
     * @param paraAccount 增值账号
     * @return 结果
     */
    @Override
    public Result doRefundNoDetail(EcShopAccount paraAccount,CostTypeEnum costTypeEnum,BigDecimal resultCostMoney,String msg){
        if(StringUtils.isBlank(paraAccount.getCostType())){
            return Result.error("费用明细不能为空！");
        }
        EcShopAccount account = ecShopAccountMapper.selectEcShopAccountById(paraAccount.getId());
        if (account != null && StringUtils.isNotBlank(account.getId())) {
        } else {
            log.error("退款充值账号不能为空！");
            return Result.error("退款充值账号不能为空！");
        }

        // 修改账号剩余金额
        EcShopAccount ecShopAccountUpt = new EcShopAccount();
        ecShopAccountUpt.setId(account.getId());
        BigDecimal syMoney = account.getTotalMoney().add(resultCostMoney);
        ecShopAccountUpt.setTotalMoney(syMoney);
        ecShopAccountUpt.setUpdateTime(DateUtils.getTimestamp());
        ecShopAccountMapper.updateEcShopAccountMonery(ecShopAccountUpt);

        // 插入账户明细
        EcBillingStatement addbo = new EcBillingStatement();
        addbo.setId(StringUtils.getUUID());
        addbo.setBussType("3");
        addbo.setCostType(costTypeEnum.getCode());
        addbo.setRemark(msg);
        addbo.setStoreId(paraAccount.getShopId());
        addbo.setStoreName(paraAccount.getShopName());
        addbo.setDelFlag(0);
        addbo.setStatus("0");
        addbo.setAccountId(account.getId());
        addbo.setAccountName(account.getAccount());
        addbo.setCostMoney(resultCostMoney);
        addbo.setCreateBy(account.getCreateBy());
        addbo.setUpdateBy(account.getCreateBy());
        addbo.setCreateTime(DateUtils.getTimestamp());
        addbo.setUpdateTime(DateUtils.getTimestamp());
        addbo.setEpsId(account.getEpsId());
        addbo.setTenantId(account.getTenantId());
        ecBillingStatementMapper.insertEcBillingStatement(addbo);
        return  Result.OK();
    }
}
