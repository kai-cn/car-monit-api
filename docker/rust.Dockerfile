# Rust 服务镜像（rust-toolchain.toml 锁 1.90.0）
# 构建上下文 = car-monit-api-rust/：
#   docker build -f docker/rust.Dockerfile -t car-monit-api-rust car-monit-api-rust
#
# 基础镜像选择：
#   * 构建阶段 rust:1.90-slim-bookworm —— 与 rust-toolchain.toml 的 1.90.0 一致；
#     rdkafka 的 cmake-build 特性需要 cmake/g++/zlib 头文件。
#   * 运行阶段 debian:12-slim —— 动态依赖 glibc/libgcc 与 zlib；另需
#     ca-certificates（reqwest/ES）与 tzdata（chrono 本地时间语义）。
#     distroless/cc 缺 CA 与 tzdata，排障也更差，故不采用。
#
# 运行期配置：镜像不打包 config/application.yaml（仓库副本含连接信息）。
# 由 K8s 挂载到 /app/config/application.yaml，或用 CAR_MONIT_CONFIG 覆盖路径。
# 注意：car-monit-api-rust/ 当前被根 .gitignore 忽略、未在 master 入库；
# CI 仅在构建上下文存在时才构建（不存在则显式跳过，不产出假镜像）。
FROM rust:1.90-slim-bookworm AS build

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      cmake build-essential zlib1g-dev pkg-config ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src

RUN cargo build --release

FROM debian:12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      zlib1g ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system carmonit \
 && useradd --system --gid carmonit --no-create-home carmonit \
 && mkdir -p /app/logs /app/data /app/config \
 && chown -R carmonit:carmonit /app

WORKDIR /app
COPY --from=build /src/target/release/car-monit-api-rust /usr/local/bin/car-monit-api-rust

USER carmonit
EXPOSE 9901

ENTRYPOINT ["/usr/local/bin/car-monit-api-rust", "--config", "/app/config/application.yaml"]
