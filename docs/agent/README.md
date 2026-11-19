# 路网数据智能助手（Agent）文档索引

本目录是"高速公路联网收费与监控数据平台"对话式数据助手的**设计与契约**文档，两个实现分支共用：

| 分支 | 框架 | 版本 | 代码目录 |
| --- | --- | --- | --- |
| `springAi` | Spring AI | 2.0.2 | `pro-business-api/.../agent/springai` |
| `agentScope2java` | AgentScope Java | 2.0.5 | `pro-business-api/.../agent/agentscope` |

两分支共享 `agent/core`（域层）、`agent/tools`（工具层）、`agent/api`（接入层），仅适配层不同。

## 文档

| 文档 | 内容 | 读者 |
| --- | --- | --- |
| [agent-design.md](./agent-design.md) | 背景与目标、分支策略、分层架构、请求时序、安全模型（信任边界/越权/脱敏/二次确认/注入）、稳定性（限流/并发/预算/超时/降级）、可观测性、容量估算、**两分支横向对比与选型**、8 条踩坑记录、演进路线 | 架构评审、后端、运维、安全 |
| [agent-spec.md](./agent-spec.md) | 8 个 HTTP 端点契约、9 类 SSE 事件字段级定义、7 个工具完整 JSON Schema 与限制、16 个错误码、27 项配置、Redis Key/日志 schema、验收用例（功能/安全/稳定性/契约）、兼容性变更策略 | 前端、backend/BFF、测试、运维 |

## 快速上手

```bash
# 1) 编译 + 单测
mvn -pl pro-business-api -am test -DskipTests=false \
    -Dtest='Agent*Test,*MiddlewareTest,SpringAi*Test' -Dsurefire.failIfNoSpecifiedTests=false

# 2) 启动（需 Redis + GaussDB；模型凭据只从环境变量注入）
TRAFFIC_AGENT_ENABLED=true \
TRAFFIC_AGENT_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
TRAFFIC_AGENT_API_KEY=$KEY \
TRAFFIC_INTERNAL_TOKEN=dev-token \
java -jar pro-business-api/target/pro-business-api-1.0.jar

# 3) 看能力清单与健康状态
curl -s localhost:9902/api/v1/agent/tools  -H 'X-Internal-Token: dev-token' \
     -H 'X-Tenant-Id: t1' -H 'X-User-Id: u1' -H 'X-User-Roles: ops'
curl -s localhost:9902/api/v1/agent/health -H 'X-Internal-Token: dev-token'
```

## 三条硬约束（改代码前请先确认）

1. `agent/core`、`agent/tools`、`agent/api` **不得** import `org.springframework.ai.*` 或 `io.agentscope.*`；
2. 工具契约的唯一事实源是 `AgentToolCatalog`，改工具必须同时改 spec §5 与 `GET /tools` 的一致性校验；
3. SSE 事件名/字段是强契约：只允许新增可选字段，不允许改名或删除。
