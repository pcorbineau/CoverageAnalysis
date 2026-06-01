@echo off
setlocal

cd /d "%~dp0\.."
python scripts\run_microsoft_coverage.py %*

endlocal
