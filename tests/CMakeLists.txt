include(FetchContent)

FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG        v3.5.3
)
FetchContent_MakeAvailable(Catch2)

add_executable(tests
    test_math_utils.cpp
    test_string_utils.cpp
    test_calculator.cpp
    test_shapes.cpp
)

target_link_libraries(tests PRIVATE coverage_lib Catch2::Catch2WithMain)
target_include_directories(tests PRIVATE ${CMAKE_SOURCE_DIR}/src)
set_target_properties(tests PROPERTIES CXX_STANDARD 23)

if(COVERAGE_GCOV)
    enable_gcov_coverage(tests)
endif()
if(COVERAGE_LLVM)
    enable_llvm_coverage(tests)
endif()
if(COVERAGE_MSVC)
    enable_msvc_coverage(tests)
endif()

include(CTest)
list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
include(Catch)
catch_discover_tests(tests)
