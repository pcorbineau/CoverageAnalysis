#include "shapes.hpp"

#include <numbers>    // std::numbers::pi  (C++20)
#include <cmath>
#include <sstream>

// ── Shape (base) ──────────────────────────────────────────────────────────

std::string Shape::describe() const
{
    return "Shape (base)";
}

// ── Circle ────────────────────────────────────────────────────────────────

Circle::Circle(double radius) : radius_(radius) {}

double Circle::area() const
{
    return std::numbers::pi * radius_ * radius_;
}

double Circle::perimeter() const
{
    return 2.0 * std::numbers::pi * radius_;
}

std::string Circle::describe() const
{
    std::ostringstream oss;
    oss << "Circle(r=" << radius_ << ")";
    return oss.str();
}

// ── Rectangle ─────────────────────────────────────────────────────────────

Rectangle::Rectangle(double width, double height)
    : width_(width), height_(height) {}

double Rectangle::area() const
{
    return width_ * height_;
}

double Rectangle::perimeter() const
{
    return 2.0 * (width_ + height_);
}

// describe() not overridden → Shape::describe() is called — covered in tests.

// ── Triangle — NOT TESTED ─────────────────────────────────────────────────

Triangle::Triangle(double a, double b, double c) : a_(a), b_(b), c_(c) {}

double Triangle::area() const
{
    double s = (a_ + b_ + c_) / 2.0;
    return std::sqrt(s * (s - a_) * (s - b_) * (s - c_));
}

double Triangle::perimeter() const
{
    return a_ + b_ + c_;
}

std::string Triangle::describe() const
{
    std::ostringstream oss;
    oss << "Triangle(" << a_ << ", " << b_ << ", " << c_ << ")";
    return oss.str();
}
