cmake_minimum_required(VERSION 3.20)
project(car_monit_api_cpp VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

if(MSVC)
  add_compile_options(/W3 /utf-8 /bigobj)
else()
  add_compile_options(-Wall -Wextra -Wno-unused-parameter -Wno-missing-field-initializers)
endif()

find_package(Threads REQUIRED)

# ---------------------------------------------------------------------------
# librdkafka：真实 Kafka 生产者（对应 Java 的 KafkaTemplate / KafkaProducerConfig）。
#
# 依赖获取方式：FetchContent（首次 configure 时从 codeload.github.com 下载
# v2.6.1 源码，缓存在 build/_deps 下）。若目标机器离线，可预先设置
# -DFETCHCONTENT_SOURCE_DIR_LIBRDKAFKA=<本地源码目录>；
# 或 -DCM_WITH_KAFKA=OFF 退回 Redis 队列降级路径。
#
# 关闭 SSL/SASL/zlib/zstd/curl：Java 侧连接 localhost:9092 为 PLAINTEXT，
# 压缩使用 librdkafka 内置 LZ4，避免额外二进制依赖。
# ---------------------------------------------------------------------------
option(CM_WITH_KAFKA "使用 librdkafka 发送真实 Kafka 消息" ON)
if(CM_WITH_KAFKA)
  include(FetchContent)
  set(RDKAFKA_BUILD_STATIC ON CACHE BOOL "" FORCE)
  set(RDKAFKA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
  set(RDKAFKA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
  set(WITH_SSL OFF CACHE BOOL "" FORCE)
  set(WITH_SASL OFF CACHE BOOL "" FORCE)
  set(WITH_ZLIB OFF CACHE BOOL "" FORCE)
  set(WITH_ZSTD OFF CACHE BOOL "" FORCE)
  set(WITH_CURL OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(librdkafka
    URL https://codeload.github.com/confluentinc/librdkafka/tar.gz/refs/tags/v2.6.1
    URL_HASH SHA256=0ddf205ad8d36af0bc72a2fec20639ea02e1d583e353163bf7f4683d949e901b
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  )
  FetchContent_MakeAvailable(librdkafka)
endif()

file(GLOB_RECURSE CORE_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/src/common/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/config/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/db/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/cache/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/es/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/meta/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/repo/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/service/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/handler/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/scheduler/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/mq/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/router/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/http/*.cpp"
)

add_library(carmonit_core STATIC ${CORE_SOURCES})
target_include_directories(carmonit_core PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/src"
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party"
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party/httplib"
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party/nlohmann"
)
target_compile_definitions(carmonit_core PUBLIC
  CPPHTTPLIB_THREAD_POOL_COUNT=16
  WIN32_LEAN_AND_MEAN
  NOMINMAX
)
target_link_libraries(carmonit_core PUBLIC Threads::Threads)
if(WIN32)
  # secur32 由 librdkafka 在 Windows 下用于随机源（即使关闭 SASL）。
  target_link_libraries(carmonit_core PUBLIC ws2_32 crypt32 secur32)
endif()
if(TARGET rdkafka)
  target_link_libraries(carmonit_core PUBLIC rdkafka)
  target_compile_definitions(carmonit_core PUBLIC CM_WITH_KAFKA=1)
endif()

add_executable(car-monit-api "${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp")
target_link_libraries(car-monit-api PRIVATE carmonit_core)

enable_testing()
add_executable(carmonit_tests "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_main.cpp")
target_link_libraries(carmonit_tests PRIVATE carmonit_core)
add_test(NAME carmonit_tests COMMAND carmonit_tests)
