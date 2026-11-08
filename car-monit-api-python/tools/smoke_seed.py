# -*- coding: utf-8 -*-
"""冒烟脚本的 ES 种子数据（P2-3 起经业务链路写入）。

此前 scripts/smoke_test.py 与 tools/smoke_all_routes.py 直接戳替身的类属性
``RestHighLevelClient._INDICES``——只对进程内替身有效。P2-3 引入真实 ES 适配后，
改为经 **EsIndexManageService.createIndexIfAbsent + RestHighLevelClient.index**
的业务链路写入，同一份代码在两种模式下都成立：

* shim（默认，未设 ``CAR_MONIT_ES_URL``）：写进程内替身索引，走 ES 的
  统一查询/统计/导出链路能拿到数据；
* 设了 ``CAR_MONIT_ES_URL``：同样的链路把索引（含 ngram mapping）与种子
  文档写进真实集群，冒烟与生产行为同一条代码路径。

种子文档与时间窗（2025-06-01 12:00:00，窗 2025-06-01 ~ 06-02）保持与历史
版本完全一致，冒烟断言不受影响。
"""
from __future__ import annotations

import json

#: snapshot_flow 的种子文档（字段与直写 _INDICES 的历史版本逐字段一致）
SMOKE_DOC = {
    "big_id": "smoke-1",
    "snapshottime": "2025-06-01 12:00:00",
    "platenumber": "赣A12345",
    "gantrycode": "G1",
}


def seed_es_via_business_chain() -> None:
    """经业务链路建三个索引并写入一条 snapshot 样例文档（幂等）。"""
    import bootstrap  # noqa: F401  镜像树 sys.path 引导（种子先于 app.main 导入）

    from org.elasticsearch.action.index.IndexRequest import IndexRequest
    from org.elasticsearch.client.RequestOptions import RequestOptions
    from org.elasticsearch.xcontent.XContentType import XContentType

    from com.ruoyi.base.service.optimization.EsIndexManageService import (
        EsIndexManageService,
    )

    service = EsIndexManageService()
    service.createIndexIfAbsent(service.snapshotIndex, "es/index/snapshot_flow.json")
    service.createIndexIfAbsent(service.feeIndex, "es/index/fee_records.json")
    service.createIndexIfAbsent(service.trailIndex, "es/index/trail_fitting.json")

    request = (IndexRequest(service.snapshotIndex)
               .id("smoke-1")
               .source(json.dumps(SMOKE_DOC, ensure_ascii=False), XContentType.JSON))
    service.esClient.index(request, RequestOptions.DEFAULT)
