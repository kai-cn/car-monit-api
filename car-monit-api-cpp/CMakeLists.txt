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

file(GLOB_RECURSE CORE_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/src/common/*.cpp"
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
)

add_library(carmonit_core STATIC ${CORE_SOURCES})
target_include_directories(carmonit_core PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/src"
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party"
)
target_compile_definitions(carmonit_core PUBLIC
  CPPHTTPLIB_THREAD_POOL_COUNT=16
  WIN32_LEAN_AND_MEAN
  NOMINMAX
)
target_link_libraries(carmonit_core PUBLIC Threads::Threads)
if(WIN32)
  target_link_libraries(carmonit_core PUBLIC ws2_32 crypt32)
endif()

add_executable(car-monit-api "${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp")
target_link_libraries(car-monit-api PRIVATE carmonit_core)

enable_testing()
add_executable(carmonit_tests "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_main.cpp")
target_link_libraries(carmonit_tests PRIVATE carmonit_core)
add_test(NAME carmonit_tests COMMAND carmonit_tests)
