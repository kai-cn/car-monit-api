# -*- coding: utf-8 -*-
"""org.elasticsearch.client.RestHighLevelClient

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.client.RestHighLevelClient``。
本工程用法：
    - ElasticsearchConfig.restHighLevelClient()：new RestHighLevelClient(RestClient.builder(...))
    - DataProcessService.insertIntoEs()：client.index(request, RequestOptions.DEFAULT)
    - EsQueryService.queryFromEs()：client.search(request, RequestOptions.DEFAULT)
    - ElasticsearchConfig：client.ping(RequestOptions.DEFAULT)
    - LargeScaleDataSyncService：client.bulkAsync(request, RequestOptions.DEFAULT, listener)

【Java→Python】关键差异（影响面最大的一个替身）
1) **集群存储放在类属性上**：真实 ES 是一个外部集群，DataProcessService 写入的数据
   EsQueryService 能查到，哪怕两者持有不同的 client 实例。替身用
   ``RestHighLevelClient._INDICES``（类级 dict）模拟这一“跨实例共享”的语义，
   保证“写入→查询”链路在进程内闭合。测试可用 ``resetStore()`` 清空。
2) **查询在客户端执行**：真实 ES 把 QueryBuilder 序列化成 DSL 交给服务端；
   替身没有网络层，直接调用 ``query.matches(document)`` 在进程内过滤
   （见 QueryBuilder.py 的说明）。文档按**插入顺序**返回（ES 默认按 _score 再按 _doc）。
3) **异常语义**：真实客户端在网络/集群异常时抛 ``IOException``（受检）或
   ``ElasticsearchException``（运行时）；替身统一抛 ``ConnectionError``，
   使 ``EsQueryService.query`` 的 ``catch (Exception e)`` 降级分支可以被触发。
   可用实例/类属性 ``available = False`` 注入“ES 不可用”。
   **索引不存在**是另一类异常：真实 ES 返回 HTTP 404 ``index_not_found_exception``，
   客户端抛 ``ElasticsearchStatusException``（见 ``_resolveIndices``），
   替身同样抛出，不能默默返回空结果。
4) Java 的 ``index`` / ``search`` 都有多个重载（带 RequestOptions / 不带）；
   替身把 ``options`` 设为可选参数，调用写法不受影响。
5) ``ping`` 在 Java 里返回 boolean 且**可能抛异常**（连接失败时抛 IOException，
   而不是返回 false）；替身保持“可用返回 True、不可用抛 ConnectionError”。
6) ``close()`` 在 Java 里来自 ``Closeable``；替身转发给内部 RestClient。
7) **聚合在本地求值**：``search`` 对**全部命中文档**调用
   ``AggregationBuilder.aggregate(...)``，结果放进 ``SearchResponse.getAggregations()``。
   真实 ES 由各分片并行聚合后再 reduce；两者在“聚合只看命中集合、与 from/size 无关”
   这一点上一致，因此 ``size(0)`` 只取聚合的行为完全对齐。
8) **scroll 游标存在进程内**：``search`` 检测到 ``request.getScroll() != null`` 时，
   首页返回前 ``size`` 条、其余登记到 ``_SCROLLS``（类属性，模拟服务端 search context）；
   ``scroll(request)`` 逐批取走，``clearScroll(request)`` 释放。
   真实 ES 按 keepAlive 超时回收上下文，替身**不做过期回收**（进程内数据量有限）；
   游标耗尽后继续 ``scroll`` 返回空 page（与 ES 一致，不抛异常）。
9) **P2-3 真实后端挂载**：设置 ``CAR_MONIT_ES_URL`` 后，本类构造时挂载
   :class:`app.middleware.real_es.RealEsBackend`（进程级共享，等价 Java 里
   多个服务注入同一个 Bean）。此后 ``index``/``bulkAsync``/``search``/
   ``scroll``/``clearScroll``/``ping`` 全部翻译成真实 REST/DSL 发往集群，
   响应重建回本模块的替身对象——业务代码零改动。未设置 URL 时行为与
   纯替身完全一致（P0-2 守卫也只在此路径触发）。原进程内存实现抽到
   ``_*_memory`` 私有方法，供真实后端“熔断降级为进程内存”时复用
   （见 real_es.py 的降级语义说明）。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from org.elasticsearch.action.bulk.BulkItemResponse import BulkItemResponse
from org.elasticsearch.action.bulk.BulkRequest import BulkRequest
from org.elasticsearch.action.bulk.BulkResponse import BulkResponse
from org.elasticsearch.action.index.IndexRequest import IndexRequest
from org.elasticsearch.action.index.IndexResponse import IndexResponse
from org.elasticsearch.action.search.ClearScrollRequest import ClearScrollRequest
from org.elasticsearch.action.search.ClearScrollResponse import ClearScrollResponse
from org.elasticsearch.action.search.SearchRequest import SearchRequest
from org.elasticsearch.action.search.SearchResponse import SearchResponse
from org.elasticsearch.action.search.SearchScrollRequest import SearchScrollRequest
from org.elasticsearch.client.RestClient import RestClient, RestClientBuilder
from org.elasticsearch.client.indices.IndicesClient import IndicesClient
from org.elasticsearch.ElasticsearchException import index_not_found_exception
from org.elasticsearch.search.SearchHit import SearchHit
from org.elasticsearch.search.SearchHits import SearchHits
from org.elasticsearch.search.aggregations.Aggregations import Aggregations
from org.elasticsearch.search.builder.SearchSourceBuilder import SearchSourceBuilder

from app.runtime import reject_shim_operation

__all__ = ["RestHighLevelClient"]


class RestHighLevelClient(object):
    """``RestHighLevelClient`` 的进程内替身（内存索引 + 客户端侧查询）。"""

    #: 模拟 ES 集群：index -> {doc_id: _source JSON 文本}（dict 保序 = 插入顺序）
    _INDICES: Dict[str, Dict[str, str]] = {}
    #: 模拟索引元数据（EsIndexManageService 的 create/delete/updateAliases）：
    #: index -> {"source": 建索引请求体, "settings": ILM settings, "aliases": [...]}
    _INDEX_METADATA: Dict[str, Dict[str, Any]] = {}
    #: 模拟文档版本号：(index, doc_id) -> version
    _VERSIONS: Dict[tuple, int] = {}
    #: 模拟已打开的 scroll 游标：scrollId -> {hits/position/size/total}
    _SCROLLS: Dict[str, Dict[str, Any]] = {}
    #: scrollId 自增序号（真实 ES 由服务端生成 base64 串）
    _SCROLL_SEQ: int = 0
    #: 模拟集群可用性；置 False 后所有请求抛 ConnectionError
    available: bool = True

    def __init__(self, rest_client: Any) -> None:
        # Java 有两个构造器：RestHighLevelClient(RestClientBuilder) / (RestClient)
        if isinstance(rest_client, RestClientBuilder):
            self.restClient: RestClient = rest_client.build()
        elif isinstance(rest_client, RestClient):
            self.restClient = rest_client
        else:
            raise TypeError(
                "RestHighLevelClient 需要 RestClientBuilder 或 RestClient，实际为 "
                + type(rest_client).__name__)
        self.closed = False
        # P2-3：CAR_MONIT_ES_URL 设置时挂载真实 ES 后端（惰性 import 避免循环依赖；
        # 进程级共享，等价 Java 里多个服务注入同一个 RestHighLevelClient Bean）。
        from app.middleware.real_es import shared_es_backend
        self._real = shared_es_backend()

    # ------------------------------------------------------------------ 连接检测
    def ping(self, options: Any = None) -> bool:
        """对应 ``ping(RequestOptions)``。"""
        if self._real is not None:
            return self._real.ping(memory=lambda: True)
        self._ensureAvailable()
        return True

    # ------------------------------------------------------------------ 子客户端
    def indices(self) -> IndicesClient:
        """对应 ``IndicesClient indices()``：返回索引管理客户端。

        【Java→Python】真实 HLRC 每次调用 ``indices()`` 都新建一个轻量包装对象；
        替身保持一致（无状态，真正状态在类的类属性上）。
        """
        return IndicesClient(self)

    def getLowLevelClient(self) -> RestClient:
        """对应 ``RestClient getLowLevelClient()``：暴露低层 REST 客户端。

        EsIndexManageService 用它发 ILM 相关的原生 REST 请求
        （HLRC 7.17 没有 ILM 高层 API）。
        """
        return self.restClient

    # ------------------------------------------------------------------ 写入
    def index(self, request: IndexRequest,
              options: Any = None) -> IndexResponse:
        """对应 ``index(IndexRequest, RequestOptions)``。"""
        if self._real is not None:
            return self._real.index(
                request, memory=lambda: self._index_memory(request))
        # P0-2：prod 模式下拒绝“假写入”（文档只会进进程内存，集群收不到）。
        reject_shim_operation(
            "RestHighLevelClient.index",
            "（真实 ES 适配器未实现，文档不会写入集群。）")
        self._ensureAvailable()
        return self._index_memory(request)

    def _index_memory(self, request: IndexRequest) -> IndexResponse:
        """进程内存实现（P2-3 抽出：真实后端熔断降级时复用同一份逻辑）。"""
        index_name = request.index()
        doc_id = request.getId()
        source = request.getSource()
        if source is None:
            # 真实 ES 会拒绝空 _source；这里抛 ValueError 对应 IllegalArgumentException
            raise ValueError("IndexRequest.source 不能为空")

        store = self._INDICES.setdefault(index_name, {})
        if doc_id is None:
            # 真实 ES 未指定 id 时自动生成；替身用递增序号模拟
            doc_id = str(len(store) + 1)
        existed = doc_id in store
        version = self._VERSIONS.get((index_name, doc_id), 0) + 1
        store[doc_id] = source
        self._VERSIONS[(index_name, doc_id)] = version
        return IndexResponse(index_name, doc_id,
                             "UPDATED" if existed else "CREATED", version)

    def bulkAsync(self, request: BulkRequest, options: Any = None,
                  listener: Any = None) -> Optional[BulkResponse]:
        """对应 ``bulkAsync(BulkRequest, RequestOptions, ActionListener<BulkResponse>)``。

        【Java→Python】真实 `bulkAsync` 把批次异步发给集群，完成后在 IO 线程回调
        listener；替身**同步执行**：逐条调用 `index(...)` 落库，构造 `BulkResponse`
        后立即回调 listener（见 BulkProcessor.py 文件头第 1 条）。

        语义对齐点：Java 的 bulk 是“部分失败”语义 —— 单条文档失败只会体现在
        对应 `BulkItemResponse` 上，不会中断整个批次；替身同样逐条 try/except。
        """
        if self._real is not None:
            return self._real.bulkAsync(
                request, listener,
                memory=lambda: self._bulkAsync_memory(request, listener))
        # P0-2：prod 模式下拒绝“假写入”（bulkAsync 内部逐条调用 index，此处统一拦截）。
        reject_shim_operation(
            "RestHighLevelClient.bulkAsync",
            "（真实 ES 适配器未实现，批次不会写入集群。）")
        self._ensureAvailable()
        return self._bulkAsync_memory(request, listener)

    def _bulkAsync_memory(self, request: BulkRequest,
                          listener: Any) -> BulkResponse:
        """进程内存实现（P2-3 抽出）。"""
        items: List[BulkItemResponse] = []
        for action in request.requests():
            try:
                self._index_memory(action)
                items.append(BulkItemResponse(action.getId(), False, None))
            except Exception as error:  # noqa: BLE001 - 单条失败不影响整批
                items.append(BulkItemResponse(action.getId(), True, str(error)))
        response = BulkResponse(items)
        # 【Java→Python】Java 的 listener 可能为 null（重载）；替身同样允许
        if listener is not None:
            listener.onResponse(response)
        return response

    # ------------------------------------------------------------------ 查询
    def search(self, request: SearchRequest,
               options: Any = None) -> SearchResponse:
        """对应 ``search(SearchRequest, RequestOptions)``。"""
        if self._real is not None:
            return self._real.search(
                request, memory=lambda: self._search_memory(request))
        # P0-2：prod 模式下拒绝“假查询”（内存索引 ≠ 集群数据，查出的结果是错的；
        # 抛错后 UnifiedQueryService 走 MySQL 降级，与 Java-ES-宕机一致）。
        reject_shim_operation(
            "RestHighLevelClient.search",
            "（真实 ES 适配器未实现，查询不会发往集群。）")
        self._ensureAvailable()
        return self._search_memory(request)

    def _search_memory(self, request: SearchRequest) -> SearchResponse:
        """进程内存实现（P2-3 抽出：真实后端熔断降级时复用同一份逻辑）。"""
        builder: Optional[SearchSourceBuilder] = request.getSource()
        query = builder.getQuery() if builder is not None else None
        skip = builder.getFrom() if builder is not None else 0
        size = builder.getSize() if builder is not None else SearchSourceBuilder.DEFAULT_SIZE

        index_names: List[str] = self._resolveIndices(request.indices())
        matched: List[SearchHit] = []
        documents: List[Dict[str, Any]] = []
        for index_name in index_names:
            for doc_id, source in self._INDICES.get(index_name, {}).items():
                try:
                    document = json.loads(source) if source else {}
                except ValueError:
                    # 真实 ES 在写入阶段就会拒绝非法 JSON；替身保守跳过坏文档
                    continue
                if query is not None and not query.matches(document):
                    continue
                matched.append(SearchHit(index_name, doc_id, source))
                documents.append(document)

        total = len(matched)
        # 【Java→Python】聚合作用于**全部命中文档**，与 from/size 无关
        # （ES 在分片上聚合后再 reduce；size(0) 只取聚合就是靠这个语义）
        aggregations = Aggregations({
            agg_builder.getName(): agg_builder.aggregate(documents)
            for agg_builder in
            (builder.getAggregationBuilders() if builder is not None else [])
        })

        scroll = request.getScroll()
        if scroll is not None:
            # 游标查询：首页取 size 条，剩余登记到游标上下文（见 scroll()）
            batch_size = max(size, 0) if size is not None else SearchSourceBuilder.DEFAULT_SIZE
            page = matched[:batch_size]
            scroll_id = self._openScroll(matched[batch_size:], batch_size, total)
            return SearchResponse(SearchHits(page, total),
                                  aggregations=aggregations,
                                  scroll_id=scroll_id)

        # ES 语义：from 是偏移量、size 是返回条数（size=0 时只返回聚合）
        page = matched[skip:skip + max(size, 0)] if size is not None else matched[skip:]
        return SearchResponse(SearchHits(page, total), aggregations=aggregations)

    # ------------------------------------------------------------------ 索引解析
    def _resolveIndices(self, names: List[str]) -> List[str]:
        """把请求里的索引名/别名解析成实际索引名。

        【Java→Python】真实 ES 由服务端解析：不存在的索引直接返回 HTTP 404
        ``index_not_found_exception``，客户端抛异常。替身必须复刻这个行为，
        否则 ``UnifiedQueryService.query`` 的 “ES 失败降级 MySQL” 分支永远不会触发
        （实测：``/api/v1/large/snapshot`` Java 10 条 / Python 0 条）。

        未指定索引（``request.indices()`` 为空）时搜全部，与 ES 一致，不报错。
        """
        if not names:
            return list(self._INDICES.keys())
        resolved: List[str] = []
        for name in names:
            if name in self._INDICES or name in self._INDEX_METADATA:
                resolved.append(name)
                continue
            # 别名 -> 真实索引（真实 ES 在服务端展开别名）
            aliased = [index_name for index_name, entry
                       in self._INDEX_METADATA.items()
                       if name in (entry or {}).get("aliases", [])]
            if aliased:
                resolved.extend(aliased)
                continue
            raise index_not_found_exception(name)
        return resolved

    def scroll(self, request: SearchScrollRequest,
               options: Any = None) -> SearchResponse:
        """对应 ``scroll(SearchScrollRequest, RequestOptions)``：取下一批。

        【Java→Python】真实 ES 靠 scrollId 找回服务端 search context；替身从
        ``_SCROLLS`` 里取出剩余文档，按首页的 batch size 切片返回。
        游标已被 clear（或 id 非法）时，ES 抛 ``SearchContextMissingException``，
        替身抛 ``ValueError``。
        """
        if self._real is not None:
            return self._real.scroll(
                request, memory=lambda: self._scroll_memory(request))
        # P0-2：prod 模式下拒绝“假游标”（进程内 _SCROLLS ≠ 集群 search context）。
        reject_shim_operation(
            "RestHighLevelClient.scroll",
            "（真实 ES 适配器未实现，游标不会发往集群。）")
        self._ensureAvailable()
        return self._scroll_memory(request)

    def _scroll_memory(self, request: SearchScrollRequest) -> SearchResponse:
        """进程内存实现（P2-3 抽出）。"""
        scroll_id = request.scrollId()
        cursor = self._SCROLLS.get(scroll_id)
        if cursor is None:
            # 对应 SearchContextMissingException（No search context found for id）
            raise ValueError(
                "No search context found for id [%s]" % scroll_id)
        start = cursor["position"]
        end = start + cursor["size"]
        page = cursor["hits"][start:end]
        cursor["position"] = end
        return SearchResponse(SearchHits(page, cursor["total"]),
                              scroll_id=scroll_id)

    def clearScroll(self, request: ClearScrollRequest,
                    options: Any = None) -> ClearScrollResponse:
        """对应 ``clearScroll(ClearScrollRequest, RequestOptions)``：释放游标。"""
        if self._real is not None:
            return self._real.clearScroll(
                request, memory=lambda: self._clearScroll_memory(request))
        self._ensureAvailable()
        return self._clearScroll_memory(request)

    def _clearScroll_memory(self, request: ClearScrollRequest) -> ClearScrollResponse:
        """进程内存实现（P2-3 抽出）。"""
        freed = 0
        for scroll_id in request.getScrollIds():
            if self._SCROLLS.pop(scroll_id, None) is not None:
                freed += 1
        return ClearScrollResponse(True, freed)

    # ------------------------------------------------------------------ 生命周期
    def close(self) -> None:
        self.closed = True
        self.restClient.close()

    # ------------------------------------------------------------------ 内部
    @classmethod
    def _openScroll(cls, remaining: List[SearchHit], batch_size: int,
                    total: int) -> str:
        """登记一个新的 scroll 游标（Java 无此方法：服务端行为，替身在本地模拟）。"""
        cls._SCROLL_SEQ += 1
        scroll_id = "scroll-%d" % cls._SCROLL_SEQ
        cls._SCROLLS[scroll_id] = {
            "hits": list(remaining),
            "position": 0,
            "size": batch_size,
            "total": total,
        }
        return scroll_id

    def _ensureAvailable(self) -> None:
        if not self.available:
            # 对应 java.net.ConnectException / IOException: Connection refused
            raise ConnectionError(
                "Connection refused: 模拟 Elasticsearch 集群不可用")

    # ------------------------------------------------------------------ 测试辅助
    @classmethod
    def resetStore(cls) -> None:
        """清空“集群”数据（Java 无此方法，仅供测试隔离）。"""
        cls._INDICES.clear()
        cls._INDEX_METADATA.clear()
        cls._VERSIONS.clear()
        cls._SCROLLS.clear()
        cls._SCROLL_SEQ = 0
        RestClient.resetIlmPolicies()
        cls.available = True

    @classmethod
    def documents(cls, index_name: str) -> Dict[str, Any]:
        """查看某索引下的文档（Java 无此方法，仅供测试断言）。"""
        return {doc_id: json.loads(source)
                for doc_id, source in cls._INDICES.get(index_name, {}).items()}

    def __repr__(self) -> str:
        return "RestHighLevelClient(%r)" % (self.restClient,)
