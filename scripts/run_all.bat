@echo off
setlocal enabledelayedexpansion

:: ─────────────────────────────────────────────────────────────────────────────
:: run_all.bat — Master orchestrator
:: Runs all three coverage pipelines from the project root on Windows.
:: Requires: OpenCppCoverage on PATH, WSL with GCC+gcovr and Clang+llvm-cov,
::           Python 3 on PATH for landing page generation.
:: ─────────────────────────────────────────────────────────────────────────────

:: Always run from project root (one level above scripts\)
cd /d "%~dp0\.."

echo.
echo ============================================================
echo   Coverage Demo -- All three tools
echo ============================================================
echo   Project root: %CD%
echo ============================================================

:: ── Prerequisite check ───────────────────────────────────────────────────────
echo.
echo [0/4] Checking prerequisites ...
call scripts\check_prereqs.bat
if errorlevel 1 (
    echo.
    echo [ABORT] Prerequisite check reported errors. Fix them and re-run.
    exit /b 1
)

:: ── Determine what is available after the check ──────────────────────────────
set SKIP_OPENCPP=0
set SKIP_PYTHON=0

where OpenCppCoverage >nul 2>&1
if errorlevel 1 set SKIP_OPENCPP=1

where python >nul 2>&1
if errorlevel 1 set SKIP_PYTHON=1

:: ── Step results ─────────────────────────────────────────────────────────────
set OPENCPP_OK=0
set GCOV_OK=0
set LLVM_OK=0

:: ── 1. MSVC + OpenCppCoverage ────────────────────────────────────────────────
echo.
if "%SKIP_OPENCPP%"=="1" (
    echo [1/4] OpenCppCoverage -- SKIPPED ^(not on PATH^)
) else (
    echo [1/4] Running OpenCppCoverage ^(MSVC^) ...
    call scripts\run_opencpp_coverage.bat
    if errorlevel 1 (
        echo [FAIL] OpenCppCoverage step failed.
    ) else (
        set OPENCPP_OK=1
        echo [OK]   OpenCppCoverage done.
    )
)

:: ── 2. WSL GCC + gcovr ───────────────────────────────────────────────────────
echo.
echo [2/4] Running gcov ^(WSL GCC^) ...
call scripts\run_gcov.bat
if errorlevel 1 (
    echo [FAIL] gcov step failed.
) else (
    set GCOV_OK=1
    echo [OK]   gcov done.
)

:: ── 3. WSL Clang + llvm-cov ──────────────────────────────────────────────────
echo.
echo [3/4] Running llvm-cov ^(WSL Clang^) ...
call scripts\run_llvm_cov.bat
if errorlevel 1 (
    echo [FAIL] llvm-cov step failed.
) else (
    set LLVM_OK=1
    echo [OK]   llvm-cov done.
)

:: ── 4. Landing page ──────────────────────────────────────────────────────────
echo.
if "%SKIP_PYTHON%"=="1" (
    echo [4/4] Landing page -- SKIPPED ^(python not on PATH^)
) else (
    echo [4/4] Generating landing page ...
    python scripts\generate_landing_page.py
    if errorlevel 1 (
        echo [WARN] Landing page generation failed.
    ) else (
        echo [OK]   Landing page: coverage-reports\index.html
        start "" "coverage-reports\index.html"
    )
)

:: ── Summary ──────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo   Summary
echo ============================================================
if "%OPENCPP_OK%"=="1" (
    echo   [OK]     OpenCppCoverage   coverage-reports\opencpp\index.html
) else (
    echo   [--]     OpenCppCoverage   FAILED or SKIPPED
)
if "%GCOV_OK%"=="1" (
    echo   [OK]     gcov / gcovr      coverage-reports\gcov\index.html
) else (
    echo   [--]     gcov / gcovr      FAILED
)
if "%LLVM_OK%"=="1" (
    echo   [OK]     llvm-cov          coverage-reports\llvm\html\index.html
) else (
    echo   [--]     llvm-cov          FAILED
)
echo ============================================================
echo.

endlocal
