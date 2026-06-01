# run_llvm_cov.ps1 — delegates the Clang + llvm-cov pipeline to WSL FedoraLinux-44
param(
    [string]$WslDistro = "FedoraLinux-44"
)
Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host "--- llvm-cov: delegating to $WslDistro ---"
wsl -d $WslDistro bash scripts/run_llvm_cov.sh
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

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
