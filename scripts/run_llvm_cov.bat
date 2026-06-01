@echo off
setlocal

:: ─────────────────────────────────────────────────────────────────────────────
:: run_llvm_cov.bat
:: Delegates the Clang + llvm-cov pipeline to WSL via run_llvm_cov.sh.
:: ─────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0\.."

echo --- llvm-cov: delegating to WSL ---
wsl bash scripts/run_llvm_cov.sh

exit /b %errorlevel%
