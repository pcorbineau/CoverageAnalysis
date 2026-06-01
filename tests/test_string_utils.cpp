#include <catch2/catch_test_macros.hpp>

#include "string_utils.hpp"

// ─────────────────────────────────────────────────────────────────────────────
// trim
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("trim", "[string]")
{
    SECTION("no whitespace")       { CHECK(trim("hello")         == "hello"); }
    SECTION("leading spaces")      { CHECK(trim("  hello")       == "hello"); }
    SECTION("trailing spaces")     { CHECK(trim("hello  ")       == "hello"); }
    SECTION("both sides")          { CHECK(trim("  hello  ")     == "hello"); }
    SECTION("tabs and newlines")   { CHECK(trim("\t hello \n")   == "hello"); }
    SECTION("all whitespace")      { CHECK(trim("   ")           == "");      }
    SECTION("empty string")        { CHECK(trim("")              == "");      }
}

// ─────────────────────────────────────────────────────────────────────────────
// to_upper / to_lower
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("to_upper", "[string]")
{
    CHECK(to_upper("hello")   == "HELLO");
    CHECK(to_upper("Hello")   == "HELLO");
    CHECK(to_upper("HELLO")   == "HELLO");
    CHECK(to_upper("")        == "");
}

TEST_CASE("to_lower", "[string]")
{
    CHECK(to_lower("HELLO")   == "hello");
    CHECK(to_lower("Hello")   == "hello");
    CHECK(to_lower("hello")   == "hello");
    CHECK(to_lower("")        == "");
}

// ─────────────────────────────────────────────────────────────────────────────
// contains
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("contains", "[string]")
{
    SECTION("found")     { CHECK(contains("hello world", "world") == true);  }
    SECTION("not found") { CHECK(contains("hello world", "xyz")   == false); }
    SECTION("empty sub") { CHECK(contains("hello", "")            == true);  }
}

// ─────────────────────────────────────────────────────────────────────────────
// repeat
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("repeat", "[string]")
{
    CHECK(repeat("ab", 3) == "ababab");
    CHECK(repeat("x",  1) == "x");
    CHECK(repeat("y",  0) == "");
}

// starts_with, ends_with, replace_all are NOT tested — intentional gaps.
