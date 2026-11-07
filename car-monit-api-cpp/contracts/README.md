# 契约测试（P5）

本目录保存端点契约基线，供“Java ↔ C++”响应 diff 使用。

## 现状（2026-11-08）

- `endpoints.golden.json`：由 `carmonit_tests::test_contract_routes_golden` 生成并校验，
  覆盖 **87 条路由**（85 个业务端点 + `/health`、`/metrics`），字段为
  `method` / `path` / `kind`：
  - `table`：列表端点（`/list`、`/listToExport`、`/listAll`），响应为 `{total, rows}`
  - `ajax_entity`：`/{id}` 详情端点，响应为 `AjaxResult.success(entity)`
  - `raw_entity`：仅 feeGantry/feerecords/snapshotflow 三个控制器直接返回实体
  - `diagnostic`：`/health`、`/metrics`
  - `ajax`：其它
- `samples.json`：采集用的 path 参数/query 参数默认值。
- **Java 实例 9902 当前不可达**（TCP 连接被拒绝），因此真实响应样本
  标记为“待采集”，未纳入仓库（`captured/` 已被 `.gitignore` 忽略，避免把
  生产数据/凭据写入版本库）。

## 更新基线

```powershell
# 在 car-monit-api-cpp 目录
$env:CM_UPDATE_CONTRACT_GOLDEN = "1"
build\carmonit_tests.exe
Remove-Item Env:CM_UPDATE_CONTRACT_GOLDEN
```

随后 `ctest` 会用新基线做严格比较；路由/响应形态发生变化时测试会失败并打印差异。

## 采集真实响应（DB 解锁后）

```powershell
# Java 实例（默认 9902）
powershell -File scripts/contract-collect.ps1 -BaseUrl http://127.0.0.1:9902 -OutDir contracts/captured/java

# C++ 实例（默认 9901）
powershell -File scripts/contract-collect.ps1 -BaseUrl http://127.0.0.1:9901 -OutDir contracts/captured/cpp

# 比较
powershell -File scripts/contract-diff.ps1
```

采集脚本只发 GET 请求，跳过 POST/PUT/DELETE/PATCH；实例不可达时写
`captured/<side>/PENDING.json` 并以 0 退出，不会反复重试。

## 限制

- 基线目前只固化“路由 + 响应形态”；精确响应体需要在 DB 可用后采集并校准。
- `contract-diff.ps1` 会忽略时间戳/自增 id/分页 total 等易变字段；数组按元素
  JSON 排序后比较。
