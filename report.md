# C++ Coverage Tools Comparison Report

## 1. Introduction

This project demonstrates and compares three mainstream C++ coverage tools applied
to the same source base, built with three different compilers:

| Tool | Compiler | Version | Environment |
|---|---|---|---|
| [OpenCppCoverage](https://github.com/OpenCppCoverage/OpenCppCoverage) | MSVC | 19.44 / VS 2022 17.14 | Windows (Ninja build) |
| [gcov](https://gcc.gnu.org/onlinedocs/gcc/Gcov.html) + [gcovr](https://gcovr.com) | GCC | 16.1.1 | WSL FedoraLinux-44 |
| [llvm-cov](https://llvm.org/docs/CommandGuide/llvm-cov.html) | Clang | 22.1.6 | WSL FedoraLinux-44 |

All tests passed: **85 assertions in 29 test cases** across all three runs.

---

## 2. Results

### 2.1 Overall totals

| Tool | Line % | Branch % | Function % |
|---|---|---|---|
| OpenCppCoverage (MSVC) | **86.1%** (124/144) | N/A | N/A |
| gcov / gcovr (GCC) | **85.0%** (113/133) | **52.8%** (38/72) | **86.5%** (45/52) |
| llvm-cov (Clang) | **71.4%** (125/175) | **100.0%** (26/26) | **72.0%** (36/50) |

### 2.2 Per-file breakdown

#### OpenCppCoverage (line % only)

| File | Line % | Lines covered / total | Notes |
|---|---|---|---|
| `calculator.cpp` | 82.4% | — | `reset_history`, `to_degrees` not called |
| `math_utils.hpp` | **100%** | — | Dead functions (`is_prime`, `cube`) invisible |
| `shapes.cpp` | 62.9% | — | All `Triangle` methods uncalled |
| `shapes.hpp` | 50.0% | — | `Shape::reset()` inline body uncalled |
| `stack.hpp` | **100%** | — | `clear`, `peek_bottom` invisible (never instantiated) |
| `string_utils.hpp` | **100%** | — | `starts_with`, `ends_with`, `replace_all` invisible |
| `calculator.hpp` | **not listed** | — | Entire file invisible (inline only, never emitted to PDB) |

#### gcov / gcovr (GCC)

| File | Line % | Branch % | Function % |
|---|---|---|---|
| `calculator.cpp` | 80.8% (21/26) | 75.0% (3/4) | 77.8% (7/9) |
| `math_utils.hpp` | **100%** (32/32) | **93.8%** (15/16) | **100%** (15/15) |
| `shapes.cpp` | 62.1% (18/29) | 20.0% (6/30) | 66.7% (8/12) |
| `shapes.hpp` | 33.3% (1/3) | N/A | 50.0% (1/2) |
| `stack.hpp` | 95.5% (21/22) | 58.3% (7/12) | **100%** (7/7) |
| `string_utils.hpp` | 95.2% (20/21) | 70.0% (7/10) | **100%** (7/7) |
| **TOTAL** | **85.0%** | **52.8%** | **86.5%** |

#### llvm-cov (Clang)

| File | Region % | Line % | Branch % | Function % |
|---|---|---|---|---|
| `calculator.cpp` | 83.3% (10/12) | 82.4% (28/34) | **100%** (2/2) | 77.8% (7/9) |
| `calculator.hpp` | 0.0% (0/2) | 0.0% (0/6) | — | 0.0% (0/2) |
| `math_utils.hpp` | 97.3% (36/37) | 83.8% (31/37) | **100%** (16/16) | 90.0% (9/10) |
| `shapes.cpp` | 61.1% (11/18) | 62.9% (22/35) | — | 66.7% (8/12) |
| `shapes.hpp` | 0.0% (0/2) | 0.0% (0/2) | — | 0.0% (0/2) |
| `stack.hpp` | **100%** (11/11) | **100%** (17/17) | **100%** (4/4) | **100%** (5/5) |
| `string_utils.hpp` | 81.3% (13/16) | 61.4% (27/44) | **100%** (4/4) | 70.0% (7/10) |
| **TOTAL** | **82.7%** | **71.4%** | **100%** | **72.0%** |

---

## 3. Key Observations

### 3.1 Header-only dead code is invisible to OpenCppCoverage

OpenCppCoverage works through the PDB file. If a function is inline, `constexpr`, or from a
header and is **never called**, MSVC emits no debug info for it and it simply does not appear
in the PDB. As a result:

- `calculator.hpp` is **not listed at all** — the only executable code in it
  (`unreachable_lambda_wrapper`) was never called, so MSVC never emitted it.
- `string_utils.hpp` reports **100%** despite `starts_with`, `ends_with`, and `replace_all`
  being completely untested — those functions are invisible.
- `math_utils.hpp` reports **100%** despite `is_prime`, `cube`, `product3`, and `min_of`
  being untested.

**Conclusion:** OpenCppCoverage systematically over-reports coverage for header-heavy codebases.
It cannot distinguish "100% covered" from "nothing to cover here."

### 3.2 Uninstantiated template methods are invisible to all three tools

`Stack<T>::clear()` and `Stack<T>::peek_bottom()` were intentionally never called in tests.
All three tools report `stack.hpp` as either **100%** (OpenCppCoverage, llvm-cov) or **95.5%
line / 100% function** (gcov). None of them flag the two dead methods.

This is not a tool defect — it is correct behaviour: a template method that is never
instantiated generates no machine code and no debug info. There is physically nothing to
instrument. To catch this kind of gap, a static analysis tool is needed rather than a
dynamic coverage tool.

The 4.5% line gap gcov does report on `stack.hpp` comes from the `throw` lines inside
`pop()` and `top()` which gcov counts as uncovered branches (the exception path) not from
the missing template methods.

### 3.3 Branch coverage — a tale of two counting models

| Tool | Branches total | Branches covered | % |
|---|---|---|---|
| gcov | 72 | 38 | 52.8% |
| llvm-cov | 26 | 26 | 100% |

This is the most striking divergence. Both tools ran the **same tests** on the **same source**.

**gcov** counts branches at the basic-block level — every `if/else`, every exception-handling
path, every destructor call site, and even implicit branches injected by the compiler
(e.g. for `std::vector` reallocation checks inside `push_back`). This produces 72 branches,
many of which are never exercised because they are compiler-generated, not source-level.

`shapes.cpp` alone contributes 30 branches to gcov with only 20% covered — mostly because
gcov counts the exception-handling infrastructure around the `Triangle` methods as uncovered
branches, even though `Triangle` was never called.

**llvm-cov** uses source-based coverage and only counts branches that are explicitly visible
in the source: `if/else`, ternary operators, `&&`/`||` short-circuits, `switch` cases. It
produces 26 branches and reports 100% — because every `if` that our tests reach does exercise
both sides (e.g., `clamp`'s three paths, `divide`'s zero-check, `factorial`'s base case).

**Which is more useful?** For most developers, llvm-cov's branch count is more actionable —
it maps directly to logic you wrote. gcov's implicit branches are harder to reason about
and can give a misleadingly low branch percentage.

### 3.4 `if constexpr` branches — gcov over-reports, llvm-cov is precise

`safe_negate<T>` uses `if constexpr`. Tests instantiate it with both `int` and `unsigned int`,
covering both compile-time paths.

- **gcov** reports `math_utils.hpp` at 93.8% branch coverage — it sees one branch as
  uncovered. This is the discarded branch of `if constexpr` in the **other** instantiation:
  for `safe_negate<int>`, the unsigned branch is discarded; gcov still counts it.
- **llvm-cov** reports **100% branches** on `math_utils.hpp` — source-based coverage correctly
  excludes discarded `if constexpr` branches from the coverage map entirely.

### 3.5 `if consteval` block — universally uncovered, correctly

`checked_factorial` contains an `if consteval { ... } else { ... }` block. Tests only
exercise the runtime path (the `else` branch). Both gcov and llvm-cov report the
compile-time `if consteval` block as not covered, which is correct — it can never execute
at runtime by definition. This is one of the few areas where both tools agree completely.

### 3.6 `constexpr` dead functions — gcov counts them, OpenCppCoverage and llvm-cov do not

`is_prime`, `cube`, `product3`, `min_of` are header-only functions never called in tests.

- **gcov** includes them in `math_utils.hpp`'s function count (15 total / 15 covered = 100%)
  — wait, gcov also reports 100% function coverage for `math_utils.hpp`. This means gcov
  is also not counting the dead constexpr/inline functions as "missing."
- **llvm-cov** reports 90% function coverage on `math_utils.hpp` (9/10) — it detects
  exactly **one** missing function. Given the file contains `is_prime` (never called),
  `cube`, `product3`, `min_of`, and `compile_time_square` (consteval, uncallable), the
  fact that only 1 is flagged as missed suggests llvm-cov merges some of the dead inline
  functions or only counts instantiated ones.

The key takeaway: **none of the tools reliably flag dead constexpr/inline functions**.
llvm-cov comes closest with its per-region tracking.

### 3.7 Virtual dispatch and uncalled overrides

`Triangle` overrides `area()`, `perimeter()`, and `describe()` — all untested.
`Shape::reset()` has an inline default body — never called.

- **gcov**: `shapes.cpp` at 62.1% line / 20% branch (the 30 branches are mostly
  compiler-injected exception paths around the 4 untested Triangle methods).
- **llvm-cov**: `shapes.cpp` at 62.9% line / 66.7% function — cleaner signal.
- **OpenCppCoverage**: `shapes.cpp` at 62.9% — consistent with llvm-cov since no implicit
  branches inflate the number.
- **shapes.hpp** (contains `Shape::reset() {}`):
  - OpenCppCoverage: 50% — sees the inline empty body as a line.
  - gcov: 33.3% line / 50% function — slightly different counting of blank lines.
  - llvm-cov: 0% regions / 0% lines — the two pure virtual declarations and `reset()`
    register as regions; since `reset()` is never called, all are 0%.

---

## 4. CMake Integration Complexity

| Tool | Extra CMake flags | Post-build steps | Notes |
|---|---|---|---|
| OpenCppCoverage | None | None (wraps the binary externally) | Requires no recompilation |
| gcov | `--coverage -O0 -g -fno-inline` (compile + link) | `gcovr` command after test run | Clean and well-supported |
| llvm-cov | `-fprofile-instr-generate -fcoverage-mapping -O0 -g` (compile + link) | `llvm-profdata merge` then `llvm-cov report/show` | Extra merge step; versioned binaries needed on Fedora (`llvm-cov-22`) |

---

## 5. Conclusion & Recommendations

| Criterion | Winner | Notes |
|---|---|---|
| **Line coverage accuracy** | llvm-cov | Reports lines including those in headers; not fooled by PDB gaps |
| **Branch coverage accuracy** | llvm-cov | Source-level branches only; gcov counts implicit compiler branches |
| **Function coverage accuracy** | llvm-cov | Per-instantiation tracking; catches more gaps in templates |
| **`if constexpr` handling** | llvm-cov | Correctly excludes discarded branches |
| **`if consteval` handling** | tie (gcov / llvm-cov) | Both correctly mark compile-time block as uncovered |
| **Header-only / inline code** | gcov > llvm-cov >> OpenCppCoverage | OpenCppCoverage misses dead header code entirely |
| **Ease of setup** | OpenCppCoverage | Zero CMake changes; any Debug MSVC binary works |
| **Windows-only / no recompile** | OpenCppCoverage | Only viable option in this scenario |
| **Linux / CI pipeline** | llvm-cov or gcov | Both work well; llvm-cov preferred for accuracy |
| **Most actionable output** | llvm-cov | Region-level HTML; per-instantiation views |

### Recommended strategy

- **Development (local, fast feedback):** OpenCppCoverage — zero friction, no rebuild needed.
- **CI gate / PR coverage check:** llvm-cov — most accurate line + branch + function metrics.
- **GCC-only environments:** gcov + gcovr — solid line/function coverage; treat branch % as
  a rough guide only due to implicit branch inflation.
- **Never rely on OpenCppCoverage alone for header-heavy C++ projects** — dead inline and
  constexpr functions will be silently omitted, inflating reported coverage.
