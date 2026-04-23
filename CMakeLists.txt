# Сборка библиотеки ядра (деградация WABT), CLI degradation_cli и опционально gtest.
# Исходники C++ в Code/; тесты в tests/ (корень репозитория — «Цифровая нефть»).
cmake_minimum_required(VERSION 3.16)
project(degradation_core VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CODE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/Code)

add_library(degradation_core
    Code/src/Regression.cpp
    Code/src/PeriodDetector.cpp
    Code/src/DegradationEngine.cpp
)

target_include_directories(degradation_core
    PUBLIC
        ${CODE_DIR}/include
)

add_executable(degradation_cli Code/src/main.cpp)
target_link_libraries(degradation_cli PRIVATE degradation_core)

option(BUILD_TESTING "Build tests" ON)
if(BUILD_TESTING)
    enable_testing()

    include(FetchContent)
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
        DOWNLOAD_EXTRACT_TIMESTAMP TRUE
    )
    FetchContent_MakeAvailable(googletest)

    add_executable(degradation_tests ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_degradation.cpp)
    target_link_libraries(degradation_tests PRIVATE degradation_core GTest::gtest_main)
    target_include_directories(degradation_tests PRIVATE ${CODE_DIR}/include)

    add_test(NAME degradation_tests COMMAND degradation_tests)
endif()
