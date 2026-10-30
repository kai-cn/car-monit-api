# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.DwdLcztSfzjcxxController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/DwdLcztSfzjcxxController.java

收费站基础信息Controller（sfzjcxx）

【Java→Python】关键差异
1) ``@RestController`` + ``@RequestMapping("/base/sfzjcxx")`` → 路由前缀保留为 ``BASE_PATH``。
2) ``@Autowired`` 字段注入 → 构造器注入（缺省 ``DwdLcztSfzjcxxServiceImpl()``）。
3) ``startPage()`` / ``getDataTable(...)`` → 调用 BaseController 同名方法。
4) ``@PathVariable("agentPk") String agentPk`` → 普通参数（Python 无注解）。
5) 局部变量 ``list`` → ``list_``（避免遮蔽内置 ``list``）。
"""
from __future__ import annotations

from typing import List, Optional

from com.ruoyi.base.domain.DwdLcztSfzjcxx import DwdLcztSfzjcxx
from com.ruoyi.base.service.IDwdLcztSfzjcxxService import IDwdLcztSfzjcxxService
from com.ruoyi.base.service.impl.DwdLcztSfzjcxxServiceImpl import DwdLcztSfzjcxxServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["DwdLcztSfzjcxxController"]


class DwdLcztSfzjcxxController(BaseController):
    """收费站基础信息Controller（sfzjcxx）。"""

    # Java: @RequestMapping("/base/sfzjcxx")
    BASE_PATH = "/base/sfzjcxx"

    def __init__(self, dwdLcztSfzjcxxService: Optional[IDwdLcztSfzjcxxService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IDwdLcztSfzjcxxService dwdLcztSfzjcxxService;
        self.dwdLcztSfzjcxxService = dwdLcztSfzjcxxService or DwdLcztSfzjcxxServiceImpl()

    def list(self, dwdLcztSfzjcxx: DwdLcztSfzjcxx) -> TableDataInfo:
        """查询收费站基础信息列表。

        Java: @GetMapping("/list") → GET /base/sfzjcxx/list
        """
        self.startPage()
        list_ = self.dwdLcztSfzjcxxService.selectDwdLcztSfzjcxxList(dwdLcztSfzjcxx)
        return self.getDataTable(list_)

    def getInfo(self, agentPk: str) -> AjaxResult:
        """获取收费站基础信息详细信息。

        Java: @GetMapping(value = "/{agentPk}") → GET /base/sfzjcxx/{agentPk}
        """
        return AjaxResult.success(self.dwdLcztSfzjcxxService.selectDwdLcztSfzjcxxById(agentPk))

    def getListAll(self) -> List[DwdLcztSfzjcxx]:
        """获取收费站基础信息列表（不分页）。

        Java: @GetMapping(value = "/listAll") → GET /base/sfzjcxx/listAll
        """
        return self.dwdLcztSfzjcxxService.selectDwdLcztSfzjcxxList(DwdLcztSfzjcxx())
