#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>

#include "math_utils.hpp"

// ─────────────────────────────────────────────────────────────────────────────
// constexpr  factorial
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("factorial", "[math][constexpr]")
{
    SECTION("base cases")
    {
        CHECK(factorial(0) == 1);
        CHECK(factorial(1) == 1);
    }
    SECTION("positive values")
    {
        CHECK(factorial(5)  == 120);
        CHECK(factorial(10) == 3628800);
    }
    // is_prime is NOT tested — intentional gap
}

// ─────────────────────────────────────────────────────────────────────────────
// constexpr  power
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("power", "[math][constexpr]")
{
    SECTION("zero exponent always returns 1")
    {
        CHECK(power(2LL, 0)  == 1);
        CHECK(power(0LL, 0)  == 1);
    }
    SECTION("negative exponent returns 0")
    {
        CHECK(power(5LL, -1) == 0);
    }
    SECTION("positive exponent")
    {
        CHECK(power(2LL, 10) == 1024);
        CHECK(power(3LL, 4)  == 81);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Classic template  clamp<T>
// Tested only with double — clamp<int> is never instantiated (visible in
// llvm-cov per-instantiation report).
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("clamp", "[math][template]")
{
    SECTION("below lower bound") { CHECK(clamp(1.0, 2.0, 5.0) == 2.0); }
    SECTION("within range")      { CHECK(clamp(3.0, 2.0, 5.0) == 3.0); }
    SECTION("above upper bound") { CHECK(clamp(9.0, 2.0, 5.0) == 5.0); }
    // min_of<T> is NOT tested — intentional gap
}

// ─────────────────────────────────────────────────────────────────────────────
// Classic template  abs_val<T>
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("abs_val", "[math][template]")
{
    CHECK(abs_val(-5)    == 5);
    CHECK(abs_val(3)     == 3);
    CHECK(abs_val(0)     == 0);
    CHECK(abs_val(-3.14) == Catch::Approx(3.14));
}

// ─────────────────────────────────────────────────────────────────────────────
// Abbreviated templates  (C++20  auto param)
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("square (abbreviated template)", "[math][auto_template]")
{
    CHECK(square(4)    == 16);
    CHECK(square(2.5)  == Catch::Approx(6.25));
    // cube() and product3() are NOT tested — intentional gaps
}

TEST_CASE("sum3 (abbreviated template)", "[math][auto_template]")
{
    CHECK(sum3(1, 2, 3)       == 6);
    CHECK(sum3(1.0, 2.0, 3.0) == Catch::Approx(6.0));
}

// ─────────────────────────────────────────────────────────────────────────────
// if constexpr  safe_negate<T>
// Both branches covered by instantiating with signed and unsigned types.
// Tools differ on whether compile-time branch selection is "branch coverage".
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("safe_negate (if constexpr)", "[math][if_constexpr]")
{
    SECTION("signed int  — returns -val")
    {
        CHECK(safe_negate(5)  == -5);
        CHECK(safe_negate(-3) == 3);
    }
    SECTION("unsigned int — returns 0")
    {
        CHECK(safe_negate(5u) == 0u);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// if constexpr  to_double<T>
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("to_double (if constexpr)", "[math][if_constexpr]")
{
    SECTION("bool path")
    {
        CHECK(to_double(true)  == Catch::Approx(1.0));
        CHECK(to_double(false) == Catch::Approx(0.0));
    }
    SECTION("general path")
    {
        CHECK(to_double(42)   == Catch::Approx(42.0));
        CHECK(to_double(3.14) == Catch::Approx(3.14));
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// if consteval  checked_factorial
// Only the runtime else-branch can be exercised here.
// The if-consteval block is compile-time only — never a runtime hit.
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("checked_factorial (if consteval)", "[math][if_consteval]")
{
    SECTION("runtime path — valid input")
    {
        CHECK(checked_factorial(5)  == 120);
        CHECK(checked_factorial(0)  == 1);
    }
    SECTION("runtime path — negative input returns -1")
    {
        CHECK(checked_factorial(-1) == -1);
    }
    // compile_time_square() is a consteval — cannot be called at runtime
    // → shown as not covered by all tools
}
