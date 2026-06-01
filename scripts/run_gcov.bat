@echo off
setlocal

:: ─────────────────────────────────────────────────────────────────────────────
:: run_gcov.bat
:: Delegates the GCC + gcovr pipeline to WSL via run_gcov.sh.
:: The WSL process inherits the current Windows directory, which is translated
:: automatically to /mnt/... by WSL.
:: ─────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0\.."

echo --- gcov: delegating to WSL ---
wsl bash scripts/run_gcov.sh

exit /b %errorlevel%
