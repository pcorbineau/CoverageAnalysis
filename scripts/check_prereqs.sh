#!/usr/bin/env bash
# check_prereqs.sh — WSL-side tool checks (no awk dependency)
# Called by check_prereqs.ps1 via: wsl -d FedoraLinux-44 bash scripts/check_prereqs.sh

ERRORS=0
WARNINGS=0

ok()   { printf "  [OK]    %-22s %s\n" "$1" "$2"; }
warn() { printf "  [WARN]  %-22s %s\n" "$1" "$2"; WARNINGS=$((WARNINGS+1)); }
err()  { printf "  [ERROR] %-22s %s\n" "$1" "$2"; ERRORS=$((ERRORS+1)); }

require_cmd() {
    local name="$1" bin="$2"
    if ! command -v "$bin" &>/dev/null; then
        err "$name" "NOT FOUND  -- install with: sudo dnf install $bin"
        return 1
    fi
    return 0
}

# Extract first semver-like version string from a line
extract_ver() { echo "$1" | grep -oP '\d+\.\d+[\.\d]*' | head -1; }

# ── cmake ─────────────────────────────────────────────────────────────────────
if require_cmd "cmake" "cmake"; then
    line=$(cmake --version 2>&1 | head -1)
    ver=$(extract_ver "$line")
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "${major:-0}" -gt 3 ] || { [ "${major:-0}" -eq 3 ] && [ "${minor:-0}" -ge 20 ]; }; then
        ok "cmake" "$ver"
    else
        warn "cmake" "$ver  (need >= 3.20, upgrade: sudo dnf install cmake or pip install cmake)"
    fi
fi

# ── g++ ───────────────────────────────────────────────────────────────────────
GPP_VER=""
if require_cmd "g++" "g++"; then
    line=$(g++ --version 2>&1 | head -1)
    GPP_VER=$(extract_ver "$line")
    ok "g++" "$GPP_VER"
fi

# ── gcov — must match g++ major version ──────────────────────────────────────
GCOV_VER=""
if require_cmd "gcov" "gcov"; then
    line=$(gcov --version 2>&1 | head -1)
    GCOV_VER=$(extract_ver "$line")
    ok "gcov" "$GCOV_VER"

    if [ -n "$GPP_VER" ] && [ -n "$GCOV_VER" ]; then
        GPP_MAJOR=$(echo "$GPP_VER"  | cut -d. -f1)
        GCOV_MAJOR=$(echo "$GCOV_VER" | cut -d. -f1)
        if [ "$GPP_MAJOR" = "$GCOV_MAJOR" ]; then
            ok "gcc/gcov version" "match (major $GPP_MAJOR)"
        else
            err "gcc/gcov version" "MISMATCH  g++=$GPP_VER  gcov=$GCOV_VER -- .gcda files will be corrupt"
        fi
    fi
fi

# ── gcovr ─────────────────────────────────────────────────────────────────────
if require_cmd "gcovr" "gcovr"; then
    line=$(gcovr --version 2>&1 | head -1)
    GCOVR_VER=$(extract_ver "$line")
    GCOVR_MAJOR=$(echo "$GCOVR_VER" | cut -d. -f1)
    if [ "${GCOVR_MAJOR:-0}" -ge 5 ] 2>/dev/null; then
        ok "gcovr" "$GCOVR_VER"
    else
        warn "gcovr" "$GCOVR_VER  (need >= 5.0; upgrade: pip install --upgrade gcovr)"
    fi
else
    echo "          Fix: sudo dnf install gcovr   or   pip install gcovr"
fi

# ── clang++ ───────────────────────────────────────────────────────────────────
CLANGPP_VER=""
if require_cmd "clang++" "clang++"; then
    line=$(clang++ --version 2>&1 | head -1)
    CLANGPP_VER=$(extract_ver "$line")
    ok "clang++" "$CLANGPP_VER"
fi

# ── llvm-profdata — must match clang++ major ─────────────────────────────────
PROFDATA_BIN=""
CLANG_MAJOR=$(echo "$CLANGPP_VER" | cut -d. -f1)
for candidate in "llvm-profdata-${CLANG_MAJOR}" "llvm-profdata"; do
    if command -v "$candidate" &>/dev/null; then PROFDATA_BIN="$candidate"; break; fi
done

if [ -z "$PROFDATA_BIN" ]; then
    err "llvm-profdata" "NOT FOUND  -- install: sudo dnf install llvm"
else
    line=$("$PROFDATA_BIN" --version 2>&1 | grep -i 'version' | head -1)
    PROFDATA_VER=$(extract_ver "$line")
    PROFDATA_MAJOR=$(echo "$PROFDATA_VER" | cut -d. -f1)
    if [ -z "$PROFDATA_VER" ]; then
        warn "$PROFDATA_BIN" "could not determine version"
    elif [ -n "$CLANGPP_VER" ] && [ "$CLANG_MAJOR" != "$PROFDATA_MAJOR" ]; then
        err "$PROFDATA_BIN" "VERSION MISMATCH  clang++=$CLANGPP_VER  llvm-profdata=$PROFDATA_VER"
    else
        ok "$PROFDATA_BIN" "$PROFDATA_VER  (matches clang++ $CLANG_MAJOR.x)"
    fi
fi

# ── llvm-cov — must match clang++ major ──────────────────────────────────────
LLVMCOV_BIN=""
for candidate in "llvm-cov-${CLANG_MAJOR}" "llvm-cov"; do
    if command -v "$candidate" &>/dev/null; then LLVMCOV_BIN="$candidate"; break; fi
done

if [ -z "$LLVMCOV_BIN" ]; then
    err "llvm-cov" "NOT FOUND  -- install: sudo dnf install llvm"
else
    line=$("$LLVMCOV_BIN" --version 2>&1 | grep -i 'version' | head -1)
    LLVMCOV_VER=$(extract_ver "$line")
    LLVMCOV_MAJOR=$(echo "$LLVMCOV_VER" | cut -d. -f1)
    if [ -z "$LLVMCOV_VER" ]; then
        warn "$LLVMCOV_BIN" "could not determine version"
    elif [ -n "$CLANGPP_VER" ] && [ "$CLANG_MAJOR" != "$LLVMCOV_MAJOR" ]; then
        err "$LLVMCOV_BIN" "VERSION MISMATCH  clang++=$CLANGPP_VER  llvm-cov=$LLVMCOV_VER"
    else
        ok "$LLVMCOV_BIN" "$LLVMCOV_VER  (matches clang++ $CLANG_MAJOR.x)"
    fi
fi

# ── python3 ───────────────────────────────────────────────────────────────────
if require_cmd "python3" "python3"; then
    line=$(python3 --version 2>&1 | head -1)
    PY3_VER=$(extract_ver "$line")
    ok "python3" "$PY3_VER"
fi

# ── C++23 compile test ────────────────────────────────────────────────────────
echo ""
echo "  Checking C++23 support (if consteval) ..."
TMPDIR_CHECK=$(mktemp -d)
cat > "$TMPDIR_CHECK/test.cpp" <<'CPP'
constexpr int f(int n) {
    if consteval { return n * 2; }
    else         { return n + 1; }
}
int main() { return f(0); }
CPP

if command -v g++ &>/dev/null; then
    if g++ -std=c++23 -o "$TMPDIR_CHECK/tg" "$TMPDIR_CHECK/test.cpp" 2>/dev/null; then
        ok "g++ C++23" "if consteval compiles OK"
    else
        warn "g++ C++23" "if consteval failed  (need GCC >= 12)"
    fi
fi

if command -v clang++ &>/dev/null; then
    if clang++ -std=c++23 -o "$TMPDIR_CHECK/tc" "$TMPDIR_CHECK/test.cpp" 2>/dev/null; then
        ok "clang++ C++23" "if consteval compiles OK"
    else
        warn "clang++ C++23" "if consteval failed  (need Clang >= 14)"
    fi
fi
rm -rf "$TMPDIR_CHECK"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "  ──────────────────────────────────────────────"
if [ "$ERRORS" -gt 0 ]; then
    printf "  Result: %d error(s),  %d warning(s)  -- fix errors before running.\n" "$ERRORS" "$WARNINGS"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    printf "  Result: 0 errors,  %d warning(s)  -- some features may be limited.\n" "$WARNINGS"
    exit 0
else
    echo "  Result: all WSL checks passed."
    exit 0
fi
