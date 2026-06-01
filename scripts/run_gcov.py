#!/usr/bin/env python3
"""
run_gcov.py
Cross-platform GCC + gcovr coverage pipeline.

Steps:
  1. CMake configure  (build-gcc/)  with COVERAGE_GCOV=ON
  2. Build
  3. Run tests
  4. gcovr  → HTML, text summary, JSON summary, per-line JSON
  5. (Optional) generate landing page

Isolation: gcovr is invoked from the project venv (.coverage-venv/).
           Falls back to the system gcovr if the venv binary is absent.

Usage:
  python scripts/run_gcov.py
  python scripts/run_gcov.py --non-interactive --install   # CI
  python scripts/run_gcov.py --skip-prereqs                # skip check step
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
SYSTEM  = platform.system()

# ── Paths ─────────────────────────────────────────────────────────────────────

BUILD_DIR   = ROOT / "build-gcc"
REPORT_DIR  = ROOT / "coverage-reports" / "gcov"
VENV_DIR    = ROOT / ".coverage-venv"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _c(code: str, text: str) -> str:
    if SYSTEM == "Windows" and not os.environ.get("WT_SESSION"):
        return text
    return f"\033[{code}m{text}\033[0m"

def banner(msg: str) -> None:
    print(f"\n{_c('36', '─' * 60)}")
    print(f"{_c('36', f'  gcov: {msg}')}")
    print(f"{_c('36', '─' * 60)}")

def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, streaming output. Raises on non-zero exit."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(_c("31", f"  [ERROR] command failed (exit {result.returncode})"))
        sys.exit(result.returncode)
    return result

def cpu_count() -> int:
    return os.cpu_count() or 2

def find_gcc() -> str:
    """
    Return the GCC C++ binary to use.
    - macOS: prefers the highest Homebrew g++-N over Apple's 'g++' shim.
    - Linux: prefers g++-14 → g++-13 → g++ to avoid GCC 13 C++23/<cmath> bugs
             (GCC 13 generates calls to nextafterf16/__builtin_nextafterf16b
              which are absent from its own runtime; fixed in GCC 14).
    """
    if SYSTEM == "Darwin":
        brew = shutil.which("brew")
        if brew:
            try:
                prefix = subprocess.check_output([brew, "--prefix"], text=True).strip()
                bin_dir = Path(prefix) / "bin"
                versioned = sorted(bin_dir.glob("g++-[0-9]*"), reverse=True)
                if versioned:
                    return str(versioned[0])
            except subprocess.CalledProcessError:
                pass
    elif SYSTEM == "Linux":
        for ver in ("16", "15", "14", "13"):
            binary = shutil.which(f"g++-{ver}")
            if binary:
                return binary
    return "g++"

def find_gcovr() -> str:
    """
    Return the gcovr binary to use.
    Priority: project venv → system PATH.
    """
    venv_gcovr = (
        VENV_DIR / ("Scripts" if SYSTEM == "Windows" else "bin") / (
            "gcovr.exe" if SYSTEM == "Windows" else "gcovr"
        )
    )
    if venv_gcovr.exists():
        return str(venv_gcovr)
    sys_gcovr = shutil.which("gcovr")
    if sys_gcovr:
        return sys_gcovr
    print(_c("31", "  [ERROR] gcovr not found. Run: python scripts/check_prereqs.py --install"))
    sys.exit(1)

def find_test_binary() -> Path:
    if SYSTEM == "Windows":
        # Multi-config generators put the binary under Debug/
        candidates = [
            BUILD_DIR / "tests" / "Debug" / "tests.exe",
            BUILD_DIR / "tests" / "tests.exe",
        ]
    else:
        candidates = [BUILD_DIR / "tests" / "tests"]
    for c in candidates:
        if c.exists():
            return c
    # Not built yet — return the most likely path (cmake --build will create it)
    return candidates[0]

# ── Pipeline steps ────────────────────────────────────────────────────────────

def step_configure(gcc_bin: str) -> None:
    banner("CMake configure (GCC)")
    cmd = [
        "cmake", "-B", str(BUILD_DIR),
        "-DCOVERAGE_GCOV=ON",
        "-DCMAKE_BUILD_TYPE=Debug",
        f"-DCMAKE_CXX_COMPILER={gcc_bin}",
    ]
    # Derive C compiler from the C++ compiler name:
    #   /opt/homebrew/bin/g++-15 → /opt/homebrew/bin/gcc-15
    #   g++ → gcc
    gcc_c = str(gcc_bin).replace("g++", "gcc")
    if not (shutil.which(gcc_c) or Path(gcc_c).exists()):
        gcc_c = "gcc"
    cmd.append(f"-DCMAKE_C_COMPILER={gcc_c}")
    run(cmd, cwd=ROOT)

def step_build() -> None:
    banner("Build")
    run(["cmake", "--build", str(BUILD_DIR), f"-j{cpu_count()}"], cwd=ROOT)

def step_test(test_bin: Path) -> None:
    banner("Run tests")
    run([str(test_bin)], cwd=ROOT)

def step_gcovr(gcovr_bin: str, gcc_bin: str) -> None:
    banner("Generate gcovr report")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # gcovr needs to know which gcov binary matches the compiler.
    # Derive gcov binary from the C++ compiler name:
    #   g++-15  → gcov-15
    #   g++     → gcov
    gcov_bin = "gcov"
    bin_name = Path(gcc_bin).name  # e.g. "g++-15" or "g++"
    if "-" in bin_name:
        major = bin_name.rsplit("-", 1)[-1]
        candidate_name = f"gcov-{major}"
        candidate_path = Path(gcc_bin).parent / candidate_name
        if candidate_path.exists():
            gcov_bin = str(candidate_path)
        elif shutil.which(candidate_name):
            gcov_bin = candidate_name

    run([
        gcovr_bin,
        "--root",             str(ROOT),
        "--object-directory", str(BUILD_DIR),
        f"--gcov-executable={gcov_bin}",
        "--exclude",          r"tests/.*",
        "--exclude",          r".*catch.*",
        "--exclude",          r".*_deps.*",
        "--html-details",     str(REPORT_DIR / "index.html"),
        "--txt",              str(REPORT_DIR / "summary.txt"),
        "--json-summary",     str(REPORT_DIR / "summary.json"),
        "--json",             str(REPORT_DIR / "lines.json"),
        "--print-summary",
    ], cwd=ROOT)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="GCC + gcovr coverage pipeline")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Non-interactive mode (for CI)")
    parser.add_argument("--install", action="store_true",
                        help="Auto-install missing tools (requires --non-interactive)")
    parser.add_argument("--skip-prereqs", action="store_true",
                        help="Skip the prerequisite check step")
    args = parser.parse_args()

    # Optional prereq check
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

    gcc_bin   = find_gcc()
    gcovr_bin = find_gcovr()

    print(f"\n  Using compiler : {gcc_bin}")
    print(f"  Using gcovr    : {gcovr_bin}")

    step_configure(gcc_bin)
    step_build()
    test_bin = find_test_binary()
    step_test(test_bin)
    step_gcovr(gcovr_bin, gcc_bin)

    print(_c("32", f"\n  [DONE] gcov pipeline complete"))
    print(f"    HTML   : {REPORT_DIR / 'index.html'}")
    print(f"    Summary: {REPORT_DIR / 'summary.txt'}")
    print(f"    JSON   : {REPORT_DIR / 'summary.json'}")
    print(f"    Lines  : {REPORT_DIR / 'lines.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
