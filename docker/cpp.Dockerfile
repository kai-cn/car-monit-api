# C++ 服务镜像（CMake 3.20+ / C++20 / librdkafka 静态构建）
# 构建上下文 = car-monit-api-cpp/：
#   docker build -f docker/cpp.Dockerfile -t car-monit-api-cpp car-monit-api-cpp
#
# 基础镜像选择：
#   * 构建阶段 debian:12-slim + g++12/cmake/ninja —— g++12 完整支持 C++20；
#     CMakeLists 通过 FetchContent 编译 librdkafka（关闭 SSL/SASL/zlib/zstd/curl），
#     只需要 ca-certificates 保证 HTTPS 下载。
#   * 运行阶段 debian:12-slim —— 二进制动态依赖 glibc/libstdc++/libgcc；同时需要
#     ca-certificates（访问 ES 等 HTTP/TLS 端点）与 tzdata（调度器按本地时区计算）。
#     distroless/cc 虽更小，但缺 CA 证书、无 shell，排障成本更高，故不采用。
#
# 运行期配置：镜像不打包 configs/config.yaml（可能含连接串/口令）。
# 由 K8s 以 ConfigMap/Secret 挂载到 /app/configs/config.yaml；也可用 -c 覆盖路径。
# 注意：master 目前只跟踪 11 个 C++ 文件，完整源码在 car-monit-api-cpp 分支；
# 源码未入库时本镜像无法构建（CI 会显式跳过/失败，不会产出假镜像）。
FROM debian:12-slim AS build

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential cmake ninja-build ca-certificates pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . .

RUN cmake -S . -B build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCM_WITH_KAFKA=ON \
 && cmake --build build --parallel

FROM debian:12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libstdc++6 ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system carmonit \
 && useradd --system --gid carmonit --no-create-home carmonit \
 && mkdir -p /app/logs /app/data /app/configs \
 && chown -R carmonit:carmonit /app

WORKDIR /app
COPY --from=build /src/build/car-monit-api /usr/local/bin/car-monit-api

USER carmonit
EXPOSE 9901

ENTRYPOINT ["/usr/local/bin/car-monit-api", "--config", "/app/configs/config.yaml"]
