@echo off
setlocal enabledelayedexpansion

:: check_prereqs.bat
:: Verifies all tools required by the three coverage pipelines.
:: Automatically locates and loads vcvarsall.bat (MSVC environment).
:: Exit code: 0 = all required tools found, 1 = at least one error.

cd /d "%~dp0\.."

set ERRORS=0
set WARNINGS=0

echo.
echo ============================================================
echo   Prerequisite check
echo ============================================================

:: ----------------------------------------------------------------------------
:: Locate Visual Studio and load MSVC environment via vcvarsall.bat
:: ----------------------------------------------------------------------------
echo.
echo [Windows / MSVC]

set VSWHERE="%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist %VSWHERE% set VSWHERE="%ProgramFiles%\Microsoft Visual Studio\Installer\vswhere.exe"

if not exist %VSWHERE% (
    echo   [WARN]  vswhere.exe    NOT FOUND -- Visual Studio may not be installed
    set /a WARNINGS+=1
    goto :skip_vs
)

for /f "usebackq delims=" %%p in (`%VSWHERE% -latest -property installationPath`) do set VS_PATH=%%p
if not defined VS_PATH (
    echo   [WARN]  Visual Studio  No installation found via vswhere
    set /a WARNINGS+=1
    goto :skip_vs
)

for /f "usebackq delims=" %%v in (`%VSWHERE% -latest -property catalog_productDisplayVersion`) do set VS_VER=%%v
echo   [OK]    Visual Studio  !VS_VER!  (!VS_PATH!)

set VCVARSALL=!VS_PATH!\VC\Auxiliary\Build\vcvarsall.bat
if not exist "!VCVARSALL!" (
    echo   [WARN]  vcvarsall.bat  NOT FOUND at !VCVARSALL!
    set /a WARNINGS+=1
    goto :skip_vs
)

echo   [OK]    vcvarsall.bat  found -- loading x64 environment...
call "!VCVARSALL!" x64 >nul 2>&1
if errorlevel 1 (
    echo   [WARN]  vcvarsall.bat  failed to initialize environment
    set /a WARNINGS+=1
) else (
    echo   [OK]    MSVC env       loaded (x64)
)

:skip_vs

:: ----------------------------------------------------------------------------
:: cmake
:: ----------------------------------------------------------------------------
where cmake >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] cmake          NOT FOUND -- install from https://cmake.org
    set /a ERRORS+=1
) else (
    for /f "tokens=3 delims= " %%v in ('cmake --version 2^>^&1') do (
        echo   [OK]    cmake          %%v
        goto :cmake_done
    )
    :cmake_done
)

:: ----------------------------------------------------------------------------
:: Python
:: ----------------------------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo   [WARN]  python         NOT FOUND -- landing page will not be generated
    set /a WARNINGS+=1
) else (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do (
        echo   [OK]    python         %%v
        goto :python_done
    )
    :python_done
)

:: ----------------------------------------------------------------------------
:: WSL
:: ----------------------------------------------------------------------------
where wsl >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] wsl            NOT FOUND -- required for GCC and Clang builds
    set /a ERRORS+=1
    goto :skip_wsl_ver
)
echo   [OK]    wsl            found
:skip_wsl_ver

:: ----------------------------------------------------------------------------
:: OpenCppCoverage
:: ----------------------------------------------------------------------------
where OpenCppCoverage >nul 2>&1
if errorlevel 1 (
    echo   [WARN]  OpenCppCoverage NOT FOUND -- MSVC pipeline will be skipped
    echo           Download: https://github.com/OpenCppCoverage/OpenCppCoverage/releases
    set /a WARNINGS+=1
) else (
    echo   [OK]    OpenCppCoverage found
)

:: ----------------------------------------------------------------------------
:: WSL tool checks (delegated to check_prereqs.sh)
:: ----------------------------------------------------------------------------
echo.
echo [WSL]

where wsl >nul 2>&1
if errorlevel 1 (
    echo   [SKIP]  WSL not available -- skipping WSL tool checks
    goto :wsl_done
)

wsl bash scripts/check_prereqs.sh
if errorlevel 1 (
    set /a ERRORS+=1
)

:wsl_done

:: ----------------------------------------------------------------------------
:: Summary
:: ----------------------------------------------------------------------------
echo.
echo ============================================================
if %ERRORS% GTR 0 (
    echo   Result: %ERRORS% error(s^),  %WARNINGS% warning(s^) -- fix errors before running.
    echo ============================================================
    echo.
    endlocal
    exit /b 1
) else if %WARNINGS% GTR 0 (
    echo   Result: 0 errors,  %WARNINGS% warning(s^) -- some pipelines may be skipped.
    echo ============================================================
) else (
    echo   Result: all checks passed.
    echo ============================================================
)
echo.

endlocal
exit /b 0
