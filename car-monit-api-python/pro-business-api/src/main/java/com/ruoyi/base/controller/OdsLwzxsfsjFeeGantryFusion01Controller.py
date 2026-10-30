# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsLwzxsfsjFeeGantryFusion01Controller

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeGantryFusion01Controller.java

交易流水Controller（门架融合流水）

【Java→Python】关键差异（本文件有 3 处非模板逻辑，务必注意）
1) **列表回填 id**：``for (OdsLwzxsfsjFeeGantryFusion01 rtn : list) rtn.setId(StringUtils.getUUID());``
   Java 增强 for 循环 → Python ``for ... in list_``（元素是同一对象引用，setId 生效）；
   ``StringUtils.getUUID()`` 保留原工具类调用（不用 ``uuid.uuid4()``，保证与 Java 同源）。
2) **getInfo 不包 AjaxResult**：Java 直接 ``return service.select...ById(bigId);``
   —— 序列化由 Jackson 处理。Python 保持**直接返回实体**，不额外包 AjaxResult
   （若包了会改变 JSON 结构，属于行为变更）。
3) ``StringUtils`` 的 import 来自 ``com.ruoyi.common.utils.StringUtils``（工具类静态方法）。
4) 其余：``@Autowired`` → 构造器注入；``@PathVariable("bigId") String bigId`` → 普通参数；
   局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.OdsLwzxsfsjFeeGantryFusion01 import OdsLwzxsfsjFeeGantryFusion01
from com.ruoyi.base.service.IOdsLwzxsfsjFeeGantryFusion01Service import \
    IOdsLwzxsfsjFeeGantryFusion01Service
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeGantryFusion01ServiceImpl import \
    OdsLwzxsfsjFeeGantryFusion01ServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo
from com.ruoyi.common.utils.StringUtils import StringUtils

__all__ = ["OdsLwzxsfsjFeeGantryFusion01Controller"]


class OdsLwzxsfsjFeeGantryFusion01Controller(BaseController):
    """交易流水Controller（门架融合）。"""

    # Java: @RequestMapping("/base/feeGantry")
    BASE_PATH = "/base/feeGantry"

    def __init__(self,
                 odsLwzxsfsjFeeGantryFusion01Service:
                 Optional[IOdsLwzxsfsjFeeGantryFusion01Service] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsLwzxsfsjFeeGantryFusion01Service ...;
        self.odsLwzxsfsjFeeGantryFusion01Service = (
            odsLwzxsfsjFeeGantryFusion01Service or OdsLwzxsfsjFeeGantryFusion01ServiceImpl())

    def list(self, odsLwzxsfsjFeeGantryFusion01: OdsLwzxsfsjFeeGantryFusion01) -> TableDataInfo:
        """查询交易流水列表（GET /base/feeGantry/list）。"""
        self.startPage()
        list_ = self.odsLwzxsfsjFeeGantryFusion01Service \
            .selectOdsLwzxsfsjFeeGantryFusion01List(odsLwzxsfsjFeeGantryFusion01)
        # 【Java→Python】Java 的 `null != list && list.size() > 0` → Python 的 `list_`
        # 空列表即 falsy，``if list_:`` 与 ``list_ is not None and len(list_) > 0`` 等价。
        if list_ is not None and len(list_) > 0:
            for rtn in list_:
                # 列表项本身没有 id 时，用 UUID 临时回填给前端做行标识
                rtn.setId(StringUtils.getUUID())
        return self.getDataTable(list_)

    def getInfo(self, bigId: str) -> OdsLwzxsfsjFeeGantryFusion01:
        """获取交易流水详细信息（GET /base/feeGantry/{bigId}）。

        【Java→Python】Java 返回**裸实体**（不经 AjaxResult 包装），Python 同样直接返回实体。
        """
        return self.odsLwzxsfsjFeeGantryFusion01Service \
            .selectOdsLwzxsfsjFeeGantryFusion01ById(bigId)
