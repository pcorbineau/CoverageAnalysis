#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>

#include "calculator.hpp"
#include "stack.hpp"

// ─────────────────────────────────────────────────────────────────────────────
// Calculator — arithmetic
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("Calculator::add", "[calculator]")
{
    Calculator c;
    CHECK(c.add(2.0, 3.0)   == Catch::Approx(5.0));
    CHECK(c.add(-1.0, 1.0)  == Catch::Approx(0.0));
    CHECK(c.last_result()   == Catch::Approx(0.0));
}

TEST_CASE("Calculator::subtract", "[calculator]")
{
    Calculator c;
    CHECK(c.subtract(5.0, 3.0)  == Catch::Approx(2.0));
    CHECK(c.subtract(0.0, 4.0)  == Catch::Approx(-4.0));
}

TEST_CASE("Calculator::multiply", "[calculator]")
{
    Calculator c;
    CHECK(c.multiply(4.0, 3.0)  == Catch::Approx(12.0));
    CHECK(c.multiply(-2.0, 3.0) == Catch::Approx(-6.0));
    CHECK(c.multiply(0.0, 99.0) == Catch::Approx(0.0));
}

TEST_CASE("Calculator::divide", "[calculator]")
{
    Calculator c;
    SECTION("normal division")
    {
        CHECK(c.divide(10.0, 2.0) == Catch::Approx(5.0));
        CHECK(c.divide(7.0, 2.0)  == Catch::Approx(3.5));
    }
    SECTION("divide by zero throws")
    {
        CHECK_THROWS_AS(c.divide(1.0, 0.0), std::invalid_argument);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Calculator — apply (higher-order, uses a caller-supplied lambda)
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("Calculator::apply with lambda", "[calculator][lambda]")
{
    Calculator c;
    // Generic lambda passed as std::function
    auto add_op = [](double a, double b) { return a + b; };
    CHECK(c.apply(3.0, 4.0, add_op) == Catch::Approx(7.0));

    auto mul_op = [](double a, double b) { return a * b; };
    CHECK(c.apply(3.0, 4.0, mul_op) == Catch::Approx(12.0));
}

// ─────────────────────────────────────────────────────────────────────────────
// Calculator — static methods
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("Calculator::to_radians (static)", "[calculator][static]")
{
    CHECK(Calculator::to_radians(0.0)   == Catch::Approx(0.0));
    CHECK(Calculator::to_radians(180.0) == Catch::Approx(3.14159265).epsilon(1e-6));
    CHECK(Calculator::to_radians(360.0) == Catch::Approx(6.28318530).epsilon(1e-6));
}
// to_degrees() is NOT tested — intentional gap.
// reset_history() is NOT tested — intentional gap.
// unreachable_lambda_wrapper() is NOT tested — intentional gap.

// ─────────────────────────────────────────────────────────────────────────────
// Stack<T> — classic template class
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("Stack<int> basic operations", "[stack][template]")
{
    Stack<int> s;

    SECTION("empty stack")
    {
        CHECK(s.empty() == true);
        CHECK(s.size()  == 0);
    }

    SECTION("push and top")
    {
        s.push(10);
        s.push(20);
        CHECK(s.top()  == 20);
        CHECK(s.size() == 2);
    }

    SECTION("pop")
    {
        s.push(1);
        s.push(2);
        CHECK(s.pop() == 2);
        CHECK(s.pop() == 1);
        CHECK(s.empty() == true);
    }

    SECTION("pop on empty throws")
    {
        CHECK_THROWS_AS(s.pop(), std::underflow_error);
    }

    SECTION("top on empty throws")
    {
        CHECK_THROWS_AS(s.top(), std::underflow_error);
    }
}

TEST_CASE("Stack<std::string> push by move", "[stack][template]")
{
    Stack<std::string> s;
    std::string val = "hello";
    s.push(std::move(val));
    CHECK(s.top() == "hello");
}

// Stack::clear() and Stack::peek_bottom() are NOT tested — intentional gaps.
