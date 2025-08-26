package com.ruoyi.modules.vo.orders;

import com.ruoyi.modules.vo.orders.operatesign.*;
import lombok.Data;

@Data
public class OperateSignVO {

    private AfterSale afterSale;
    private ApplyRefund applyRefund;
    private AuctionOrdersInfo auctionOrdersInfo;
    private BindQualityAssuranceCode bindQualityAssuranceCode;
    private BindSerialNumber bindSerialNumber;
    private C2mCustomInfo c2mCustomInfo;
    private C2mOrderSampleInfo c2mOrderSampleInfo;
    private CancelLogistics cancelLogistics;
    private CancelWaybill cancelWaybill;
    private ChangePrice changePrice;
    private CustomerReject customerReject;
    private CiscountDetails discountDetails;
    private FlowerStoreTransfer flowerStoreTransfer;
    private GoldWeighEnter goldWeighEnter;
    private InnerShip innerShip;
    private JewelryCertificate jewelryCertificate;
    private LocHouseContract locHouseContract;
    private ModifyFreight modifyFreight;
    private ModifyPackageNum modifyPackageNum;
    private OrderAddress orderAddress;
    private OrderSignAudit orderSignAudit;
    private OverseasOut overseasOut;
    private PaymentRecord paymentRecord;
    private PhoneSequence phoneSequence;
    private PlatformFreightPay platformFreightPay;
    private QueryPlatformFreight queryPlatformFreight;
    private ReUploadOrderSign reUploadOrderSign;
    private Refundment refundment;
    private ShowCuiDanDetail showCuiDanDetail;
    private ShowDelayDelivery showDelayDelivery;
    private ShowPlatformFreight showPlatformFreight;
    private ShowReplyCuiDan showReplyCuiDan;
    private ShowRetain showRetain;
    private ShowSplitOrder showSplitOrder;
    private SmallPayment smallPayment;
    private StockOut stockOut;
    private UploadOrderSign uploadOrderSign;
    private VenderRemark venderRemark;
    private VerifyOrder verifyOrder;
    private ViewConsignmentOrder viewConsignmentOrder;
    private WaybillNo waybillNo;
    private String orderId;
}
