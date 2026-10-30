# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.DwdLcztFwqjcxxController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/DwdLcztFwqjcxxController.java

服务区基础信息Controller

【Java→Python】关键差异
1) ``@RestController`` + ``@RequestMapping("/base/fwqjcxx")``：Python 无 Web 容器，
   路由前缀保留为类常量 ``BASE_PATH``（方法注释里写全 ``GET 路径``），
   方法签名与 Java 完全一致 —— 接入 FastAPI/Flask 时按这些常量注册即可。
2) ``@Autowired private IDwdLcztFwqjcxxService ...`` → 构造器注入，
   缺省 ``DwdLcztFwqjcxxServiceImpl()``（等价 Spring 单例 Bean）。
3) ``@GetMapping("/list")`` 的 ``startPage()`` + ``getDataTable(list)`` →
   直接调用 BaseController 的同名方法（分页靠 PageUtils 线程局部变量，与 Java 同构）。
4) ``@PathVariable("agentPk") String agentPk`` → Python 普通参数 ``agentPk``
   （无注解机制，类型由标注 + 调用方保证）。
5) ``List<X> list`` 局部变量 → ``list_``：Python 里 ``list`` 是内置类型名，
   遮蔽后会让同作用域的 ``list(...)`` 调用报错，故原工程惯例加下划线。
6) ``new DwdLcztFwqjcxx()`` 作为“空查询条件” → 无参构造实体（字段全 None）。
"""
from __future__ import annotations

from typing import List, Optional

from com.ruoyi.base.domain.DwdLcztFwqjcxx import DwdLcztFwqjcxx
from com.ruoyi.base.service.IDwdLcztFwqjcxxService import IDwdLcztFwqjcxxService
from com.ruoyi.base.service.impl.DwdLcztFwqjcxxServiceImpl import DwdLcztFwqjcxxServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["DwdLcztFwqjcxxController"]


class DwdLcztFwqjcxxController(BaseController):
    """服务区基础信息Controller。"""

    # Java: @RequestMapping("/base/fwqjcxx")
    BASE_PATH = "/base/fwqjcxx"

    def __init__(self, dwdLcztFwqjcxxService: Optional[IDwdLcztFwqjcxxService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IDwdLcztFwqjcxxService dwdLcztFwqjcxxService;
        self.dwdLcztFwqjcxxService = dwdLcztFwqjcxxService or DwdLcztFwqjcxxServiceImpl()

    def list(self, dwdLcztFwqjcxx: DwdLcztFwqjcxx) -> TableDataInfo:
        """查询服务区基础信息列表。

        Java: @GetMapping("/list") → GET /base/fwqjcxx/list
        """
        self.startPage()
        list_ = self.dwdLcztFwqjcxxService.selectDwdLcztFwqjcxxList(dwdLcztFwqjcxx)
        return self.getDataTable(list_)

    def getInfo(self, agentPk: str) -> AjaxResult:
        """获取服务区基础信息详细信息。

        Java: @GetMapping(value = "/{agentPk}") → GET /base/fwqjcxx/{agentPk}
        """
        return AjaxResult.success(self.dwdLcztFwqjcxxService.selectDwdLcztFwqjcxxById(agentPk))

    def getListAll(self) -> List[DwdLcztFwqjcxx]:
        """获取服务区基础信息列表（不分页）。

        Java: @GetMapping(value = "/listAll") → GET /base/fwqjcxx/listAll
        """
        return self.dwdLcztFwqjcxxService.selectDwdLcztFwqjcxxList(DwdLcztFwqjcxx())
