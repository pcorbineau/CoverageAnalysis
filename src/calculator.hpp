#pragma once

#include <functional>
#include <stdexcept>

// ═══════════════════════════════════════════════════════════════════════════
// Calculator class — split across .hpp / .cpp
// Demonstrates coverage on regular member functions, static methods,
// and a method using an internal generic lambda.
// ═══════════════════════════════════════════════════════════════════════════

class Calculator
{
public:
    // ── Arithmetic ─────────────────────────────────────────────────────────
    /// TESTED.
    double add(double a, double b);
    /// TESTED.
    double subtract(double a, double b);
    /// TESTED.
    double multiply(double a, double b);
    /// TESTED — including the divide-by-zero exception path.
    double divide(double a, double b);

    // ── State ──────────────────────────────────────────────────────────────
    /// TESTED.
    double last_result() const;
    /// NOT TESTED — intentional gap on a regular member function.
    void reset_history();

    // ── Higher-order ───────────────────────────────────────────────────────
    /// Applies a binary operation supplied as a callable.
    /// TESTED with a lambda to show coverage of the internal generic lambda.
    double apply(double a, double b,
                 const std::function<double(double, double)>& op);

    // ── Static methods ─────────────────────────────────────────────────────
    /// Convert degrees to radians. TESTED.
    static double to_radians(double degrees);
    /// Convert radians to degrees. NOT TESTED — intentional gap.
    static double to_degrees(double radians);

private:
    double last_result_ = 0.0;
};

// ═══════════════════════════════════════════════════════════════════════════
// Free function with an unreachable generic lambda (C++14 auto lambda).
// NOT TESTED — the entire function is dead code.
// Shows how each tool handles an uncalled inline function containing a lambda.
// ═══════════════════════════════════════════════════════════════════════════
inline double unreachable_lambda_wrapper(double x)
{
    // Generic lambda — never instantiated at all.
    auto scale = [](auto val, auto factor) { return val * factor; };
    return scale(x, 2.0);
}
