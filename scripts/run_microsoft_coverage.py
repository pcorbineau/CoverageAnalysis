#!/usr/bin/env python3
"""
run_microsoft_coverage.py
Windows-only MSVC + Microsoft.CodeCoverage.Console coverage pipeline.

On non-Windows platforms this script exits immediately with a clear message
(exit code 0) so it can be called unconditionally in cross-platform scripts.

Steps (Windows only):
  1. Locate MSVC via vswhere.exe and load the x64 environment
  2. Detect generator: Ninja (build-msvc-coverage/) if available, VS 17 2022 otherwise
  3. CMake configure + build (Debug) with COVERAGE_MSVC=ON
  4. Run Microsoft.CodeCoverage.Console collect
     → Cobertura XML (coverage-reports/microsoft/coverage.xml)
     → XML summary source (coverage-reports/microsoft/coverage.xml)
  5. Generate summary.json and a minimal HTML index page

Usage:
  python scripts/run_microsoft_coverage.py
  python scripts/run_microsoft_coverage.py --non-interactive
  python scripts/run_microsoft_coverage.py --skip-prereqs
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEM = platform.system()

if SYSTEM != "Windows":
    print(f"  [INFO] run_microsoft_coverage.py: Microsoft Code Coverage is Windows-only. Skipped on {SYSTEM}.")
    sys.exit(0)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPORT_DIR = ROOT / "coverage-reports" / "microsoft"
SETTINGS_PATH = REPORT_DIR / "codecoverage.runsettings"


def _c(code: str, text: str) -> str:
    if not os.environ.get("WT_SESSION"):
        return text
    return f"\033[{code}m{text}\033[0m"


def banner(msg: str) -> None:
    print(f"\n{_c('34', '─' * 60)}")
    print(f"{_c('34', f'  microsoft: {msg}')}")
    print(f"{_c('34', '─' * 60)}")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(_c("31", f"  [ERROR] command failed (exit {result.returncode})"))
        sys.exit(result.returncode)
    return result


def cpu_count() -> int:
    return os.cpu_count() or 2


def load_msvc_env() -> None:
    banner("Loading MSVC x64 environment")
    vswhere_candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
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

    env_dump = subprocess.check_output(
        f'"{vcvarsall}" x64 > nul 2>&1 && set',
        shell=True,
        text=True,
    )
    for line in env_dump.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ[key] = value

    print(f"  {_c('32', '[OK]')} MSVC env loaded from {vcvarsall}")


def choose_generator() -> tuple[str, Path, Path]:
    if shutil.which("ninja"):
        build_dir = ROOT / "build-msvc-coverage"
        test_exe = build_dir / "tests" / "tests.exe"
        print(f"  [INFO] Ninja found — using generator 'Ninja' in {build_dir.name}/")
        return "Ninja", build_dir, test_exe

    build_dir = ROOT / "build-msvc-coverage-vs"
    test_exe = build_dir / "tests" / "Debug" / "tests.exe"
    print(f"  [INFO] Ninja not found — using 'Visual Studio 17 2022' in {build_dir.name}/")
    return "Visual Studio 17 2022", build_dir, test_exe


def find_codecoverage_console() -> str:
    candidates = []
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", ""))
    program_files = Path(os.environ.get("ProgramFiles", ""))
    for root in (program_files_x86, program_files):
        if not root:
            continue
        candidates.extend(
            sorted(
                root.glob("Microsoft Visual Studio/*/*/Common7/IDE/Extensions/Microsoft/CodeCoverage.Console/Microsoft.CodeCoverage.Console.exe"),
                reverse=True,
            )
        )

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    binary = shutil.which("Microsoft.CodeCoverage.Console")
    if binary:
        return binary

    print(_c("31", "  [ERROR] Microsoft.CodeCoverage.Console.exe not found. Install Visual Studio Code Coverage tools."))
    sys.exit(1)


def write_settings(build_dir: Path) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    xml = f"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<RunSettings>
  <DataCollectionRunSettings>
    <DataCollectors>
      <DataCollector friendlyName=\"Code Coverage\" uri=\"datacollector://Microsoft/CodeCoverage/2.0\" assemblyQualifiedName=\"Microsoft.VisualStudio.Coverage.DynamicCoverageDataCollector, Microsoft.VisualStudio.TraceCollector, Version=11.0.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a\">
        <Configuration>
          <Format>Cobertura</Format>
          <IncludeTestAssembly>False</IncludeTestAssembly>
          <CodeCoverage>
            <ModulePaths>
              <Include>
                <ModulePath>.*coverage_lib.*</ModulePath>
                <ModulePath>.*tests.*</ModulePath>
              </Include>
              <IncludeDirectories>
                <Directory Recursive=\"true\">{build_dir}</Directory>
              </IncludeDirectories>
            </ModulePaths>
            <Functions>
              <Exclude>
                <Function>^std::.*</Function>
                <Function>^ATL::.*</Function>
                <Function>^Catch::.*</Function>
                <Function>^testing::.*</Function>
                <Function>.*::__GetTestMethodInfo.*</Function>
              </Exclude>
            </Functions>
            <Sources>
              <Exclude>
                <Source>.*\\tests\\.*</Source>
                <Source>.*\\_deps\\.*</Source>
                <Source>.*catch.*</Source>
                <Source>.*\\Windows Kits\\.*</Source>
                <Source>.*\\MSVC\\.*</Source>
                <Source>.*\\VC\\Tools\\.*</Source>
              </Exclude>
            </Sources>
            <EnableStaticNativeInstrumentation>True</EnableStaticNativeInstrumentation>
            <EnableDynamicNativeInstrumentation>False</EnableDynamicNativeInstrumentation>
            <EnableStaticNativeInstrumentationRestore>True</EnableStaticNativeInstrumentationRestore>
          </CodeCoverage>
        </Configuration>
      </DataCollector>
    </DataCollectors>
  </DataCollectionRunSettings>
</RunSettings>
"""
    SETTINGS_PATH.write_text(xml, encoding="utf-8")
    print(f"  Written: {SETTINGS_PATH}")


def step_configure(generator: str, build_dir: Path) -> None:
    banner(f"CMake configure ({generator})")
    cmd = [
        "cmake",
        "-B",
        str(build_dir),
        "-DCMAKE_BUILD_TYPE=Debug",
        "-DCOVERAGE_MSVC=ON",
        "-DBUILD_TESTING=ON",
    ]
    if generator == "Ninja":
        cmd += ["-G", generator]
    else:
        cmd += ["-G", generator, "-A", "x64"]
    run(cmd, cwd=ROOT)


def step_build(build_dir: Path) -> None:
    banner("Build")
    run([
        "cmake",
        "--build",
        str(build_dir),
        "--config",
        "Debug",
        f"-j{cpu_count()}",
    ], cwd=ROOT)


def step_collect(codecov_bin: str, test_exe: Path) -> Path:
    banner("Collect coverage (Microsoft Code Coverage)")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    coverage_xml = REPORT_DIR / "coverage.xml"
    run([
        codecov_bin,
        "collect",
        f"--settings={SETTINGS_PATH}",
        f"--output={coverage_xml}",
        "--output-format=cobertura",
        str(test_exe),
    ], cwd=ROOT)
    print(f"  Written: {coverage_xml}")
    return coverage_xml


def _is_test_file(filename: str) -> bool:
    """Return True if the filename does NOT belong to project source (src/)."""
    normalised = filename.replace("\\", "/").lower()
    return "/src/" not in normalised


def write_summary(coverage_xml: Path) -> None:
    import re
    root = ET.parse(coverage_xml).getroot()

    lines_valid = 0
    lines_covered = 0
    branches_valid = 0
    branches_covered = 0
    functions_total = 0
    functions_covered = 0

    for cls in root.iter("class"):
        if _is_test_file(cls.attrib.get("filename", "")):
            continue

        lines_el = cls.find("lines")
        if lines_el is not None:
            for line_el in lines_el:
                lines_valid += 1
                if int(line_el.attrib.get("hits", 0)) > 0:
                    lines_covered += 1
                branch_str = line_el.attrib.get("condition-coverage", "")
                if branch_str:
                    m = re.search(r"\((\d+)/(\d+)\)", branch_str)
                    if m:
                        branches_covered += int(m.group(1))
                        branches_valid += int(m.group(2))

        methods = cls.find("methods")
        if methods is not None:
            for method in methods.findall("method"):
                functions_total += 1
                if float(method.attrib.get("line-rate", "0")) > 0.0:
                    functions_covered += 1

    line_rate = (lines_covered / lines_valid) if lines_valid else 0.0
    branch_rate = (branches_covered / branches_valid) if branches_valid else 0.0

    summary = {
        "line_total": lines_valid,
        "line_covered": lines_covered,
        "line_percent": round(line_rate * 100.0, 1),
        "branch_total": branches_valid,
        "branch_covered": branches_covered,
        "branch_percent": round(branch_rate * 100.0, 1),
        "function_total": functions_total,
        "function_covered": functions_covered,
        "function_percent": round((functions_covered / functions_total * 100.0) if functions_total else 0.0, 1),
    }

    (REPORT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (REPORT_DIR / "summary.txt").write_text(
        "\n".join(
            [
                f"Line coverage    : {summary['line_covered']}/{summary['line_total']} ({summary['line_percent']:.1f}%)",
                f"Branch coverage  : {summary['branch_covered']}/{summary['branch_total']} ({summary['branch_percent']:.1f}%)",
                f"Function coverage: {summary['function_covered']}/{summary['function_total']} ({summary['function_percent']:.1f}%)",
            ]
        ) + "\n",
        encoding="utf-8",
    )


def write_index() -> None:
    html = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Microsoft Code Coverage</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #F5F5F7; color: #1D1D1F; margin: 0; padding: 2rem; }
    .card { max-width: 720px; margin: 0 auto; background: white; border-radius: 14px; padding: 1.5rem; box-shadow: 0 2px 10px rgba(0,0,0,.08); }
    h1 { margin-top: 0; }
    ul { line-height: 1.8; }
    a { color: #0071E3; text-decoration: none; }
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>Microsoft Code Coverage</h1>
    <p>This pipeline exports Cobertura XML for native C++ coverage using <code>Microsoft.CodeCoverage.Console</code>.</p>
    <ul>
      <li><a href=\"coverage.xml\">coverage.xml</a></li>
      <li><a href=\"summary.json\">summary.json</a></li>
      <li><a href=\"summary.txt\">summary.txt</a></li>
    </ul>
  </div>
</body>
</html>
"""
    (REPORT_DIR / "index.html").write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="MSVC + Microsoft Code Coverage pipeline (Windows only)")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--skip-prereqs", action="store_true")
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
    codecov_bin = find_codecoverage_console()
    generator, build_dir, test_exe = choose_generator()
    write_settings(build_dir)
    step_configure(generator, build_dir)
    step_build(build_dir)
    coverage_xml = step_collect(codecov_bin, test_exe)
    write_summary(coverage_xml)
    write_index()

    print(_c("32", "\n  [DONE] Microsoft Code Coverage pipeline complete"))
    print(f"    HTML   : {REPORT_DIR / 'index.html'}")
    print(f"    XML    : {REPORT_DIR / 'coverage.xml'}")
    print(f"    Summary: {REPORT_DIR / 'summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
