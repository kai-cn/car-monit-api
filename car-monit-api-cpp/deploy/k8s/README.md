# Kubernetes 部署说明

清单内容：

| 文件 | 说明 |
|---|---|
| `namespace.yaml` | 命名空间 `car-monit-api` |
| `configmap.yaml` | 非敏感环境变量（中间件地址、日志、选主开关等） |
| `deployment.yaml` | 2 副本、探针、资源限制、安全上下文、优雅停机、PDB 配套 |
| `service.yaml` | ClusterIP:80 → 容器 9901 |
| `hpa.yaml` | 2–6 副本，CPU/内存触发，缩容保守 |
| `pdb.yaml` | `minAvailable: 1` |
| `examples/secret.example.yaml` | Secret 创建示例（**不要直接 apply**） |
| `kustomization.yaml` | 聚合上述清单（不含 Secret） |

## 1. 部署前准备

1. 替换 `configmap.yaml` 中的占位地址（`*.example.internal`）为实际中间件地址。
2. 替换 `deployment.yaml` 的镜像地址 `registry.example.com/car-monit-api:0.1.0`。
3. 创建口令 Secret（口令不要写入 Git）：

```bash
kubectl create namespace car-monit-api --dry-run=client -o yaml | kubectl apply -f -

kubectl -n car-monit-api create secret generic car-monit-api-secret \
  --from-literal=CM_PG_PASSWORD='<真实口令>'
```

4. 如果 ES 需要认证：`CM_ES_HOST` 有环境变量覆盖，但 ES 用户名/口令没有 `CM_*` 覆盖项，
   需要把 `elasticsearch.username/password` 写进 `config.local.yaml` 并用 Secret 挂载。
   按 `examples/secret.example.yaml` 创建 `car-monit-api-local-config`，再取消
   `deployment.yaml` 中 `local-config` volume/volumeMount 的注释。

## 2. 发布

```bash
# 仅校验（需要 kubectl，不要求连上集群时可加 --dry-run=client）
kubectl apply -k deploy/k8s --dry-run=client

# 实际发布
kubectl apply -k deploy/k8s
kubectl -n car-monit-api rollout status deploy/car-monit-api

# 验证
kubectl -n car-monit-api get pods
kubectl -n car-monit-api port-forward svc/car-monit-api 9901:80
curl -s http://127.0.0.1:9901/health
curl -s 'http://127.0.0.1:9901/metrics?format=prometheus' | head
```

## 3. 多实例单活（必须理解的前提）

- 调度器与全量/增量同步由 Redis 分布式锁选主（`cluster.leader-election`，
  key 默认 `car-monit:leader`）。**副本数 > 1 时所有副本必须连同一个 Redis**，
  否则会出现多个实例同时执行调度/同步。
- `CM_LEADER_ELECTION_ENABLED=true` 且 Redis 正常时，只有一个副本持有锁；
  主副本退出后由其它副本接管。
- `CM_LEADER_FAIL_OPEN=false`（默认）：Redis 不可用时后台任务暂停，但 HTTP 继续服务，
  `/health` 显示 `DEGRADED`。这是有意的安全降级，不要改成 fail-open。
- HPA 扩缩容、滚动发布都不影响该语义；但 Redis 主从切换期间可能出现短暂双主，
  需要运维确认锁 TTL（默认 30s，续期 10s）。

## 4. 探针语义

`readinessProbe` / `livenessProbe` 都访问 `/health`。该端点即使依赖 DOWN 也返回
HTTP 200（`body.status=DEGRADED`），原因是探针不应把依赖抖动放大成全体副本摘除。
依赖级判定请用 Prometheus 告警（`carmonit_dependency_up == 0`）。

## 5. 回滚

```bash
# 查看历史版本
kubectl -n car-monit-api rollout history deploy/car-monit-api

# 回滚到上一版本
kubectl -n car-monit-api rollout undo deploy/car-monit-api

# 或直接回滚到指定 revision
kubectl -n car-monit-api rollout undo deploy/car-monit-api --to-revision=<N>
```

滚动策略为 `maxUnavailable: 0, maxSurge: 1`，回滚期间至少保留一个可用副本；
`terminationGracePeriodSeconds: 45` + `preStop sleep 10` 给在途请求留出排空时间。
