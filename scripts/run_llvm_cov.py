#!/usr/bin/env python3
"""
run_llvm_cov.py
Cross-platform Clang + llvm-cov source-based coverage pipeline.

Steps:
  1. CMake configure  (build-clang/)  with COVERAGE_LLVM=ON
  2. Build
  3. Run tests  (LLVM_PROFILE_FILE → default.profraw)
  4. llvm-profdata merge  → default.profdata
  5. llvm-cov show        → HTML report
  6. llvm-cov report      → summary.txt + summary.json
  7. llvm-cov export      → lines.json

LLVM binary resolution order:
  1. Versioned binary matching clang major  (llvm-cov-22)
  2. Unversioned binary on PATH             (llvm-cov)
  3. Homebrew llvm formula bin dir          (/opt/homebrew/opt/llvm/bin/)
  4. Linux apt multi-version dirs           (/usr/lib/llvm-*/bin/)

Usage:
  python scripts/run_llvm_cov.py
  python scripts/run_llvm_cov.py --non-interactive --install   # CI
  python scripts/run_llvm_cov.py --skip-prereqs                # skip check
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
SYSTEM  = platform.system()

# ── Paths ─────────────────────────────────────────────────────────────────────

BUILD_DIR   = ROOT / "build-clang"
REPORT_DIR  = ROOT / "coverage-reports" / "llvm"
PROF_RAW    = REPORT_DIR / "default.profraw"
PROF_DATA   = REPORT_DIR / "default.profdata"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _c(code: str, text: str) -> str:
    if SYSTEM == "Windows" and not os.environ.get("WT_SESSION"):
        return text
    return f"\033[{code}m{text}\033[0m"

def banner(msg: str) -> None:
    print(f"\n{_c('35', '─' * 60)}")
    print(f"{_c('35', f'  llvm-cov: {msg}')}")
    print(f"{_c('35', '─' * 60)}")

def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(_c("31", f"  [ERROR] command failed (exit {result.returncode})"))
        sys.exit(result.returncode)
    return result

def cpu_count() -> int:
    return os.cpu_count() or 2

# ── LLVM binary resolution ────────────────────────────────────────────────────

def _homebrew_llvm_bin() -> Path | None:
    brew = shutil.which("brew")
    if not brew:
        return None
    try:
        prefix = subprocess.check_output([brew, "--prefix"], text=True).strip()
        candidate = Path(prefix) / "opt" / "llvm" / "bin"
        return candidate if candidate.is_dir() else None
    except subprocess.CalledProcessError:
        return None

def _apt_llvm_bin() -> Path | None:
    """Highest versioned /usr/lib/llvm-N/bin that has llvm-cov."""
    candidates = sorted(Path("/usr/lib").glob("llvm-*/bin"), reverse=True)
    for d in candidates:
        if (d / "llvm-cov").exists():
            return d
    return None

def find_clang() -> str:
    """
    Return the clang++ binary.
    On macOS: prefers Homebrew LLVM over Apple Clang (Apple Clang lacks
    llvm-profdata / llvm-cov in the same suite).
    """
    if SYSTEM == "Darwin":
        llvm_bin = _homebrew_llvm_bin()
        if llvm_bin:
            candidate = llvm_bin / "clang++"
            if candidate.exists():
                return str(candidate)
    return "clang++"

def _clang_major(clang_bin: str) -> str:
    try:
        out = subprocess.check_output([clang_bin, "--version"],
                                       stderr=subprocess.STDOUT, text=True)
        m = re.search(r"(\d+)\.\d+", out)
        return m.group(1) if m else ""
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""

def find_llvm_tool(tool: str, clang_bin: str) -> str:
    """
    Resolve an LLVM tool binary (llvm-cov, llvm-profdata) following the
    priority order described in the module docstring.
    """
    major = _clang_major(clang_bin)

    # 1. Versioned on PATH
    if major and shutil.which(f"{tool}-{major}"):
        return f"{tool}-{major}"

    # 2. Unversioned on PATH
    if shutil.which(tool):
        return tool

    # 3. Homebrew LLVM bin dir (macOS)
    if SYSTEM == "Darwin":
        llvm_bin = _homebrew_llvm_bin()
        if llvm_bin:
            for candidate_name in ([f"{tool}-{major}", tool] if major else [tool]):
                p = llvm_bin / candidate_name
                if p.exists():
                    return str(p)

    # 4. Linux apt multi-version
    if SYSTEM == "Linux":
        apt_bin = _apt_llvm_bin()
        if apt_bin:
            for candidate_name in ([f"{tool}-{major}", tool] if major else [tool]):
                p = apt_bin / candidate_name
                if p.exists():
                    return str(p)

    print(_c("31", f"  [ERROR] {tool} not found. Run: python scripts/check_prereqs.py --install"))
    sys.exit(1)

def find_test_binary() -> Path:
    if SYSTEM == "Windows":
        candidates = [
            BUILD_DIR / "tests" / "Debug" / "tests.exe",
            BUILD_DIR / "tests" / "tests.exe",
        ]
    else:
        candidates = [BUILD_DIR / "tests" / "tests"]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

# ── Pipeline steps ────────────────────────────────────────────────────────────

def step_configure(clang_bin: str) -> None:
    banner("CMake configure (Clang)")
    # Derive C compiler from clang++
    clang_c = clang_bin.replace("clang++", "clang").replace("clang++-", "clang-")
    cmd = [
        "cmake", "-B", str(BUILD_DIR),
        "-DCOVERAGE_LLVM=ON",
        "-DCMAKE_BUILD_TYPE=Debug",
        f"-DCMAKE_CXX_COMPILER={clang_bin}",
    ]
    if shutil.which(clang_c) or Path(clang_c).exists():
        cmd.append(f"-DCMAKE_C_COMPILER={clang_c}")
    run(cmd, cwd=ROOT)

def step_build() -> None:
    banner("Build")
    run(["cmake", "--build", str(BUILD_DIR), f"-j{cpu_count()}"], cwd=ROOT)

def step_test(test_bin: Path) -> None:
    banner("Run tests (collecting profile data)")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LLVM_PROFILE_FILE"] = str(PROF_RAW)
    run([str(test_bin)], cwd=ROOT, env=env)

def step_merge(profdata_bin: str) -> None:
    banner("Merge profile data")
    run([
        profdata_bin, "merge",
        "-sparse", str(PROF_RAW),
        "-o",      str(PROF_DATA),
    ], cwd=ROOT)

def step_html(llvmcov_bin: str, test_bin: Path) -> None:
    banner("Generate HTML report")
    html_dir = REPORT_DIR / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    run([
        llvmcov_bin, "show", str(test_bin),
        f"-instr-profile={PROF_DATA}",
        "-format=html",
        f"-output-dir={html_dir}",
        "-ignore-filename-regex=.*catch.*|.*_deps.*|.*tests/.*",
    ], cwd=ROOT)

def step_summary(llvmcov_bin: str, test_bin: Path) -> None:
    banner("Generate text summary")
    result = subprocess.run([
        llvmcov_bin, "report", str(test_bin),
        f"-instr-profile={PROF_DATA}",
        "-ignore-filename-regex=.*catch.*|.*_deps.*|.*tests/.*",
    ], capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        print(_c("31", f"  [ERROR] llvm-cov report failed:\n{result.stderr}"))
        sys.exit(1)
    print(result.stdout)
    summary_path = REPORT_DIR / "summary.txt"
    summary_path.write_text(result.stdout, encoding="utf-8")
    print(f"  Written: {summary_path}")
    _write_summary_json(result.stdout)

def _write_summary_json(summary_text: str) -> None:
    """Parse the TOTAL line from llvm-cov report output → summary.json."""
    total_line = next(
        (l for l in reversed(summary_text.splitlines()) if l.strip().startswith("TOTAL")),
        None,
    )
    if not total_line:
        print(_c("33", "  [WARN] Could not find TOTAL line — summary.json not written"))
        return

    tokens = total_line.split()
    # Format: TOTAL  <reg_total> <reg_miss> <reg_%>  <fn_total> <fn_miss> <fn_%>
    #                <ln_total>  <ln_miss>  <ln_%>   <br_total> <br_miss> <br_%>
    def pct(s: str) -> float:
        return float(s.rstrip("%"))

    try:
        data = {
            "region_total":   int(tokens[1]),  "region_missed":   int(tokens[2]),  "region_percent":   pct(tokens[3]),
            "function_total": int(tokens[4]),  "function_missed": int(tokens[5]),  "function_percent": pct(tokens[6]),
            "line_total":     int(tokens[7]),  "line_missed":     int(tokens[8]),  "line_percent":     pct(tokens[9]),
            "branch_total":   int(tokens[10]), "branch_missed":   int(tokens[11]), "branch_percent":   pct(tokens[12]),
        }
    except (IndexError, ValueError) as exc:
        print(_c("33", f"  [WARN] Could not parse TOTAL line ({exc}) — summary.json not written"))
        return

    out = REPORT_DIR / "summary.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  Written: {out}")

def step_export(llvmcov_bin: str, test_bin: Path) -> None:
    banner("Export per-line data")
    result = subprocess.run([
        llvmcov_bin, "export", str(test_bin),
        f"-instr-profile={PROF_DATA}",
        "-ignore-filename-regex=.*catch.*|.*_deps.*|.*tests/.*",
    ], capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        print(_c("31", f"  [ERROR] llvm-cov export failed:\n{result.stderr}"))
        sys.exit(1)
    out = REPORT_DIR / "lines.json"
    out.write_text(result.stdout, encoding="utf-8")
    print(f"  Written: {out}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Clang + llvm-cov coverage pipeline")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--install",         action="store_true")
    parser.add_argument("--skip-prereqs",    action="store_true")
    args = parser.parse_args()

    if not args.skip_prereqs:
        prereq_cmd = [sys.executable, str(ROOT / "scripts" / "check_prereqs.py")]
        if args.non_interactive:
            prereq_cmd.append("--non-interactive")
        if args.install:
            prereq_cmd.append("--install")
        result = subprocess.run(prereq_cmd, cwd=ROOT)
        if result.returncode != 0:
            print(_c("31", "  [ABORT] Prerequisite check failed."))
            return 1

    clang_bin    = find_clang()
    profdata_bin = find_llvm_tool("llvm-profdata", clang_bin)
    llvmcov_bin  = find_llvm_tool("llvm-cov",      clang_bin)

    print(f"\n  Using compiler    : {clang_bin}")
    print(f"  Using llvm-profdata: {profdata_bin}")
    print(f"  Using llvm-cov     : {llvmcov_bin}")

    step_configure(clang_bin)
    step_build()
    test_bin = find_test_binary()
    step_test(test_bin)
    step_merge(profdata_bin)
    step_html(llvmcov_bin, test_bin)
    step_summary(llvmcov_bin, test_bin)
    step_export(llvmcov_bin, test_bin)

    print(_c("32", f"\n  [DONE] llvm-cov pipeline complete"))
    print(f"    HTML   : {REPORT_DIR / 'html' / 'index.html'}")
    print(f"    Summary: {REPORT_DIR / 'summary.txt'}")
    print(f"    JSON   : {REPORT_DIR / 'summary.json'}")
    print(f"    Lines  : {REPORT_DIR / 'lines.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
