#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>

#include "shapes.hpp"

#include <numbers>   // std::numbers::pi

// ─────────────────────────────────────────────────────────────────────────────
// Circle — all overrides exercised
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("Circle::area", "[shapes][virtual]")
{
    Circle c(5.0);
    CHECK(c.area() == Catch::Approx(std::numbers::pi * 25.0));
}

TEST_CASE("Circle::perimeter", "[shapes][virtual]")
{
    Circle c(5.0);
    CHECK(c.perimeter() == Catch::Approx(2.0 * std::numbers::pi * 5.0));
}

TEST_CASE("Circle::describe (override)", "[shapes][virtual]")
{
    Circle c(3.0);
    CHECK(c.describe() == "Circle(r=3)");
}

// ─────────────────────────────────────────────────────────────────────────────
// Rectangle — area + perimeter exercised; describe() NOT overridden.
// Calling describe() on a Rectangle exercises Shape::describe() (base body).
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("Rectangle::area", "[shapes][virtual]")
{
    Rectangle r(4.0, 6.0);
    CHECK(r.area() == Catch::Approx(24.0));
}

TEST_CASE("Rectangle::perimeter", "[shapes][virtual]")
{
    Rectangle r(4.0, 6.0);
    CHECK(r.perimeter() == Catch::Approx(20.0));
}

TEST_CASE("Shape::describe via Rectangle (base virtual)", "[shapes][virtual]")
{
    // Rectangle does not override describe() → Shape::describe() body is hit.
    Rectangle r(4.0, 6.0);
    CHECK(r.describe() == "Shape (base)");
}

// ─────────────────────────────────────────────────────────────────────────────
// Polymorphic dispatch — exercises virtual calls through a base pointer
// ─────────────────────────────────────────────────────────────────────────────
TEST_CASE("Polymorphic area via Shape*", "[shapes][virtual][polymorphism]")
{
    Circle    c(1.0);
    Rectangle r(2.0, 3.0);

    Shape* shapes[] = { &c, &r };

    CHECK(shapes[0]->area() == Catch::Approx(std::numbers::pi));
    CHECK(shapes[1]->area() == Catch::Approx(6.0));
}

// Shape::reset() is NOT tested — intentional gap (virtual with default impl).
// Triangle (and all its overrides) is NOT tested — intentional gap.
