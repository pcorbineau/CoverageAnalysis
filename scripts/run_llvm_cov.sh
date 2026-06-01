#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_llvm_cov.sh  —  Clang + llvm-cov coverage pipeline (runs inside WSL)
# Called from run_llvm_cov.bat via:  wsl bash scripts/run_llvm_cov.sh
# Working directory is the project root (WSL /mnt/... translation is automatic).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROF_RAW="coverage-reports/llvm/default.profraw"
PROF_DATA="coverage-reports/llvm/default.profdata"
TEST_BIN="./build-clang/tests/tests"

# Use versioned LLVM binaries if available (e.g. llvm-profdata-22)
CLANG_MAJOR=$(clang++ --version 2>&1 | grep -oP '\d+\.\d+[\.\d]*' | head -1 | cut -d. -f1)
PROFDATA_BIN="llvm-profdata"
LLVMCOV_BIN="llvm-cov"
if command -v "llvm-profdata-${CLANG_MAJOR}" &>/dev/null; then PROFDATA_BIN="llvm-profdata-${CLANG_MAJOR}"; fi
if command -v "llvm-cov-${CLANG_MAJOR}"      &>/dev/null; then LLVMCOV_BIN="llvm-cov-${CLANG_MAJOR}"; fi
echo "  Using: $PROFDATA_BIN  $LLVMCOV_BIN"

echo ""
echo "--- llvm-cov: CMake configure (Clang) ---"
cmake -B build-clang \
      -DCOVERAGE_LLVM=ON \
      -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_CXX_COMPILER=clang++

echo ""
echo "--- llvm-cov: Build ---"
cmake --build build-clang -j"$(nproc)"

echo ""
echo "--- llvm-cov: Run tests (collecting profile data) ---"
mkdir -p coverage-reports/llvm
LLVM_PROFILE_FILE="$PROF_RAW" "$TEST_BIN"

echo ""
echo "--- llvm-cov: Merge profile data ---"
$PROFDATA_BIN merge \
    -sparse "$PROF_RAW" \
    -o "$PROF_DATA"

echo ""
echo "--- llvm-cov: Generate HTML report ---"
mkdir -p coverage-reports/llvm/html
$LLVMCOV_BIN show "$TEST_BIN" \
    -instr-profile="$PROF_DATA" \
    -format=html \
    -output-dir=coverage-reports/llvm/html \
    -ignore-filename-regex=".*catch.*|.*_deps.*|.*tests/.*"

echo ""
echo "--- llvm-cov: Generate text summary ---"
$LLVMCOV_BIN report "$TEST_BIN" \
    -instr-profile="$PROF_DATA" \
    -ignore-filename-regex=".*catch.*|.*_deps.*|.*tests/.*" \
    | tee coverage-reports/llvm/summary.txt

echo ""
echo "--- llvm-cov: Generate JSON summary ---"
# Extract TOTAL line metrics into a simple JSON for the landing page generator.
python3 - <<'PYEOF'
import re, json, sys

with open("coverage-reports/llvm/summary.txt") as f:
    lines = f.readlines()

# Find the TOTAL line (last line that starts with TOTAL)
total_line = next((l for l in reversed(lines) if l.strip().startswith("TOTAL")), None)
if not total_line:
    print("Could not find TOTAL line in llvm-cov summary", file=sys.stderr)
    sys.exit(1)

# Format: TOTAL  regions missed cover%  functions missed cover%  lines missed cover%  branches missed cover%
tokens = total_line.split()
# tokens[0]=TOTAL, then groups of (total, missed, cover%) for regions, functions, lines, branches
def pct(s):
    return float(s.rstrip('%'))

result = {
    "region_total":   int(tokens[1]),  "region_missed":   int(tokens[2]),  "region_percent":   pct(tokens[3]),
    "function_total": int(tokens[4]),  "function_missed": int(tokens[5]),  "function_percent": pct(tokens[6]),
    "line_total":     int(tokens[7]),  "line_missed":     int(tokens[8]),  "line_percent":     pct(tokens[9]),
    "branch_total":   int(tokens[10]), "branch_missed":   int(tokens[11]), "branch_percent":   pct(tokens[12]),
}
with open("coverage-reports/llvm/summary.json", "w") as f:
    json.dump(result, f, indent=2)
print("Written coverage-reports/llvm/summary.json")
PYEOF

echo ""
echo "--- llvm-cov: Export per-line data ---"
$LLVMCOV_BIN export "$TEST_BIN" \
    -instr-profile="$PROF_DATA" \
    -ignore-filename-regex=".*catch.*|.*_deps.*|.*tests/.*" \
    > coverage-reports/llvm/lines.json
echo "Written coverage-reports/llvm/lines.json"

echo ""
echo "--- llvm-cov: Done ---"
echo "    HTML   : coverage-reports/llvm/html/index.html"
echo "    Text   : coverage-reports/llvm/summary.txt"
echo "    JSON   : coverage-reports/llvm/summary.json"
