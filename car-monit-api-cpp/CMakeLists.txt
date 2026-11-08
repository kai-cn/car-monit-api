cmake_minimum_required(VERSION 3.20)
project(car_monit_api_cpp VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# ---------------------------------------------------------------------------
# 告警与静态检查相关选项（P0）
#
# - 告警只施加于本工程三个目标（carmonit_core / car-monit-api / carmonit_tests），
#   不使用目录级 add_compile_options：librdkafka 由 FetchContent 作为子目录加入，
#   目录级选项会被其继承，导致第三方 C 代码在 /WX 下构建失败。
# - 第三方头文件（httplib/json）通过 SYSTEM 包含隔离，避免其告警被计入。
# - CM_WERROR 默认 ON：本工程代码零告警可维持；Linux 上若出现平台特有告警导致
#   构建失败，可 -DCM_WERROR=OFF 快速解锁，再按告警修复后恢复。
# - CM_SANITIZE 仅在 GCC/Clang 生效（MSVC 无对应 -fsanitize 语义）；取值
#   address / undefined / address,undefined。ASan 与 UBSan 已在 CI 的 Linux
#   job 中验证；本机无 Clang/GCC，Windows 下不支持该选项。
# ---------------------------------------------------------------------------
option(CM_WERROR "把本工程编译告警视为错误" ON)
set(CM_SANITIZE "" CACHE STRING "启用 ASan/UBSan（仅 GCC/Clang，如 address,undefined）")
set_property(CACHE CM_SANITIZE PROPERTY STRINGS "" address undefined "address,undefined")

if(MSVC)
  set(CM_WARN_OPTIONS /W4 /utf-8 /bigobj)
  if(CM_WERROR)
    list(APPEND CM_WARN_OPTIONS /WX)
  endif()
else()
  set(CM_WARN_OPTIONS -Wall -Wextra -Wpedantic -Wno-unused-parameter -Wno-missing-field-initializers)
  # GCC 12 的 -Wrestrict 在 libstdc++ 的 std::string 内联路径（insert/replace/assign）
  # 上存在已知误报，配合 -Werror 会直接阻断 Linux 构建；仅对 GCC<13 关闭该项。
  if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS 13)
    list(APPEND CM_WARN_OPTIONS -Wno-restrict)
  endif()
  if(CM_WERROR)
    list(APPEND CM_WARN_OPTIONS -Werror)
  endif()
endif()

if(CM_SANITIZE)
  if(MSVC)
    message(FATAL_ERROR "CM_SANITIZE 仅支持 GCC/Clang；MSVC 请使用 -DCM_SANITIZE=OFF")
  endif()
  add_compile_options(-fsanitize=${CM_SANITIZE} -fno-omit-frame-pointer -g)
  add_link_options(-fsanitize=${CM_SANITIZE})
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

# ---------------------------------------------------------------------------
# PostgreSQL / GaussDB 客户端：libpqxx + libpq（替换自研 wire protocol 实现）。
#
# - libpqxx 7.10.0 由 FetchContent 获取（静态库；关闭其自带测试与文档）。
# - libpq：Linux 走系统包（CI: apt install libpq-dev）；Windows 使用 PostgreSQL
#   官方（EDB 构建）17.2 二进制包，仅用其 include/lib/bin，URL 与 SHA256 固定。
#   运行时 DLL（libpq/OpenSSL/iconv/intl）由 post-build 复制到可执行文件目录。
# - TLS 由 libpq 处理（sslmode / sslrootcert），Windows 包内置 OpenSSL 3。
# - 认证（MD5/SCRAM 等）全部交给 libpq，本工程不再维护口令派生实现。
#
# 离线构建：设置 -DFETCHCONTENT_SOURCE_DIR_LIBPQXX 与
# -DFETCHCONTENT_SOURCE_DIR_POSTGRES_WINDOWS（或系统已装 libpq）。
# ---------------------------------------------------------------------------
include(FetchContent)
if(WIN32)
  FetchContent_Declare(postgres_windows
    URL https://get.enterprisedb.com/postgresql/postgresql-17.2-1-windows-x64-binaries.zip
    URL_HASH SHA256=115eb69fa92430f162bdda2eced073b60fed538715fb3a19ce0bb8c2d8738d01
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  )
  FetchContent_MakeAvailable(postgres_windows)
  # 注：CMake 解压会去掉包内唯一的顶层目录 pgsql/，因此源目录即 pgsql 根。
  set(CM_PG_RUNTIME_DIR "${postgres_windows_SOURCE_DIR}")
  # 只保留 include/lib/bin：包内 pgAdmin/StackBuilder/doc/share 与构建无关，
  # 删除后显著降低 _deps 占用（CI 缓存也受益）。
  file(REMOVE_RECURSE
    "${CM_PG_RUNTIME_DIR}/pgAdmin 4"
    "${CM_PG_RUNTIME_DIR}/StackBuilder"
    "${CM_PG_RUNTIME_DIR}/doc"
    "${CM_PG_RUNTIME_DIR}/share"
  )
  set(PostgreSQL_INCLUDE_DIR "${CM_PG_RUNTIME_DIR}/include" CACHE PATH "" FORCE)
  set(PostgreSQL_TYPE_INCLUDE_DIR "${CM_PG_RUNTIME_DIR}/include" CACHE PATH "" FORCE)
  set(PostgreSQL_LIBRARY "${CM_PG_RUNTIME_DIR}/lib/libpq.lib" CACHE FILEPATH "" FORCE)
endif()
find_package(PostgreSQL REQUIRED)

set(BUILD_DOC OFF CACHE BOOL "" FORCE)
set(BUILD_TEST OFF CACHE BOOL "" FORCE)
set(SKIP_BUILD_TEST ON CACHE BOOL "" FORCE)
FetchContent_Declare(libpqxx
  URL https://codeload.github.com/jtv/libpqxx/tar.gz/refs/tags/7.10.0
  URL_HASH SHA256=d588bca36357eda8bcafd5bc1f95df1afe613fdc70c80e426fc89eecb828fc3e
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(libpqxx)
# libpqxx 头文件同样按 SYSTEM 引入（其 internal/concat.hxx 使用 [[assume]]，
# MSVC 19.43 会给出 C5030；/W4 + /WX 下不能让其告警阻断本工程）。
if(TARGET pqxx)
  set_target_properties(pqxx PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "")
endif()

# ---------------------------------------------------------------------------
# Redis 客户端：hiredis 1.5.0（替换自研 RESP2 实现）。
#
# - 静态库；TLS 由 hiredis_ssl + OpenSSL 提供。
# - Windows 复用 PostgreSQL 包中的 OpenSSL 3（include/openssl + libssl.lib/
#   libcrypto.lib 均由该包提供），避免再下载一份 OpenSSL。
# - Linux 需要 libssl-dev（CI 已安装）。
# - 本工程无 pipeline 批量命令调用点，故只接入同步 API；单连接 + 互斥锁语义
#   与既有实现一致（详见 docs/DECISIONS.md D-012）。
# ---------------------------------------------------------------------------
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(ENABLE_SSL ON CACHE BOOL "" FORCE)
set(DISABLE_TESTS ON CACHE BOOL "" FORCE)
set(ENABLE_SSL_TESTS OFF CACHE BOOL "" FORCE)
set(ENABLE_EXAMPLES OFF CACHE BOOL "" FORCE)
if(WIN32 AND DEFINED CM_PG_RUNTIME_DIR)
  set(OPENSSL_ROOT_DIR "${CM_PG_RUNTIME_DIR}" CACHE PATH "" FORCE)
endif()
FetchContent_Declare(hiredis
  URL https://codeload.github.com/redis/hiredis/tar.gz/refs/tags/v1.5.0
  URL_HASH SHA256=eec7ef8641d221e144a58d5ef8d733c8c75c7fd487097a233aacb4fa33981cfb
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(hiredis)
# hiredis 头文件按 SYSTEM 引入（其 sds.h 使用零长数组，C4200 会在 /W4 + /WX 下
# 变成错误）。清空其 INTERFACE_INCLUDE_DIRECTORIES，改由本工程以 SYSTEM 方式引入。
if(TARGET hiredis)
  set_target_properties(hiredis PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "")
endif()
if(TARGET hiredis_ssl)
  set_target_properties(hiredis_ssl PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "")
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
)
# 第三方头文件用 SYSTEM 包含：其告警不计入本工程 /W4、-Werror 判定。
target_include_directories(carmonit_core SYSTEM PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party"
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party/httplib"
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party/nlohmann"
  "${hiredis_SOURCE_DIR}"
  "${libpqxx_BINARY_DIR}/include"
  "${libpqxx_SOURCE_DIR}/include"
)
target_compile_options(carmonit_core PRIVATE ${CM_WARN_OPTIONS})
target_compile_definitions(carmonit_core PUBLIC
  CPPHTTPLIB_THREAD_POOL_COUNT=16
  WIN32_LEAN_AND_MEAN
  NOMINMAX
)
target_link_libraries(carmonit_core PUBLIC Threads::Threads pqxx PostgreSQL::PostgreSQL hiredis
                                              hiredis::hiredis_ssl)
if(WIN32)
  # secur32 由 librdkafka 在 Windows 下用于随机源（即使关闭 SASL）。
  target_link_libraries(carmonit_core PUBLIC ws2_32 crypt32 secur32)
endif()
if(TARGET rdkafka)
  # librdkafka 头文件按 SYSTEM 包含：其 GNU 语句表达式与返回类型限定符告警
  # 在 GCC -Wpedantic/-Werror 下会阻断构建，且不属于本工程代码。
  # 链接用 LINK_ONLY 只取库本身，避免 rdkafka 的 INTERFACE 头文件以 -I 传播回来
  # （清空其 INTERFACE 会破坏 librdkafka++ 自身对 generated 目录的依赖）。
  get_target_property(CM_RDKAFKA_INCLUDE_DIRS rdkafka INTERFACE_INCLUDE_DIRECTORIES)
  if(CM_RDKAFKA_INCLUDE_DIRS)
    target_include_directories(carmonit_core SYSTEM PUBLIC ${CM_RDKAFKA_INCLUDE_DIRS})
  endif()
  target_link_libraries(carmonit_core PUBLIC $<LINK_ONLY:rdkafka>)
  target_compile_definitions(carmonit_core PUBLIC CM_WITH_KAFKA=1)
endif()

add_executable(car-monit-api "${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp")
target_compile_options(car-monit-api PRIVATE ${CM_WARN_OPTIONS})
target_link_libraries(car-monit-api PRIVATE carmonit_core)

enable_testing()
add_executable(carmonit_tests "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_main.cpp")
target_compile_options(carmonit_tests PRIVATE ${CM_WARN_OPTIONS})
target_compile_definitions(carmonit_tests PRIVATE
  CM_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}"
)
target_link_libraries(carmonit_tests PRIVATE carmonit_core)
add_test(NAME carmonit_tests COMMAND carmonit_tests)

# libpq 运行时 DLL（Windows EDB 包）复制到可执行文件目录，避免依赖 PATH。
if(WIN32)
  set(CM_PG_RUNTIME_DLLS
    libpq.dll
    libssl-3-x64.dll
    libcrypto-3-x64.dll
    libintl-9.dll
    libiconv-2.dll
    libwinpthread-1.dll
  )
  foreach(tgt car-monit-api carmonit_tests)
    foreach(dll ${CM_PG_RUNTIME_DLLS})
      add_custom_command(TARGET ${tgt} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${CM_PG_RUNTIME_DIR}/bin/${dll}" "$<TARGET_FILE_DIR:${tgt}>"
        VERBATIM
      )
    endforeach()
  endforeach()
endif()
