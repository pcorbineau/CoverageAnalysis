#!/usr/bin/env python3
"""
check_prereqs.py
Cross-platform prerequisite checker for the coverage analysis project.

Checks for all required tools, reports missing ones, then optionally
installs them — always asking the user first unless --non-interactive is given.

Isolation strategy:
  - Python tools (gcovr) → project-local venv at .coverage-venv/
  - C++ compilers        → Homebrew (macOS), apt (Linux), MSVC (Windows)

Usage:
  python scripts/check_prereqs.py                # interactive
  python scripts/check_prereqs.py --non-interactive --install  # CI / unattended
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

# ── Project layout ────────────────────────────────────────────────────────────

ROOT      = Path(__file__).resolve().parent.parent
VENV_DIR  = ROOT / ".coverage-venv"
SYSTEM    = platform.system()   # "Darwin", "Linux", "Windows"

# ── Console helpers ───────────────────────────────────────────────────────────

def _c(code: str, text: str) -> str:
    """ANSI colour — disabled on Windows unless WT/ANSI is available."""
    if SYSTEM == "Windows" and not os.environ.get("WT_SESSION"):
        return text
    return f"\033[{code}m{text}\033[0m"

def ok(label: str, detail: str = "") -> None:
    print(f"  {_c('32', '[OK]')    }  {label:<26} {detail}")

def warn(label: str, detail: str = "") -> None:
    print(f"  {_c('33', '[WARN]')  }  {label:<26} {detail}")

def err(label: str, detail: str = "") -> None:
    print(f"  {_c('31', '[ERROR]') }  {label:<26} {detail}")

def info(msg: str) -> None:
    print(f"  {_c('36', '[INFO]')  }  {msg}")

def header(msg: str) -> None:
    print(f"\n  {'─' * 58}")
    print(f"  {msg}")
    print(f"  {'─' * 58}")

# ── Version extraction ────────────────────────────────────────────────────────

_VER_RE = re.compile(r"(\d+\.\d+(?:\.\d+)*)")

def extract_version(text: str) -> Optional[str]:
    m = _VER_RE.search(text)
    return m.group(1) if m else None

def run_version(*cmd: str) -> Optional[str]:
    try:
        out = subprocess.check_output(list(cmd), stderr=subprocess.STDOUT, text=True)
        return extract_version(out)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))

# ── Tool lookup ───────────────────────────────────────────────────────────────

def find_cmd(*candidates: str) -> Optional[str]:
    """Return the first candidate found on PATH (or as an absolute path)."""
    for c in candidates:
        if shutil.which(c):
            return c
    return None

def homebrew_prefix() -> Optional[str]:
    """Return Homebrew prefix if brew is available."""
    brew = shutil.which("brew")
    if not brew:
        return None
    try:
        return subprocess.check_output([brew, "--prefix"], text=True).strip()
    except subprocess.CalledProcessError:
        return None

def llvm_bin_dir() -> Optional[Path]:
    """
    Return the directory containing llvm-cov / llvm-profdata.
    Priority:
      1. Already on PATH
      2. Homebrew llvm formula prefix (macOS)
      3. /usr/lib/llvm-*/bin (Linux apt multi-version)
    """
    if shutil.which("llvm-cov"):
        return None  # already on PATH; no prefix needed

    if SYSTEM == "Darwin":
        prefix = homebrew_prefix()
        if prefix:
            candidate = Path(prefix) / "opt" / "llvm" / "bin"
            if (candidate / "llvm-cov").exists():
                return candidate

    if SYSTEM == "Linux":
        for d in sorted(Path("/usr/lib").glob("llvm-*/bin"), reverse=True):
            if (d / "llvm-cov").exists():
                return d

    return None

# ── venv management ───────────────────────────────────────────────────────────

def venv_python() -> Path:
    if SYSTEM == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"

def venv_bin(tool: str) -> Path:
    if SYSTEM == "Windows":
        return VENV_DIR / "Scripts" / (tool + ".exe")
    return VENV_DIR / "bin" / tool

def ensure_venv() -> bool:
    """Create the project venv if it doesn't exist. Return True on success."""
    if venv_python().exists():
        return True
    info(f"Creating project venv at {VENV_DIR} ...")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
        )
        # Upgrade pip silently
        subprocess.run(
            [str(venv_python()), "-m", "pip", "install", "--upgrade", "pip"],
            check=True, capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        err("venv", f"Could not create: {exc}")
        return False

def install_into_venv(package: str) -> bool:
    if not ensure_venv():
        return False
    info(f"Installing {package} into {VENV_DIR} ...")
    try:
        subprocess.run(
            [str(venv_python()), "-m", "pip", "install", "--upgrade", package],
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        err(package, "pip install failed")
        return False

# ── Platform installers ───────────────────────────────────────────────────────

def brew_install(formula: str) -> bool:
    brew = shutil.which("brew")
    if not brew:
        err("brew", "Homebrew not found — cannot install " + formula)
        return False
    info(f"brew install {formula} ...")
    result = subprocess.run([brew, "install", formula])
    return result.returncode == 0

def apt_install(*packages: str) -> bool:
    info(f"apt-get install {' '.join(packages)} ...")
    result = subprocess.run(
        ["sudo", "apt-get", "install", "-y"] + list(packages)
    )
    return result.returncode == 0

def choco_install(package: str) -> bool:
    choco = shutil.which("choco")
    if not choco:
        err("choco", "Chocolatey not found — cannot install " + package)
        return False
    info(f"choco install {package} ...")
    result = subprocess.run([choco, "install", package, "--no-progress", "-y"])
    return result.returncode == 0

# ── C++23 compile test ────────────────────────────────────────────────────────

CPP23_SRC = """\
constexpr int f(int n) {
    if consteval { return n * 2; }
    else         { return n + 1; }
}
int main() { return f(0); }
"""

def check_cpp23(compiler: str, label: str) -> None:
    if not shutil.which(compiler):
        return
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "test.cpp"
        src.write_text(CPP23_SRC)
        out = Path(tmp) / "test_out"
        result = subprocess.run(
            [compiler, "-std=c++23", "-o", str(out), str(src)],
            capture_output=True,
        )
        if result.returncode == 0:
            ok(f"{label} C++23", "if consteval compiles OK")
        else:
            warn(f"{label} C++23", "if consteval failed (need GCC ≥ 12 / Clang ≥ 14)")

# ── Individual checks ─────────────────────────────────────────────────────────

class CheckResult:
    def __init__(self) -> None:
        self.errors   = 0
        self.warnings = 0
        # Pending installs: list of (description, install_fn)
        self.pending: list[tuple[str, object]] = []

    def need(self, description: str, install_fn) -> None:
        self.pending.append((description, install_fn))

    def error(self) -> None:
        self.errors += 1

    def warning(self) -> None:
        self.warnings += 1


def check_cmake(r: CheckResult) -> None:
    v = run_version("cmake", "--version")
    if v is None:
        err("cmake", "NOT FOUND")
        r.error()
        if SYSTEM == "Darwin":
            r.need("cmake  (brew install cmake)", lambda: brew_install("cmake"))
        elif SYSTEM == "Linux":
            r.need("cmake  (apt-get install cmake)", lambda: apt_install("cmake"))
        return
    if version_tuple(v) >= (3, 20):
        ok("cmake", v)
    else:
        warn("cmake", f"{v}  (need ≥ 3.20)")
        r.warning()


def check_gcc(r: CheckResult) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (gcc_bin, gcov_bin) — the actual versioned binaries found.
    On macOS, `g++` is Apple Clang; we look for Homebrew gcc-* instead.
    """
    # Prefer versioned Homebrew names on macOS
    gcc_candidates = ["g++"]
    gcov_candidates = ["gcov"]

    if SYSTEM == "Darwin":
        prefix = homebrew_prefix()
        if prefix:
            bin_dir = Path(prefix) / "bin"
            # Look for g++-N (C++ compiler), not gcc-N (C compiler)
            versioned = sorted(bin_dir.glob("g++-[0-9]*"), reverse=True)
            if versioned:
                gcc_candidates = [versioned[0].name] + gcc_candidates
            versioned_gcov = sorted(bin_dir.glob("gcov-[0-9]*"), reverse=True)
            if versioned_gcov:
                gcov_candidates = [versioned_gcov[0].name] + gcov_candidates

    gcc_bin  = find_cmd(*gcc_candidates)
    gcov_bin = find_cmd(*gcov_candidates)

    if gcc_bin is None:
        err("g++", "NOT FOUND")
        r.error()
        if SYSTEM == "Darwin":
            r.need("gcc  (brew install gcc)", lambda: brew_install("gcc"))
        elif SYSTEM == "Linux":
            r.need("g++  (apt-get install g++)", lambda: apt_install("g++", "gcc"))
        return None, None

    gcc_ver  = run_version(gcc_bin, "--version")
    # Sanity: reject Apple Clang pretending to be gcc
    try:
        raw = subprocess.check_output([gcc_bin, "--version"], stderr=subprocess.STDOUT, text=True)
        if "Apple clang" in raw or "Apple LLVM" in raw:
            warn("g++", f"{gcc_bin} is Apple Clang — GCC coverage requires a real GCC (brew install gcc)")
            r.warning()
            if SYSTEM == "Darwin":
                r.need("gcc  (brew install gcc)", lambda: brew_install("gcc"))
            return None, None
    except subprocess.CalledProcessError:
        pass

    ok("g++", f"{gcc_bin}  {gcc_ver}")

    if gcov_bin is None:
        err("gcov", "NOT FOUND")
        r.error()
        return gcc_bin, None

    gcov_ver = run_version(gcov_bin, "--version")
    ok("gcov", f"{gcov_bin}  {gcov_ver}")

    # Version match check
    if gcc_ver and gcov_ver:
        if gcc_ver.split(".")[0] == gcov_ver.split(".")[0]:
            ok("gcc/gcov version", f"match (major {gcc_ver.split('.')[0]})")
        else:
            err("gcc/gcov version", f"MISMATCH  g++={gcc_ver}  gcov={gcov_ver}  — .gcda files will be corrupt")
            r.error()

    return gcc_bin, gcov_bin


def check_gcovr(r: CheckResult) -> None:
    gcovr = venv_bin("gcovr")
    if gcovr.exists():
        v = run_version(str(gcovr), "--version")
        if v and version_tuple(v) >= (5, 0):
            ok("gcovr", f"{v}  (project venv)")
            return
        warn("gcovr", f"{v}  (need ≥ 5.0 — will reinstall)")

    # Fall back to system gcovr
    sys_gcovr = shutil.which("gcovr")
    if sys_gcovr:
        v = run_version(sys_gcovr, "--version")
        if v and version_tuple(v) >= (5, 0):
            ok("gcovr", f"{v}  (system)")
            return

    err("gcovr", "NOT FOUND in venv or on PATH")
    r.error()
    r.need("gcovr  (pip install gcovr into .coverage-venv)", lambda: install_into_venv("gcovr"))


def check_llvm(r: CheckResult) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (clang_bin, profdata_bin, llvmcov_bin)."""
    # --- clang++ ---
    clang_candidates = ["clang++"]
    if SYSTEM == "Darwin":
        prefix = homebrew_prefix()
        if prefix:
            llvm_clang = Path(prefix) / "opt" / "llvm" / "bin" / "clang++"
            if llvm_clang.exists():
                clang_candidates = [str(llvm_clang)] + clang_candidates

    clang_bin = find_cmd(*clang_candidates)
    if clang_bin is None:
        err("clang++", "NOT FOUND")
        r.error()
        if SYSTEM == "Darwin":
            r.need("llvm  (brew install llvm)", lambda: brew_install("llvm"))
        elif SYSTEM == "Linux":
            r.need("clang/llvm  (apt-get install clang llvm)", lambda: apt_install("clang", "llvm"))
        return None, None, None

    clang_ver = run_version(clang_bin, "--version")
    clang_major = clang_ver.split(".")[0] if clang_ver else ""
    ok("clang++", f"{clang_bin}  {clang_ver}")

    # --- llvm-profdata ---
    llvm_dir  = llvm_bin_dir()
    candidates_profdata = (
        [str(llvm_dir / f"llvm-profdata-{clang_major}"),
         str(llvm_dir / "llvm-profdata")]
        if llvm_dir else
        [f"llvm-profdata-{clang_major}", "llvm-profdata"]
    )
    profdata_bin = find_cmd(*candidates_profdata)
    if profdata_bin is None:
        err("llvm-profdata", "NOT FOUND")
        r.error()
    else:
        pv = run_version(profdata_bin, "--version")
        ok("llvm-profdata", f"{profdata_bin}  {pv}")

    # --- llvm-cov ---
    candidates_cov = (
        [str(llvm_dir / f"llvm-cov-{clang_major}"),
         str(llvm_dir / "llvm-cov")]
        if llvm_dir else
        [f"llvm-cov-{clang_major}", "llvm-cov"]
    )
    llvmcov_bin = find_cmd(*candidates_cov)
    if llvmcov_bin is None:
        err("llvm-cov", "NOT FOUND")
        r.error()
    else:
        lv = run_version(llvmcov_bin, "--version")
        ok("llvm-cov", f"{llvmcov_bin}  {lv}")

    return clang_bin, profdata_bin, llvmcov_bin


def check_opencpp(r: CheckResult) -> None:
    if SYSTEM != "Windows":
        info("OpenCppCoverage — Windows only, skipped on this platform")
        return
    # Add default install path to search
    default = Path("C:/Program Files/OpenCppCoverage")
    if default.exists() and str(default) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(default) + os.pathsep + os.environ.get("PATH", "")
    if shutil.which("OpenCppCoverage"):
        ok("OpenCppCoverage", "found")
    else:
        err("OpenCppCoverage", "NOT FOUND")
        r.error()
        r.need("OpenCppCoverage  (choco install opencppcoverage)", lambda: choco_install("opencppcoverage"))


def check_python(r: CheckResult) -> None:
    py = sys.executable
    v  = run_version(py, "--version")
    ok("python", f"{py}  {v}")

# ── Prompt & install ──────────────────────────────────────────────────────────

def prompt_and_install(pending: list, non_interactive: bool, auto_install: bool) -> int:
    """Show pending installs, ask user, run them. Returns new error count."""
    if not pending:
        return 0

    print()
    print("  The following tools need to be installed:")
    for desc, _ in pending:
        print(f"    • {desc}")

    if non_interactive:
        if auto_install:
            info("--non-interactive --install: running installs automatically ...")
            do_install = True
        else:
            info("--non-interactive: skipping installs (pass --install to auto-install)")
            return len(pending)
    else:
        print()
        try:
            answer = input("  Proceed with installation? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            answer = "n"
        do_install = answer in ("y", "yes")

    if not do_install:
        warn("install", "Skipped — fix missing tools manually before running pipelines")
        return len(pending)

    new_errors = 0
    for desc, fn in pending:
        info(f"Installing: {desc} ...")
        try:
            success = fn()
            if not success:
                err(desc, "installation FAILED")
                new_errors += 1
            else:
                ok(desc, "installed")
        except Exception as exc:
            err(desc, f"installation FAILED: {exc}")
            new_errors += 1

    return new_errors

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Check coverage tool prerequisites")
    parser.add_argument(
        "--non-interactive", action="store_true",
        help="Do not prompt for input (used in CI)"
    )
    parser.add_argument(
        "--install", action="store_true",
        help="When --non-interactive is set, auto-install missing tools"
    )
    args = parser.parse_args()

    print()
    header(f"Coverage prerequisite check  —  {SYSTEM}")

    r = CheckResult()

    print()
    print("  ── Python environment ──────────────────────────────────")
    check_python(r)

    print()
    print("  ── Build system ────────────────────────────────────────")
    check_cmake(r)

    print()
    print("  ── GCC / gcov ──────────────────────────────────────────")
    gcc_bin, gcov_bin = check_gcc(r)
    check_gcovr(r)

    print()
    print("  ── Clang / LLVM ────────────────────────────────────────")
    clang_bin, profdata_bin, llvmcov_bin = check_llvm(r)

    print()
    print("  ── OpenCppCoverage (Windows only) ──────────────────────")
    check_opencpp(r)

    print()
    print("  ── C++23 compile tests ─────────────────────────────────")
    if gcc_bin:
        check_cpp23(gcc_bin, "g++")
    if clang_bin:
        check_cpp23(clang_bin, "clang++")

    # ── Install missing tools ─────────────────────────────────────────────────
    install_errors = prompt_and_install(r.pending, args.non_interactive, args.install)
    r.errors += install_errors

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print(f"  {'─' * 58}")
    if r.errors > 0:
        print(f"  {_c('31', 'Result')}: {r.errors} error(s),  {r.warnings} warning(s)  — fix errors before running.")
        return 1
    elif r.warnings > 0:
        print(f"  {_c('33', 'Result')}: 0 errors,  {r.warnings} warning(s)  — some features may be limited.")
        return 0
    else:
        print(f"  {_c('32', 'Result')}: all checks passed.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
