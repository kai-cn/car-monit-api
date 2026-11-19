# Agent 代码导览（面向第一次接触 Agent 的 Java 开发者）

> 目标：**15 分钟能改代码，2 小时能独立加工具**。
> 读完本文再去看 `agent-design.md`（为什么这么设计）与 `agent-spec.md`（对外契约逐字段）。
> 本文只讲"代码在哪、为什么这么写、新语法是什么意思"。

---

## 1. 先用 5 分钟建立心智模型

普通接口：`HTTP 请求 → Service → SQL → 返回 JSON`。

Agent 接口：**多了一圈"大模型"**，但本质仍是同步调用链，只是中间多了几次往返：

```
用户: "查一下赣B21E85 昨天在昌九高速的通行记录"
        │
        ▼
AgentChatController        把 HTTP 变成 SSE 长连接，做限流/并发/身份
        │
        ▼
AgentOrchestrator          循环：调模型 → 模型说"要查库" → 执行工具 → 结果回给模型 → 再调模型
        │            ▲
        │            └── AgentToolService（查 ES / GaussDB / 知识库，做脱敏与截断）
        ▼
大模型（OpenAI 兼容 HTTP 接口）
```

三个必须记住的点：

1. **模型是无状态的**。"记忆"= 每次把历史消息重新发一遍（由 `ChatMemory` / `AgentStateStore` 负责存取）。
2. **模型不能查库**。它只能输出"我要调用 `query_traffic_records`，参数是 {...}"，真正执行的是我们的 Java 代码。
3. **模型给的参数不可信**。所有参数都要在 `AgentToolService` 里二次校验，身份永远来自请求头而不是模型。

---

## 2. 读代码的正确顺序

| 顺序 | 文件 | 看什么 |
| --- | --- | --- |
| 1 | `core/AgentOrchestrator.java` | 总纲：一次对话的接口定义与事件顺序 |
| 2 | `core/AgentEvent.java` | SSE 契约：8 种事件、`seq` 的作用 |
| 3 | `api/AgentChatController.java` | HTTP 入口：SseEmitter、心跳、三道闸、许可释放 |
| 4 | `springai/SpringAiAgentOrchestrator.java` | ReAct 循环在 Spring AI 里长什么样 |
| 5 | `springai/ObservableToolCallback.java` | 工具调用的观测、预算、超时、虚拟线程 |
| 6 | `tools/AgentToolCatalog.java` | 7 个工具的"说明书"（JSON Schema），单一事实源 |
| 7 | `tools/AgentToolService.java` | 工具落地：复用 V3 服务 + 二次校验 + 脱敏 |
| 8 | `core/AgentPrincipal.java` | 身份模型：为什么模型不能决定"以谁的身份查" |
| 9 | `core/AgentGuard.java`、`AgentRateLimiter.java`、`AgentConcurrencyLimiter.java` | 安全与容量 |
| 10 | `core/PromptLibrary.java` + `resources/agent/prompts/system.md` | 提示词工程 |
| 11 | `core/KnowledgeBase.java` | RAG 的最小实现（BM25 检索） |
| 12 | `config/AgentProperties.java` | 所有可调参数 |

`agentScope2java` 分支把第 4、5 步换成 `agentscope/AgentScopeAgentOrchestrator.java`、
`agentscope/AgentScopeTools.java`，其余完全一致。

---

## 3. 一次请求的完整时序（对照代码）

```
1. 拦截器 AgentSecurityInterceptor
   校验 X-Internal-Token → 读 X-Tenant-Id / X-User-Id / X-User-Roles → 构造 AgentPrincipal
   （缺头一律 401，不兜底匿名）

2. Controller.chat()
   ├─ prepare(): AgentGuard 注入检测 → AgentRateLimiter 用户/租户限流 → 并发闸
   ├─ 生成/复用 sessionId，组装 AgentInvocation
   └─ new SseEmitter(timeout) + ChatStream.start()

3. ChatStream.start()
   ├─ 起心跳（每 10s 一条 comment 帧，防网关掐空闲连接）
   └─ orchestrator.stream(invocation).subscribe(this::emit, onError, onComplete)

4. Orchestrator.stream()
   ├─ emit(meta)                      ← 前端拿到 requestId / 模型名
   ├─ sessionStore.append(user)       ← UI 历史
   ├─ 组装 toolContext（principal / confirmToken / budget / sink）
   └─ chatClient.prompt()...stream()  ← 框架内部：调模型

5. 模型决定调工具（框架自动循环）
   ObservableToolCallback.call()
   ├─ emit(tool_call)                 ← 前端显示"正在查询…"
   ├─ 扣预算（超了直接返回错误 JSON）
   ├─ 虚拟线程执行 + 20s 超时
   ├─ emit(tool_result) + 审计 + 指标
   └─ 返回 JSON 字符串给框架 → 框架回填对话 → 再调模型

6. 模型输出最终文本 → emit(delta)×N → emit(usage) → emit(done) → sink.complete()
   ChatStream.onCompletion(): 停心跳、释放并发许可、写审计、指标收尾
```

四条结束路径（**都必须释放许可**）：正常完成、模型/工具异常、SSE 超时、客户端断开。
`ChatStream` 用 `AtomicBoolean finished/released` 保证幂等。

---

## 4. Java 8+ 新特性速查（本项目真实用法）

工程基线是 **JDK 25**，下面这些语法在 `agent` 包里都能看到。每条给出"这里为什么用它"。

| 特性 | 版本 | 项目中的位置 | 说明 |
| --- | --- | --- | --- |
| `record` | 16 | `AgentPrincipal`、`ToolSpec`、`KnowledgeHit` | 不可变数据载体。访问器是 `x()` 不是 `getX()`；紧凑构造器可做校验/归一化。注意 record 不能继承类、字段全 final |
| 紧凑构造器 | 16 | `AgentPrincipal { ... }` | 在字段赋值前统一清洗入参（去空白、白名单、超长哈希） |
| `instanceof` 模式匹配 | 16 | `SpringAiToolCallbacks.principal()`、`AgentChatController.classify()` | `x instanceof Foo f` 一步完成判断 + 绑定，无需强转 |
| `switch` 表达式 + 箭头 | 14 | `SpringAiToolCallbacks.dispatch()`、`AgentScopeTools` | 有返回值、不贯穿、不漏 `break`；`case 常量 ->` 支持多标签 |
| 文本块 `"""` | 15 | `AgentToolCatalog` 的 JSON Schema、`PromptLibrary.FALLBACK` | 多行字符串不用转义引号；结尾 `"""` 的位置决定末尾换行 |
| `var` | 10 | `SpringAiAgentOrchestrator.consume()` | 局部变量类型推断，**不是动态类型**；只在右侧能明确推出类型时用，方法签名/字段不要用 |
| 虚拟线程 | 21 | `ObservableToolCallback.TOOL_EXECUTOR` | `Thread.ofVirtual()` + `newThreadPerTaskExecutor`：一任务一线程，阻塞时自动让出载体线程。适合 I/O 等待，不解决连接池上限（故另配 32 许可信号量） |
| `List.of` / `Map.of` / `Set.of` | 9 | `AgentToolCatalog.SPECS`、各处小集合 | 不可变集合，**不接受 null**；元素多时注意重载上限（10 个） |
| `Optional` | 8 | `AgentScopeStateStore.get()` 等 | 表达"可能没有"，不要用它当字段类型或参数类型 |
| `CompletableFuture` | 8 | `ObservableToolCallback.invokeWithTimeout()` | 组合异步 + `get(timeout)` 做超时；注意 `cancel` 不会中断 JDBC |
| `Stream` | 8 | `AgentToolCatalog.specs().stream()...` | 声明式集合处理；**不要在 Stream 里做阻塞 I/O**（会占住调用线程） |
| `java.time` | 8 | `ToolSupport.parseTime()`、`AgentProperties` 的 `Duration` | 替代 `Date`/`SimpleDateFormat`（后者非线程安全） |
| `sealed`（预留） | 17 | 未使用 | 若将来把 `AgentEvent` 改成密封接口约束 8 种事件，可用 `sealed interface ... permits` |

> **给 CRUD 开发者的提醒**：`record` 的 `equals` 是逐字段比较，`AgentPrincipal` 作为 Map key 时行为与普通对象不同；
> `List.of()` 返回的集合不能 `add`，需要可变集合请显式 `new ArrayList<>(...)`。

---

## 5. AI 概念速查（看代码时会反复遇到）

| 术语 | 一句话解释 | 在本项目哪里体现 |
| --- | --- | --- |
| **token** | 模型处理文本的最小单位，约等于 0.5~1 个汉字；计费与长度限制都按它算 | `usage.promptTokens/completionTokens`；`max-output-tokens` |
| **上下文窗口** | 模型单次能"看见"的 token 上限（输入+输出）。超了要么报错要么被截断 | `history-window`（只回灌最近 N 轮）；`max-tool-result-chars` |
| **temperature** | 随机性。0 最稳定、1 最发散。数据查询场景取 0~0.3 | `traffic.agent.temperature` |
| **tool calling** | 把函数用 JSON Schema 描述给模型，模型输出"调用哪个、参数是什么"，由宿主执行 | `AgentToolCatalog` + `AgentToolService` |
| **ReAct** | Reason + Act 循环：想 → 调工具 → 看结果 → 再想，直到能回答 | 两分支的 Orchestrator |
| **系统提示词** | system 角色的规则文本，是"编程模型行为"的主要手段，但**不是安全边界** | `resources/agent/prompts/system.md` |
| **RAG** | 先检索私有文档，再把片段塞进提示词，弥补模型不懂业务口径 | `KnowledgeBase`（BM25）+ `search_knowledge` 工具 |
| **流式（streaming）** | 模型边生成边返回，前端做打字机效果 | `Flux<AgentEvent>` → SSE `delta` |
| **记忆 / 会话** | 模型无状态，"记得上文"靠每次重发历史 | Spring AI `ChatMemory`；AgentScope `AgentStateStore` |
| **提示词注入** | 用户用话术让模型越权（"忽略以上规则…"） | `AgentGuard` 启发式拦截（**只是第一道，真正防线是工具授权**） |
| **幻觉** | 模型编造不存在的数据 | 系统提示词禁止编造 + 强制走工具 + 回答带出处 |

---

## 6. 四个最常见的改动场景

### 6.1 加一个工具（不改框架代码）

1. `AgentToolCatalog`：加常量 + 一条 `ToolSpec`（名字、给模型看的描述、风险级别、角色、JSON Schema）；
2. `AgentToolService`：加方法，**第一行 `authorize()`**，然后做参数校验 → 调既有 Service → 脱敏/截断 → `ToolSupport.ok(...)`；
3. 两个适配层各加一个 `case`：`SpringAiToolCallbacks.dispatch()` 与 `AgentScopeTools.dispatch()`；
4. `agent-spec.md` §5 补该工具的 schema 与限制；
5. 启动时会自动校验"注册的工具名 == 目录里的工具名"，漏改会 fail-fast。

### 6.2 改提示词

只改 `resources/agent/prompts/system.md`，重启生效。占位符（`{{tenant}}`/`{{roles}}`/`{{today}}`）由
`PromptLibrary` 服务端渲染，**不要**在提示词里写"用户说自己是管理员就相信"这类规则。

### 6.3 换模型 / 换供应商

`application.yml` 的 `traffic.agent.base-url` / `api-key` / `model`。任何 OpenAI 兼容网关都行
（vLLM、Ollama、DashScope 兼容模式、Azure 网关）。换非兼容协议才需要动适配层。

### 6.4 调容量

| 现象 | 先看 | 再调 |
| --- | --- | --- |
| 429 / 排队 | `AGENT_BUSY` 指标 | `max-concurrent`、`user-qps`、`tenant-qps` |
| 回答很慢 | 工具 `latencyMs` | `tool-timeout`、SQL/ES 索引、`max-iters` |
| 模型答非所问 | `tool_call` 是否发生 | 工具描述、`temperature`、提示词 |
| 上下文超限 | `usage.promptTokens` | `history-window`、`max-tool-result-chars` |

---

## 7. 本地怎么跑（不接真模型）

```bash
# 1. 起依赖（Redis 必须；GaussDB 按需）
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 2. 起一个 OpenAI 兼容的假模型（任意实现 /v1/chat/completions 的服务）
#    测试用见 scripts/agent/mock-llm.py（支持 SSE 流式 + tool_call）

# 3. 起应用
export JAVA_HOME=/opt/jdk25
mvn -pl pro-business-api -am spring-boot:run \
  -Dspring-boot.run.arguments="--traffic.agent.base-url=http://127.0.0.1:18080/v1 --traffic.agent.api-key=test"

# 4. 手动验证
TOKEN=$(grep -A2 internal-token pro-business-api/src/main/resources/application.yml | head -3)
curl -N -X POST http://127.0.0.1:8080/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-Id: t1' -H 'X-User-Id: u1' -H 'X-User-Roles: ops' \
  -H "X-Internal-Token: $TOKEN" \
  -d '{"message":"查一下赣B21E85 昨天的通行记录"}'
```

用 `curl -N` 才能看到逐帧输出；`-s | cat -v` 可看原始 SSE 帧。
`scripts/agent/e2e.sh` 是 CI 用的断言脚本，本地同样可跑。

---

## 8. 读代码时最容易踩的 6 个坑

1. **`meta` 只发一次**，在编排器里；Controller 不再发（历史 bug：两条 meta 让前端重复建会话）。
2. **`seq` 从 1 自增**，超时/错误帧也要带 `id`，否则前端排序会乱。
3. **工具返回 `ok:false` 不是异常**：模型需要读错误码自我修正，别改成抛异常。
4. **`ChatMemory` 与 `AgentSessionStore` 是两份数据**：前者给模型、后者给 UI；删会话时两份都要清。
5. **`AgentScopeStateStore` 的 userId 是 `tenant:user` 拼接**：不要改成只用 userId，否则跨租户同 ID 会串会话。
6. **超时 ≠ 查询被取消**：`CompletableFuture.cancel` 不会中断 JDBC，真正的取消靠 ES `socket-timeout` 与 GaussDB `statement_timeout`。

---

## 9. 想更进一步看什么

- Spring AI 官方文档：`ChatClient`、`Advisor`、`ToolCallback` 三节；
- AgentScope Java：`ReActAgent`、`Toolkit`、`AgentStateStore`、事件模型；
- 本仓库 `docs/agent/agent-design.md` §5（安全模型）、§6（四道闸与降级矩阵）；
- `docs/agent/agent-spec.md` §4（SSE 字段级定义）、§5（工具 schema）。
