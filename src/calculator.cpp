#include "calculator.hpp"

#include <numbers>   // std::numbers::pi  (C++20)
#include <stdexcept>

// ── Arithmetic ────────────────────────────────────────────────────────────

double Calculator::add(double a, double b)
{
    last_result_ = a + b;
    return last_result_;
}

double Calculator::subtract(double a, double b)
{
    last_result_ = a - b;
    return last_result_;
}

double Calculator::multiply(double a, double b)
{
    last_result_ = a * b;
    return last_result_;
}

double Calculator::divide(double a, double b)
{
    if (b == 0.0)
        throw std::invalid_argument("Calculator::divide — division by zero");
    last_result_ = a / b;
    return last_result_;
}

// ── State ─────────────────────────────────────────────────────────────────

double Calculator::last_result() const
{
    return last_result_;
}

/// NOT TESTED — intentional gap.
void Calculator::reset_history()
{
    last_result_ = 0.0;
}

// ── Higher-order ──────────────────────────────────────────────────────────

double Calculator::apply(double a, double b,
                          const std::function<double(double, double)>& op)
{
    last_result_ = op(a, b);
    return last_result_;
}

// ── Static ────────────────────────────────────────────────────────────────

double Calculator::to_radians(double degrees)
{
    return degrees * std::numbers::pi / 180.0;
}

/// NOT TESTED — intentional gap.
double Calculator::to_degrees(double radians)
{
    return radians * 180.0 / std::numbers::pi;
}
