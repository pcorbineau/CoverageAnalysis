#pragma once

#include <type_traits>

// ═══════════════════════════════════════════════════════════════════════════
// constexpr functions (C++11)
// Interesting for coverage: some tools count them as covered when evaluated
// at compile time; others require a runtime call to report them as covered.
// ═══════════════════════════════════════════════════════════════════════════

/// Recursive factorial. TESTED — both n==0 and n>0 branches are exercised.
constexpr long long factorial(int n)
{
    if (n <= 0) return 1LL;
    return static_cast<long long>(n) * factorial(n - 1);
}

/// Integer power. TESTED.
constexpr long long power(long long base, int exp)
{
    if (exp == 0)  return 1LL;
    if (exp < 0)   return 0LL;          // branch: negative exponent
    return base * power(base, exp - 1);
}

/// Primality test. NOT TESTED — intentional gap.
/// Shows how tools report a completely dead constexpr function.
constexpr bool is_prime(int n)
{
    if (n < 2) return false;
    for (int i = 2; i * i <= n; ++i)
        if (n % i == 0) return false;
    return true;
}

// ═══════════════════════════════════════════════════════════════════════════
// Classic template functions  template <typename T>   (C++11)
// ═══════════════════════════════════════════════════════════════════════════

/// Clamp val into [lo, hi]. TESTED with double (3 branches: below/within/above).
/// Never instantiated with int → shows per-instantiation gap in llvm-cov.
template <typename T>
inline T clamp(T val, T lo, T hi)
{
    if (val < lo) return lo;
    if (val > hi) return hi;
    return val;
}

/// Absolute value. TESTED with both signed and unsigned types.
template <typename T>
inline T abs_val(T val)
{
    return val < T{0} ? -val : val;
}

/// Minimum of two values. NOT TESTED — intentional gap.
/// Never instantiated at all — unambiguous dead template.
template <typename T>
inline T min_of(T a, T b)
{
    return a < b ? a : b;
}

// ═══════════════════════════════════════════════════════════════════════════
// Abbreviated function templates  auto param  (C++20)
// ═══════════════════════════════════════════════════════════════════════════

/// Square. TESTED.
inline auto square(auto x) { return x * x; }

/// Cube. NOT TESTED — intentional gap.
inline auto cube(auto x) { return x * x * x; }

/// Sum of three values (multi-param abbreviated template). TESTED.
inline auto sum3(auto a, auto b, auto c) { return a + b + c; }

/// Product of three. NOT TESTED — intentional gap.
inline auto product3(auto a, auto b, auto c) { return a * b * c; }

// ═══════════════════════════════════════════════════════════════════════════
// if constexpr  (C++17)
// Both branches instantiated via different T: tools differ on whether
// compile-time branch selection counts as "branch coverage".
// ═══════════════════════════════════════════════════════════════════════════

/// Returns 0 for unsigned types, -val for signed types.
/// TESTED: called with int (signed branch) AND unsigned int (unsigned branch).
template <typename T>
constexpr T safe_negate(T val)
{
    if constexpr (std::is_unsigned_v<T>)
        return T{0};    // branch A — unsigned path
    else
        return -val;    // branch B — signed path
}

/// Converts a value to double, treating booleans specially.
/// TESTED: called with bool (true branch) AND double (false branch).
template <typename T>
constexpr double to_double(T val)
{
    if constexpr (std::is_same_v<T, bool>)
        return val ? 1.0 : 0.0;   // branch A — bool path
    else
        return static_cast<double>(val);  // branch B — general path
}

// ═══════════════════════════════════════════════════════════════════════════
// if consteval  (C++23)
// The compile-time block is unreachable at runtime by definition.
// Shows how each tool handles a branch that can physically never execute
// at runtime.
// ═══════════════════════════════════════════════════════════════════════════

/// Factorial with compile-time validation vs runtime fallback.
/// TESTED at runtime → runtime else-branch is covered.
/// The if-consteval block is compile-time only → never a runtime hit.
constexpr int checked_factorial(int n)
{
    if consteval {
        // Compile-time path: strict error on negative input.
        // No tool should report this as a runtime coverage gap,
        // but many will — that is the point of the demo.
        if (n < 0) throw "checked_factorial: negative input at compile time";
        return static_cast<int>(factorial(n));
    } else {
        // Runtime path — exercised in tests.
        if (n < 0) return -1;
        return static_cast<int>(factorial(n));
    }
}

/// Compile-time-only consteval function (C++20 consteval keyword).
/// Cannot be called at runtime at all → always dead from runtime perspective.
/// NOT TESTED at runtime — shows as uncovered in all tools.
consteval int compile_time_square(int n) { return n * n; }
