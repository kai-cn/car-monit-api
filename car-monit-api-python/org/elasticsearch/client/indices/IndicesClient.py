# -*- coding: utf-8 -*-
"""org.elasticsearch.client.indices.ElasticsearchIndicesClient

【无 Java 源文件：框架类替身】
Java 侧是 ``org.elasticsearch.client.RestHighLevelClient#indices()`` 返回的
``ElasticsearchIndicesClient``（实现 ``IndicesClient`` 接口），包路径
``org.elasticsearch.client.indices``。

本工程用法（EsIndexManageService）：
    esClient.indices().exists(existsReq, RequestOptions.DEFAULT)
    esClient.indices().create(createReq, RequestOptions.DEFAULT)
    esClient.indices().delete(deleteReq, RequestOptions.DEFAULT)
    esClient.indices().updateAliases(request, RequestOptions.DEFAULT)

【Java→Python 关键差异】
1) Java 的索引操作最终是**对 ES 集群发 HTTP 请求**；替身把“集群状态”放在
   ``RestHighLevelClient`` 的类属性里（跨实例共享，模拟外部集群）：
     - `_INDEX_METADATA`：index -> {source, settings, aliases}
     - `_INDICES`：index -> {doc_id: _source}（文档，见 RestHighLevelClient）
2) Java 的 ``exists`` 语义：传入多个索引时，**全部存在**才返回 true；
   替身同样要求全部命中。
3) Java 的 ``create`` 在索引已存在时抛 ``ResourceAlreadyExistsException``；
   `EsIndexManageService` 先 exists 再 create，因此替身只在重复创建时
   抛 ``ValueError``（能暴露调用顺序错误，但不影响正常路径）。
4) 所有方法都接受 ``RequestOptions`` 参数（Java 签名要求），替身忽略它。
"""

from __future__ import annotations

from typing import Any, List, Optional

from org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest import (
    AliasActions,
    IndicesAliasesRequest,
)
from org.elasticsearch.action.admin.indices.delete.DeleteIndexRequest import (
    DeleteIndexRequest,
)
from org.elasticsearch.action.support.master.AcknowledgedResponse import (
    AcknowledgedResponse,
)
from org.elasticsearch.client.indices.CreateIndexRequest import CreateIndexRequest
from org.elasticsearch.client.indices.CreateIndexResponse import CreateIndexResponse
from org.elasticsearch.client.indices.GetIndexRequest import GetIndexRequest

from app.runtime import reject_shim_operation

__all__ = ["IndicesClient"]


class IndicesClient(object):
    """``ElasticsearchIndicesClient`` 的替身（索引级管理操作）。"""

    def __init__(self, owner: Any) -> None:
        #: 持有 RestHighLevelClient，用它的类属性作为“集群元数据”
        self._owner = owner

    # ------------------------------------------------------------------ 存在性
    def exists(self, request: GetIndexRequest, options: Any = None) -> bool:
        """对应 ``exists(GetIndexRequest, RequestOptions)``。"""
        # P0-2：prod 模式下拒绝“假存在性”（内存元数据 ≠ 集群状态；抛错由
        # EsIndexManageService.init 的 catch 吞掉告警，与 Java-ES-宕机一致）。
        reject_shim_operation(
            "IndicesClient.exists",
            "（真实 ES 适配器未实现，存在性检查不会发往集群。）")
        self._ensureAvailable()
        status = self._owner
        for index_name in request.indices():
            if (index_name not in status._INDEX_METADATA
                    and index_name not in status._INDICES):
                return False
        return True

    # ------------------------------------------------------------------ 创建
    def create(self, request: CreateIndexRequest,
               options: Any = None) -> CreateIndexResponse:
        """对应 ``create(CreateIndexRequest, RequestOptions)``。"""
        # P0-2：prod 模式下拒绝“假创建”。
        reject_shim_operation(
            "IndicesClient.create",
            "（真实 ES 适配器未实现，索引不会在集群创建。）")
        self._ensureAvailable()
        index_name = request.index()
        metadata = self._owner._INDEX_METADATA
        if index_name in metadata:
            # 对应 ResourceAlreadyExistsException（RuntimeException）
            raise ValueError("resource_already_exists_exception: index [%s]" % index_name)
        metadata[index_name] = {
            "source": request.getSource(),
            "settings": request.getSettings(),
            "aliases": [],
        }
        return CreateIndexResponse(index_name, True)

    # ------------------------------------------------------------------ 删除
    def delete(self, request: DeleteIndexRequest,
               options: Any = None) -> AcknowledgedResponse:
        """对应 ``delete(DeleteIndexRequest, RequestOptions)``。"""
        # P0-2：prod 模式下拒绝“假删除”。
        reject_shim_operation(
            "IndicesClient.delete",
            "（真实 ES 适配器未实现，索引不会在集群删除。）")
        self._ensureAvailable()
        for index_name in request.indices():
            self._owner._INDEX_METADATA.pop(index_name, None)
            # 同步清空文档存储（真实 ES 删索引会连带删除数据）
            self._owner._INDICES.pop(index_name, None)
        return AcknowledgedResponse(True)

    # ------------------------------------------------------------------ 别名
    def updateAliases(self, request: IndicesAliasesRequest,
                      options: Any = None) -> AcknowledgedResponse:
        """对应 ``updateAliases(IndicesAliasesRequest, RequestOptions)``。"""
        # P0-2：prod 模式下拒绝“假别名更新”。
        reject_shim_operation(
            "IndicesClient.updateAliases",
            "（真实 ES 适配器未实现，别名不会在集群更新。）")
        self._ensureAvailable()
        metadata = self._owner._INDEX_METADATA
        for action in request.getAliasActions():
            for index_name in action.getIndices():
                entry = metadata.setdefault(index_name, {
                    "source": None, "settings": None, "aliases": []})
                for alias_name in action.getAliases():
                    if action.getType() is AliasActions.Type.ADD:
                        if alias_name not in entry["aliases"]:
                            entry["aliases"].append(alias_name)
                    elif action.getType() is AliasActions.Type.REMOVE:
                        if alias_name in entry["aliases"]:
                            entry["aliases"].remove(alias_name)
        return AcknowledgedResponse(True)

    # ------------------------------------------------------------------ 内部
    def _ensureAvailable(self) -> None:
        if not self._owner.available:
            raise ConnectionError("Connection refused: 模拟 Elasticsearch 集群不可用")

    def __repr__(self) -> str:
        return "IndicesClient(owner=%r)" % (self._owner,)
