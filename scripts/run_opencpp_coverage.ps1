# run_opencpp_coverage.ps1 — MSVC build + OpenCppCoverage
# Uses Ninja (build-ninja/) when available for faster builds,
# falls back to "Visual Studio 17 2022" (build-msvc/) otherwise.
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location (Split-Path $PSScriptRoot -Parent)
$ProjectRoot = (Get-Location).Path

# ── Load MSVC x64 environment ────────────────────────────────────────────────
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) { $vswhere = "$env:ProgramFiles\Microsoft Visual Studio\Installer\vswhere.exe" }
$vsPath    = & $vswhere -latest -property installationPath
$vcvarsall = Join-Path $vsPath "VC\Auxiliary\Build\vcvarsall.bat"
$envDump   = cmd /c "`"$vcvarsall`" x64 > nul 2>&1 && set"
foreach ($line in $envDump) {
    if ($line -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
    }
}
Write-Host "[OK] MSVC env loaded"

# ── Ensure OpenCppCoverage is on PATH ────────────────────────────────────────
$opencppDefaultPath = "C:\Program Files\OpenCppCoverage"
if ((Test-Path $opencppDefaultPath) -and ($env:PATH -notlike "*OpenCppCoverage*")) {
    $env:PATH = "$opencppDefaultPath;$env:PATH"
}

# ── Choose generator: Ninja if available, VS otherwise ───────────────────────
$useNinja  = [bool](Get-Command ninja -ErrorAction SilentlyContinue)
if ($useNinja) {
    $buildDir  = "build-ninja"
    $generator = "Ninja"
    $testExe   = "build-ninja\tests\tests.exe"
    Write-Host "[INFO] Ninja found -- using generator '$generator' in '$buildDir'"
} else {
    $buildDir  = "build-msvc"
    $generator = "Visual Studio 17 2022"
    $testExe   = "build-msvc\tests\Debug\tests.exe"
    Write-Host "[INFO] Ninja not found -- falling back to '$generator' in '$buildDir'"
}

# ── CMake configure ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "--- OpenCppCoverage: CMake configure ($generator) ---"
if ($useNinja) {
    cmake -B $buildDir -G $generator -DCMAKE_BUILD_TYPE=Debug
} else {
    cmake -B $buildDir -G $generator -A x64 -DCMAKE_BUILD_TYPE=Debug
}
if ($LASTEXITCODE -ne 0) { Write-Error "CMake configure failed"; exit 1 }

# ── Build ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "--- OpenCppCoverage: Build ---"
cmake --build $buildDir --config Debug
if ($LASTEXITCODE -ne 0) { Write-Error "Build failed"; exit 1 }

# ── Collect coverage ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "--- OpenCppCoverage: Collect coverage ---"
New-Item -ItemType Directory -Force -Path "coverage-reports\opencpp" | Out-Null

OpenCppCoverage.exe `
    --sources          "$ProjectRoot\src" `
    --excluded_sources ".*_deps.*" `
    --excluded_sources ".*catch.*" `
    --excluded_sources ".*tests.*" `
    --excluded_sources ".*Windows Kits.*" `
    --excluded_sources ".*MSVC.*" `
    --export_type      "html:coverage-reports\opencpp" `
    --export_type      "cobertura:coverage-reports\opencpp\coverage.xml" `
    --cover_children `
    -- $testExe

if ($LASTEXITCODE -ne 0) { Write-Error "OpenCppCoverage failed"; exit 1 }

Write-Host ""
Write-Host "--- OpenCppCoverage: Done ---"
Write-Host "    HTML : coverage-reports\opencpp\index.html"
Write-Host "    XML  : coverage-reports\opencpp\coverage.xml"

# ── Regenerate landing page ───────────────────────────────────────────────────
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "--- Regenerating landing page ---"
    python scripts\generate_landing_page.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK]  Landing page updated: coverage-reports\index.html" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Landing page generation failed." -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARN] python not found -- landing page not updated." -ForegroundColor DarkGray
}
