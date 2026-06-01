# check_prereqs.ps1
# Verifies all tools required by the three coverage pipelines.
# Automatically locates vcvarsall.bat and loads the MSVC x64 environment.
# Exit code: 0 = OK (warnings allowed), 1 = hard error.

param(
    [string]$WslDistro = "FedoraLinux-44"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$Script:Errors   = 0
$Script:Warnings = 0

function Write-OK   ($label, $detail) { Write-Host ("  [OK]    {0,-22} {1}" -f $label, $detail) -ForegroundColor Green  }
function Write-Warn ($label, $detail) { Write-Host ("  [WARN]  {0,-22} {1}" -f $label, $detail) -ForegroundColor Yellow; $Script:Warnings++ }
function Write-Err  ($label, $detail) { Write-Host ("  [ERROR] {0,-22} {1}" -f $label, $detail) -ForegroundColor Red;    $Script:Errors++   }

# Change to project root (parent of scripts/)
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host ""
Write-Host "============================================================"
Write-Host "  Prerequisite check"
Write-Host "============================================================"

# ── Load MSVC environment via vcvarsall.bat ───────────────────────────────────
Write-Host ""
Write-Host "[Windows / MSVC]"

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    $vswhere = "$env:ProgramFiles\Microsoft Visual Studio\Installer\vswhere.exe"
}

if (-not (Test-Path $vswhere)) {
    Write-Warn "vswhere.exe" "NOT FOUND -- Visual Studio may not be installed"
} else {
    $vsPath = & $vswhere -latest -property installationPath 2>$null
    $vsVer  = & $vswhere -latest -property catalog_productDisplayVersion 2>$null

    if (-not $vsPath) {
        Write-Warn "Visual Studio" "No installation found via vswhere"
    } else {
        Write-OK "Visual Studio" "$vsVer  ($vsPath)"

        $vcvarsall = Join-Path $vsPath "VC\Auxiliary\Build\vcvarsall.bat"
        if (-not (Test-Path $vcvarsall)) {
            Write-Warn "vcvarsall.bat" "NOT FOUND at $vcvarsall"
        } else {
            Write-OK "vcvarsall.bat" "found -- loading x64 environment"

            # Import env vars produced by vcvarsall into this PS session
            $envDump = cmd /c "`"$vcvarsall`" x64 > nul 2>&1 && set"
            foreach ($line in $envDump) {
                if ($line -match '^([^=]+)=(.*)$') {
                    [System.Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
                }
            }
            Write-OK "MSVC env (x64)" "loaded"
        }
    }
}

# Ensure OpenCppCoverage is on PATH (default install location)
$opencppDefaultPath = "C:\Program Files\OpenCppCoverage"
if ((Test-Path $opencppDefaultPath) -and ($env:PATH -notlike "*OpenCppCoverage*")) {
    $env:PATH = "$opencppDefaultPath;$env:PATH"
}

# ── cmake ─────────────────────────────────────────────────────────────────────
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Err "cmake" "NOT FOUND -- install from https://cmake.org"
} else {
    $ver = (cmake --version 2>&1 | Select-String 'cmake version').ToString().Split()[-1]
    $parts = $ver -split '\.'
    if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 20)) {
        Write-OK "cmake" $ver
    } else {
        Write-Warn "cmake" "$ver  (need >= 3.20)"
    }
}

# ── Python ────────────────────────────────────────────────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Warn "python" "NOT FOUND -- landing page will not be generated"
} else {
    $ver = (python --version 2>&1).ToString().Split()[-1]
    Write-OK "python" $ver
}

# ── WSL ───────────────────────────────────────────────────────────────────────
if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    Write-Err "wsl" "NOT FOUND -- required for GCC and Clang builds"
} else {
    Write-OK "wsl" "found"
}

# ── OpenCppCoverage ───────────────────────────────────────────────────────────
if (-not (Get-Command OpenCppCoverage -ErrorAction SilentlyContinue)) {
    Write-Warn "OpenCppCoverage" "NOT FOUND -- MSVC pipeline will be skipped"
    Write-Host "          Download: https://github.com/OpenCppCoverage/OpenCppCoverage/releases" -ForegroundColor DarkYellow
} else {
    Write-OK "OpenCppCoverage" "found"
}

# ── WSL tool checks (delegated to check_prereqs.sh) ──────────────────────────
Write-Host ""
Write-Host "[WSL]"

if (Get-Command wsl -ErrorAction SilentlyContinue) {
    wsl -d $WslDistro bash scripts/check_prereqs.sh
    if ($LASTEXITCODE -ne 0) { $Script:Errors++ }
} else {
    Write-Host "  [SKIP]  WSL not available -- skipping WSL tool checks" -ForegroundColor DarkGray
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================"
if ($Script:Errors -gt 0) {
    Write-Host ("  Result: {0} error(s),  {1} warning(s) -- fix errors before running." -f $Script:Errors, $Script:Warnings) -ForegroundColor Red
    Write-Host "============================================================"
    exit 1
} elseif ($Script:Warnings -gt 0) {
    Write-Host ("  Result: 0 errors,  {0} warning(s) -- some pipelines may be skipped." -f $Script:Warnings) -ForegroundColor Yellow
    Write-Host "============================================================"
    exit 0
} else {
    Write-Host "  Result: all checks passed." -ForegroundColor Green
    Write-Host "============================================================"
    exit 0
}
