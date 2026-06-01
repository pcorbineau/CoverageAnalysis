#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_gcov.sh  —  GCC + gcovr coverage pipeline (runs inside WSL)
# Called from run_gcov.bat via:  wsl bash scripts/run_gcov.sh
# Working directory is the project root (WSL /mnt/... translation is automatic).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

echo ""
echo "--- gcov: CMake configure (GCC) ---"
cmake -B build-gcc \
      -DCOVERAGE_GCOV=ON \
      -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_CXX_COMPILER=g++

echo ""
echo "--- gcov: Build ---"
cmake --build build-gcc -j"$(nproc)"

echo ""
echo "--- gcov: Run tests ---"
./build-gcc/tests/tests

echo ""
echo "--- gcov: Generate gcovr report ---"
mkdir -p coverage-reports/gcov

gcovr \
    --root . \
    --object-directory build-gcc \
    --exclude "tests/.*" \
    --exclude ".*catch.*" \
    --html-details coverage-reports/gcov/index.html \
    --txt          coverage-reports/gcov/summary.txt \
    --json-summary coverage-reports/gcov/summary.json \
    --json         coverage-reports/gcov/lines.json \
    --print-summary

echo ""
echo "--- gcov: Done ---"
echo "    HTML   : coverage-reports/gcov/index.html"
echo "    Text   : coverage-reports/gcov/summary.txt"
echo "    JSON   : coverage-reports/gcov/summary.json"
