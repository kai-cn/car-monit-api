# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.DwdLcztSfsjcxxController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/DwdLcztSfsjcxxController.java

收费站基础信息Controller

【Java→Python】关键差异
1) ``@RestController`` + ``@RequestMapping("/base/sfsjcxx")`` → 无 Web 容器，
   路由前缀保留为 ``BASE_PATH``，方法签名与 Java 一致（便于接入 Web 框架时注册）。
2) ``@Autowired`` 字段注入 → 构造器注入（缺省 ``DwdLcztSfsjcxxServiceImpl()``）。
3) ``@GetMapping`` 的 ``startPage()`` / ``getDataTable(...)`` → 调用 BaseController 同名方法。
4) ``@PathVariable("agentPk") String agentPk`` → 普通参数（Python 无注解）。
5) 局部变量 ``list`` → ``list_``（避免遮蔽内置 ``list``）。
"""
from __future__ import annotations

from typing import List, Optional

from com.ruoyi.base.domain.DwdLcztSfsjcxx import DwdLcztSfsjcxx
from com.ruoyi.base.service.IDwdLcztSfsjcxxService import IDwdLcztSfsjcxxService
from com.ruoyi.base.service.impl.DwdLcztSfsjcxxServiceImpl import DwdLcztSfsjcxxServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["DwdLcztSfsjcxxController"]


class DwdLcztSfsjcxxController(BaseController):
    """收费站基础信息Controller。"""

    # Java: @RequestMapping("/base/sfsjcxx")
    BASE_PATH = "/base/sfsjcxx"

    def __init__(self, dwdLcztSfsjcxxService: Optional[IDwdLcztSfsjcxxService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IDwdLcztSfsjcxxService dwdLcztSfsjcxxService;
        self.dwdLcztSfsjcxxService = dwdLcztSfsjcxxService or DwdLcztSfsjcxxServiceImpl()

    def list(self, dwdLcztSfsjcxx: DwdLcztSfsjcxx) -> TableDataInfo:
        """查询收费站基础信息列表。

        Java: @GetMapping("/list") → GET /base/sfsjcxx/list
        """
        self.startPage()
        list_ = self.dwdLcztSfsjcxxService.selectDwdLcztSfsjcxxList(dwdLcztSfsjcxx)
        return self.getDataTable(list_)

    def getInfo(self, agentPk: str) -> AjaxResult:
        """获取收费站基础信息详细信息。

        Java: @GetMapping(value = "/{agentPk}") → GET /base/sfsjcxx/{agentPk}
        """
        return AjaxResult.success(self.dwdLcztSfsjcxxService.selectDwdLcztSfsjcxxById(agentPk))

    def getListAll(self) -> List[DwdLcztSfsjcxx]:
        """获取收费站基础信息列表（不分页）。

        Java: @GetMapping(value = "/listAll") → GET /base/sfsjcxx/listAll
        """
        return self.dwdLcztSfsjcxxService.selectDwdLcztSfsjcxxList(DwdLcztSfsjcxx())
