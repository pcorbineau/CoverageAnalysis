@echo off
setlocal

:: ─────────────────────────────────────────────────────────────────────────────
:: run_opencpp_coverage.bat
:: Build with MSVC (Visual Studio 17 2022) and collect line coverage using
:: OpenCppCoverage.  Outputs an HTML report + Cobertura XML to:
::     coverage-reports\opencpp\
:: ─────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0\.."

:: Load MSVC environment
for /f "usebackq delims=" %%p in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -property installationPath 2^>nul`) do set VS_PATH=%%p
if defined VS_PATH (
    call "!VS_PATH!\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
)

echo.
echo --- OpenCppCoverage: CMake configure (MSVC) ---
cmake -B build-msvc ^
      -G "Visual Studio 17 2022" ^
      -A x64 ^
      -DCMAKE_BUILD_TYPE=Debug
if errorlevel 1 (
    echo [ERROR] CMake configure failed.
    exit /b 1
)

echo.
echo --- OpenCppCoverage: Build ---
cmake --build build-msvc --config Debug
if errorlevel 1 (
    echo [ERROR] Build failed.
    exit /b 1
)

echo.
echo --- OpenCppCoverage: Collect coverage ---
if not exist "coverage-reports\opencpp" mkdir "coverage-reports\opencpp"

OpenCppCoverage.exe ^
    --sources src ^
    --export-type html:coverage-reports\opencpp ^
    --export-type cobertura:coverage-reports\opencpp\coverage.xml ^
    --cover-children ^
    -- build-msvc\tests\Debug\tests.exe

if errorlevel 1 (
    echo [ERROR] OpenCppCoverage run failed.
    exit /b 1
)

echo.
echo --- OpenCppCoverage: Done ---
echo     HTML  : coverage-reports\opencpp\index.html
echo     XML   : coverage-reports\opencpp\coverage.xml

endlocal
