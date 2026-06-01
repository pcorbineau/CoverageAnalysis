# CoverageAnalysis

A comparison of four mainstream C++ code-coverage tools applied to the same source base.

| Tool | Compiler | Platform |
|---|---|---|
| gcov + gcovr | GCC | Linux |
| llvm-cov | Clang | Linux |
| OpenCppCoverage | MSVC | Windows |
| Visual Studio Coverage | MSVC | Windows |

The goal is to highlight how each tool counts lines, branches, and functions differently — particularly for header-only code, `constexpr`/`if constexpr`, templates, and virtual dispatch.

## Report

The full analysis is available on **[GitHub Pages](https://pcorbineau.github.io/CoverageAnalysis/)**.

## Usage

Check prerequisites (and optionally install missing tools):

```sh
python scripts/check_prereqs.py
python scripts/check_prereqs.py --install   # auto-install missing tools
```

Run all coverage pipelines:

```sh
python scripts/run_all.py
```

Run a specific tool:

```sh
python scripts/run_all.py --tools gcov
python scripts/run_all.py --tools llvm
python scripts/run_all.py --tools opencpp
python scripts/run_all.py --tools microsoft
```
