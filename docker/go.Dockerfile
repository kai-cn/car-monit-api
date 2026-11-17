# Go 服务镜像（go.mod 锁 1.26.11，入口 ./cmd/api）
# 构建上下文 = car-monit-api-go/：
#   docker build -f docker/go.Dockerfile -t car-monit-api-go car-monit-api-go
#
# 基础镜像选择：
#   * 构建阶段 golang:1.26.11-bookworm —— 与 go.mod 的 `go 1.26.11` 对齐，bookworm 提供 glibc 工具链。
#   * 运行阶段 debian:12-slim —— CGO_ENABLED=0 产物本身可静态运行，但服务需要
#     tzdata（定时任务按本地时区）与 ca-certificates（ES/外部 HTTP 端点），
#     distroless/static 缺这两项，故选择 debian-slim。
#
# 运行期配置：镜像不打包 configs/config.yaml（仓库副本含连接信息）。
# 由 K8s 挂载到 /app/configs/config.yaml；也可用 --config 覆盖。
FROM golang:1.26.11-bookworm AS build

ENV CGO_ENABLED=0

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go build -trimpath -ldflags "-s -w -X main.version=1.0.0" -o /out/api ./cmd/api

FROM debian:12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system carmonit \
 && useradd --system --gid carmonit --no-create-home carmonit \
 && mkdir -p /app/logs /app/data /app/configs \
 && chown -R carmonit:carmonit /app

WORKDIR /app
COPY --from=build /out/api /app/api

USER carmonit
EXPOSE 9901

ENTRYPOINT ["/app/api", "--config", "configs/config.yaml"]
