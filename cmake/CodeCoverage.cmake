# cmake/CodeCoverage.cmake
# Helper functions to enable coverage instrumentation for GCC (gcov),
# Clang (llvm-cov), and MSVC (Microsoft Code Coverage).
# Usage:
#   enable_gcov_coverage(<target>)   -- adds --coverage flags
#   enable_llvm_coverage(<target>)   -- adds -fprofile-instr-generate / -fcoverage-mapping flags
#   enable_msvc_coverage(<target>)   -- adds /PROFILE for static native instrumentation

function(enable_gcov_coverage target)
    message(STATUS "[Coverage] Enabling gcov instrumentation on target: ${target}")
    target_compile_options(${target} PUBLIC
        --coverage
        -O0
        -g
        -fno-inline
        # Emit out-of-line copies of inline functions even when never called,
        # so gcov can report them as uncovered instead of silently omitting them.
        -fkeep-inline-functions
        # -femit-all-decls: C-only flag, rejected by g++ — not applicable.
    )
    target_link_options(${target} PUBLIC --coverage)
endfunction()

function(enable_llvm_coverage target)
    message(STATUS "[Coverage] Enabling llvm-cov instrumentation on target: ${target}")
    target_compile_options(${target} PUBLIC
        -fprofile-instr-generate
        -fcoverage-mapping
        -O0
        -g
        -fno-inline
        # -fkeep-inline-functions: no effect on Clang (source-based coverage is
        # inliner-independent; flag is silently ignored with a warning).
        # -femit-all-decls: tested below — kept only if it produces a delta.
    )
    target_link_options(${target} PUBLIC -fprofile-instr-generate)
endfunction()

function(enable_msvc_coverage target)
    if(NOT MSVC)
        message(FATAL_ERROR "enable_msvc_coverage(${target}) requires MSVC")
    endif()

    message(STATUS "[Coverage] Enabling Microsoft Code Coverage instrumentation helpers on target: ${target}")
    target_compile_options(${target} PUBLIC
        /Od
        /Zi
    )
    # /PROFILE enables the linker support required for static native instrumentation.
    target_link_options(${target} PUBLIC /DEBUG /PROFILE)
endfunction()
