cmake_minimum_required(VERSION 3.20)
project(CoverageDemo CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(COVERAGE_GCOV "Enable gcov coverage instrumentation (GCC)" OFF)
option(COVERAGE_LLVM "Enable llvm-cov coverage instrumentation (Clang)" OFF)
option(COVERAGE_MSVC "Enable Microsoft Code Coverage instrumentation helpers (MSVC)" OFF)

include(cmake/CodeCoverage.cmake)

# ── Library ───────────────────────────────────────────────────────────────
add_library(coverage_lib
    src/calculator.cpp
    src/shapes.cpp
)
target_include_directories(coverage_lib PUBLIC src)
set_target_properties(coverage_lib PROPERTIES CXX_STANDARD 23)

if(COVERAGE_GCOV)
    enable_gcov_coverage(coverage_lib)
endif()
if(COVERAGE_LLVM)
    enable_llvm_coverage(coverage_lib)
endif()
if(COVERAGE_MSVC)
    enable_msvc_coverage(coverage_lib)
endif()

# ── Tests ─────────────────────────────────────────────────────────────────
enable_testing()
add_subdirectory(tests)
