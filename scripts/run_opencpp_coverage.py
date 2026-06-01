#!/usr/bin/env python3
"""
run_opencpp_coverage.py
Windows-only MSVC + OpenCppCoverage coverage pipeline.

On non-Windows platforms this script exits immediately with a clear message
(exit code 0) so it can be called unconditionally in cross-platform scripts
without breaking anything.

Steps (Windows only):
  1. Locate MSVC via vswhere.exe and load the x64 environment
  2. Detect generator: Ninja (build-ninja/) if available, VS 17 2022 (build-msvc/)
  3. CMake configure + build (Debug)
  4. OpenCppCoverage.exe wrapping the test binary
     → HTML report   (coverage-reports/opencpp/index.html)
     → Cobertura XML (coverage-reports/opencpp/coverage.xml)

Usage:
  python scripts/run_opencpp_coverage.py
  python scripts/run_opencpp_coverage.py --non-interactive   # CI
  python scripts/run_opencpp_coverage.py --skip-prereqs
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).resolve().parent.parent
SYSTEM = platform.system()

# ── Non-Windows early exit ────────────────────────────────────────────────────

if SYSTEM != "Windows":
    print(f"  [INFO] run_opencpp_coverage.py: OpenCppCoverage is Windows-only. "
          f"Skipped on {SYSTEM}.")
    sys.exit(0)

# ── Paths ─────────────────────────────────────────────────────────────────────

REPORT_DIR = ROOT / "coverage-reports" / "opencpp"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _c(code: str, text: str) -> str:
    if not os.environ.get("WT_SESSION"):
        return text
    return f"\033[{code}m{text}\033[0m"

def banner(msg: str) -> None:
    print(f"\n{_c('33', '─' * 60)}")
    print(f"{_c('33', f'  opencpp: {msg}')}")
    print(f"{_c('33', '─' * 60)}")

def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(_c("31", f"  [ERROR] command failed (exit {result.returncode})"))
        sys.exit(result.returncode)
    return result

def cpu_count() -> int:
    return os.cpu_count() or 2

# ── MSVC environment loader ───────────────────────────────────────────────────

def load_msvc_env() -> None:
    """
    Locate vswhere.exe, find the latest Visual Studio installation,
    run vcvarsall.bat x64, and merge the resulting environment into
    the current process so subsequent subprocess calls inherit it.
    """
    banner("Loading MSVC x64 environment")

    vswhere_candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
        Path(os.environ.get("ProgramFiles", ""))       / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
    ]
    vswhere = next((p for p in vswhere_candidates if p.exists()), None)
    if vswhere is None:
        print(_c("31", "  [ERROR] vswhere.exe not found — is Visual Studio installed?"))
        sys.exit(1)

    try:
        vs_path = subprocess.check_output(
            [str(vswhere), "-latest", "-property", "installationPath"],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        print(_c("31", "  [ERROR] vswhere could not find a Visual Studio installation"))
        sys.exit(1)

    vcvarsall = Path(vs_path) / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
    if not vcvarsall.exists():
        print(_c("31", f"  [ERROR] vcvarsall.bat not found at {vcvarsall}"))
        sys.exit(1)

    # Dump the environment after running vcvarsall
    env_dump = subprocess.check_output(
        f'"{vcvarsall}" x64 > nul 2>&1 && set',
        shell=True, text=True,
    )
    for line in env_dump.splitlines():
        if "=" in line:
            key, _, val = line.partition("=")
            os.environ[key] = val

    print(f"  {_c('32', '[OK]')} MSVC env loaded from {vcvarsall}")


def ensure_opencpp_on_path() -> str:
    """Add OpenCppCoverage default install dir to PATH if needed. Return binary path."""
    default = Path("C:/Program Files/OpenCppCoverage")
    if default.exists() and str(default) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(default) + os.pathsep + os.environ["PATH"]
    binary = shutil.which("OpenCppCoverage")
    if binary is None:
        print(_c("31", "  [ERROR] OpenCppCoverage.exe not found on PATH. "
                       "Install via: choco install opencppcoverage"))
        sys.exit(1)
    return binary

# ── Generator selection ───────────────────────────────────────────────────────

def choose_generator() -> tuple[str, Path, Path]:
    """
    Returns (generator_name, build_dir, test_exe_path).
    Prefers Ninja when available; falls back to Visual Studio 17 2022.
    """
    if shutil.which("ninja"):
        build_dir = ROOT / "build-ninja"
        test_exe  = build_dir / "tests" / "tests.exe"
        print(f"  [INFO] Ninja found — using generator 'Ninja' in {build_dir.name}/")
        return "Ninja", build_dir, test_exe
    else:
        build_dir = ROOT / "build-msvc"
        test_exe  = build_dir / "tests" / "Debug" / "tests.exe"
        print(f"  [INFO] Ninja not found — using 'Visual Studio 17 2022' in {build_dir.name}/")
        return "Visual Studio 17 2022", build_dir, test_exe

# ── Pipeline steps ────────────────────────────────────────────────────────────

def step_configure(generator: str, build_dir: Path) -> None:
    banner(f"CMake configure ({generator})")
    cmd = [
        "cmake", "-B", str(build_dir),
        "-G", generator,
        "-DCMAKE_BUILD_TYPE=Debug",
    ]
    if generator != "Ninja":
        cmd += ["-A", "x64"]
    run(cmd, cwd=ROOT)

def step_build(build_dir: Path) -> None:
    banner("Build")
    run([
        "cmake", "--build", str(build_dir),
        "--config", "Debug",
        f"-j{cpu_count()}",
    ], cwd=ROOT)

def step_coverage(opencpp_bin: str, test_exe: Path) -> None:
    banner("Collect coverage (OpenCppCoverage)")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run([
        opencpp_bin,
        "--sources",          str(ROOT / "src"),
        "--excluded_sources", r".*_deps.*",
        "--excluded_sources", r".*catch.*",
        "--excluded_sources", r".*tests.*",
        "--excluded_sources", r".*Windows Kits.*",
        "--excluded_sources", r".*MSVC.*",
        "--export_type",      f"html:{REPORT_DIR}",
        "--export_type",      f"cobertura:{REPORT_DIR / 'coverage.xml'}",
        "--cover_children",
        "--",                 str(test_exe),
    ], cwd=ROOT)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="MSVC + OpenCppCoverage pipeline (Windows only)")
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

    load_msvc_env()
    opencpp_bin                = ensure_opencpp_on_path()
    generator, build_dir, test_exe = choose_generator()

    step_configure(generator, build_dir)
    step_build(build_dir)
    step_coverage(opencpp_bin, test_exe)

    print(_c("32", f"\n  [DONE] OpenCppCoverage pipeline complete"))
    print(f"    HTML : {REPORT_DIR / 'index.html'}")
    print(f"    XML  : {REPORT_DIR / 'coverage.xml'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
