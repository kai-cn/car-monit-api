# syntax=docker/dockerfile:1
# =============================================================================
# car-monit-api (C++) 生产镜像
#
# 构建阶段与 CI 的 Linux job 对齐：Debian 12 + GCC 12 + CMake + Ninja，
# 依赖获取方式与 CMakeLists.txt 一致（FetchContent：libpqxx / hiredis /
# librdkafka，来源为固定版本的 GitHub tarball + SHA256 校验）。
#
# 链接策略：
#   * libpqxx / hiredis / librdkafka 由本工程 CMake 以静态库方式链接
#     （CMakeLists.txt 中 BUILD_SHARED_LIBS=OFF、RDKAFKA_BUILD_STATIC=ON），
#     因此运行镜像不需要这些第三方开发包。
#   * libpq 使用系统共享库（libpq5），OpenSSL 使用系统共享库（libssl3）：
#     二者是 libpqxx/hiredis_ssl 的运行时依赖，运行镜像必须安装。
#     构建阶段用 libpq-dev/libssl-dev，运行阶段只保留 libpq5/libssl3。
#   * librdkafka 关闭 SSL/SASL/zlib/zstd/curl（与 Java 侧 PLAINTEXT + LZ4 一致），
#     不引入额外运行库。
#
# 安全基线：非 root（uid/gid 10001）运行、只复制运行所需产物、镜像内置
# healthcheck 指向 /health。注意：/health 在依赖降级时仍返回 HTTP 200
# （body.status=DEGRADED），健康检查只代表进程可服务；依赖告警见监控规则。
# =============================================================================

ARG DEBIAN_RELEASE=12

# -----------------------------------------------------------------------------
# 构建阶段
# -----------------------------------------------------------------------------
FROM debian:${DEBIAN_RELEASE}-slim AS build

ARG CMAKE_BUILD_PARALLEL_LEVEL=4
ENV DEBIAN_FRONTEND=noninteractive \
    CMAKE_BUILD_PARALLEL_LEVEL=${CMAKE_BUILD_PARALLEL_LEVEL}

# 只安装构建必需项；git/ca-certificates 供 FetchContent 通过 HTTPS 下载源码包。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       cmake \
       ninja-build \
       libpq-dev \
       libssl-dev \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# 先复制构建入口与源码目录，尽量复用依赖下载层。
COPY CMakeLists.txt ./
COPY src ./src
COPY tests ./tests
COPY third_party ./third_party

# CM_WERROR=ON：与 CI 一致，把本工程告警视为错误。
# 只构建服务目标 car-monit-api；carmonit_tests 目标保留但不构建。
RUN cmake -S . -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCM_WERROR=ON \
    && cmake --build build --target car-monit-api --parallel "${CMAKE_BUILD_PARALLEL_LEVEL}"

# -----------------------------------------------------------------------------
# 运行阶段（最小 debian-slim；distroless 不含 libpq 依赖链，故不采用）
# -----------------------------------------------------------------------------
FROM debian:${DEBIAN_RELEASE}-slim AS runtime

# 全局 ARG 在 FROM 之后不自动进入本阶段作用域，需重新声明供 LABEL 使用。
ARG DEBIAN_RELEASE=12
ARG VERSION=dev
ARG GIT_SHA=unknown

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai

LABEL org.opencontainers.image.title="car-monit-api" \
      org.opencontainers.image.description="car-monit-api C++ 服务" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.base.name="debian:${DEBIAN_RELEASE}-slim"

# 运行库：
#   libpq5        -> libpqxx/libpq 依赖
#   libssl3       -> libpq(hiredis_ssl) 依赖
#   curl          -> 仅供 HEALTHCHECK 使用（debian-slim 默认没有 curl）
#   ca-certificates/tzdata -> TLS 校验与 Asia/Shanghai 日志时间
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpq5 \
       libssl3 \
       curl \
       ca-certificates \
       tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 carmonit \
    && useradd --system --uid 10001 --gid carmonit \
       --home-dir /app --shell /usr/sbin/nologin carmonit

WORKDIR /app

COPY --from=build --chown=carmonit:carmonit /src/build/car-monit-api /app/car-monit-api
# 配置随镜像提供默认值；敏感值必须通过环境变量（CM_*）或 config.local.yaml/Secret 注入，
# 不要打进镜像。config.yaml 中的口令字段是 ${CM_PG_PASSWORD} 占位。
COPY --chown=carmonit:carmonit configs/config.yaml /app/configs/config.yaml

# 日志目录与导出目录必须可写（config.yaml: logging / optimization.export.dir）。
RUN mkdir -p /app/logs /data/export \
    && chown -R carmonit:carmonit /app/logs /data/export

USER 10001:10001

EXPOSE 9901

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:9901/health || exit 1

ENTRYPOINT ["/app/car-monit-api"]
CMD ["-c", "configs/config.yaml"]
