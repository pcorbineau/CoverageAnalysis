# run_all.ps1 — Master orchestrator (parallel execution)
# Launches all three coverage pipelines concurrently then generates the landing page.
param(
    [string]$WslDistro  = "FedoraLinux-44",
    [switch]$SkipChecks
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

Set-Location (Split-Path $PSScriptRoot -Parent)
$ProjectRoot = (Get-Location).Path
$LogDir      = Join-Path $ProjectRoot "coverage-reports\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "  Coverage Demo -- All three tools (parallel)"
Write-Host "  Project root: $ProjectRoot"
Write-Host "============================================================"

# ── 0. Prerequisite check (sequential — must pass before launching) ───────────
if (-not $SkipChecks) {
    Write-Host ""
    Write-Host "[0/4] Checking prerequisites ..."
    & "$PSScriptRoot\check_prereqs.ps1" -WslDistro $WslDistro
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ABORT] Prerequisite check reported errors." -ForegroundColor Red
        exit 1
    }
}

$hasOpenCpp = [bool](Get-Command OpenCppCoverage -ErrorAction SilentlyContinue)
if (-not $hasOpenCpp) {
    $opencppPath = "C:\Program Files\OpenCppCoverage"
    if (Test-Path $opencppPath) { $env:PATH = "$opencppPath;$env:PATH"; $hasOpenCpp = $true }
}
$hasPython = [bool](Get-Command python -ErrorAction SilentlyContinue)

# ── Helper: print a prefixed, coloured log line ───────────────────────────────
function Show-Log($prefix, $color, $line) {
    Write-Host ("[{0}] {1}" -f $prefix, $line) -ForegroundColor $color
}

# ── 1-3. Launch all three pipelines as background jobs ───────────────────────
Write-Host ""
Write-Host "[1-3/4] Launching all three pipelines in parallel ..."
Write-Host ""

$jobs = @()

# ── Job: OpenCppCoverage ──────────────────────────────────────────────────────
if ($hasOpenCpp) {
    $jobs += Start-Job -Name "opencpp" -ScriptBlock {
        param($root, $scriptDir)
        Set-Location $root
        $log = Join-Path $root "coverage-reports\logs\opencpp.log"
        & powershell -ExecutionPolicy Bypass -File "$scriptDir\run_opencpp_coverage.ps1" 2>&1 |
            Tee-Object -FilePath $log
        exit $LASTEXITCODE
    } -ArgumentList $ProjectRoot, $PSScriptRoot
} else {
    Write-Host "[opencpp] SKIPPED -- OpenCppCoverage not on PATH" -ForegroundColor DarkGray
}

# ── Job: gcov ─────────────────────────────────────────────────────────────────
$jobs += Start-Job -Name "gcov" -ScriptBlock {
    param($root, $distro)
    Set-Location $root
    $log = Join-Path $root "coverage-reports\logs\gcov.log"
    wsl -d $distro bash scripts/run_gcov.sh 2>&1 |
        Tee-Object -FilePath $log
    exit $LASTEXITCODE
} -ArgumentList $ProjectRoot, $WslDistro

# ── Job: llvm-cov ─────────────────────────────────────────────────────────────
$jobs += Start-Job -Name "llvm" -ScriptBlock {
    param($root, $distro)
    Set-Location $root
    $log = Join-Path $root "coverage-reports\logs\llvm.log"
    wsl -d $distro bash scripts/run_llvm_cov.sh 2>&1 |
        Tee-Object -FilePath $log
    exit $LASTEXITCODE
} -ArgumentList $ProjectRoot, $WslDistro

# ── Stream output from all running jobs until all finish ─────────────────────
$colors = @{ opencpp = 'Cyan'; gcov = 'Green'; llvm = 'Yellow' }

Write-Host "  Streaming output (interleaved by arrival order) ..."
Write-Host "  Full logs: $LogDir"
Write-Host ""

while ($jobs | Where-Object { $_.State -eq 'Running' }) {
    foreach ($job in $jobs) {
        $lines = Receive-Job $job -ErrorAction SilentlyContinue
        foreach ($line in $lines) {
            Show-Log $job.Name $colors[$job.Name] $line
        }
    }
    Start-Sleep -Milliseconds 200
}

# Drain any remaining output after all jobs finish
foreach ($job in $jobs) {
    $lines = Receive-Job $job -ErrorAction SilentlyContinue
    foreach ($line in $lines) {
        Show-Log $job.Name $colors[$job.Name] $line
    }
}

# ── Collect results ───────────────────────────────────────────────────────────
$opencppOk = $false
$gcovOk    = $false
$llvmOk    = $false

foreach ($job in $jobs) {
    $code = $job.ChildJobs[0].JobStateInfo.Reason
    $ok   = ($job.State -eq 'Completed') -and ($null -eq $code)
    switch ($job.Name) {
        'opencpp' { $opencppOk = $ok }
        'gcov'    { $gcovOk    = $ok }
        'llvm'    { $llvmOk    = $ok }
    }
    Remove-Job $job
}

# ── 4. Landing page (after all three complete) ────────────────────────────────
Write-Host ""
if (-not $hasPython) {
    Write-Host "[4/4] Landing page -- SKIPPED (python not on PATH)" -ForegroundColor DarkGray
} else {
    Write-Host "[4/4] Generating landing page ..."
    python scripts\generate_landing_page.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK]  Landing page: coverage-reports\index.html" -ForegroundColor Green
        Start-Process "coverage-reports\index.html"
    } else {
        Write-Host "[WARN] Landing page generation failed." -ForegroundColor Yellow
    }
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================"
Write-Host "  Summary"
Write-Host "============================================================"
@(
    @{ ok = $opencppOk; label = "OpenCppCoverage"; path = "coverage-reports\opencpp\index.html"    }
    @{ ok = $gcovOk;    label = "gcov / gcovr";    path = "coverage-reports\gcov\index.html"        }
    @{ ok = $llvmOk;    label = "llvm-cov";        path = "coverage-reports\llvm\html\index.html"   }
) | ForEach-Object {
    if ($_.ok) { Write-Host ("  [OK]  {0,-20} {1}" -f $_.label, $_.path) -ForegroundColor Green }
    else       { Write-Host ("  [--]  {0,-20} FAILED or SKIPPED"          -f $_.label)           -ForegroundColor DarkGray }
}
Write-Host "  Logs: $LogDir"
Write-Host "============================================================"
Write-Host ""
