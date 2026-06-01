#pragma once

#include <string>

// ═══════════════════════════════════════════════════════════════════════════
// Shape hierarchy — virtual / override coverage demo
//
// Base class:  Shape
//   virtual describe()  — has default implementation — TESTED via Circle
//   virtual reset()     — has default implementation — NOT TESTED
//
// Derived (TESTED):   Circle, Rectangle
// Derived (NOT TESTED): Triangle  — all overrides dead code
// ═══════════════════════════════════════════════════════════════════════════

class Shape
{
public:
    virtual ~Shape() = default;

    // Pure virtual — no body; tools must not count these as covered/uncovered.
    virtual double area()      const = 0;
    virtual double perimeter() const = 0;

    // Virtual with default implementation.
    // TESTED indirectly: Rectangle does NOT override this → base body runs.
    virtual std::string describe() const;

    // Virtual with inline default (empty body). NOT TESTED.
    virtual void reset() {}
};

// ── Circle ────────────────────────────────────────────────────────────────

class Circle : public Shape
{
public:
    explicit Circle(double radius);

    double area()      const override;   // TESTED
    double perimeter() const override;   // TESTED
    std::string describe() const override; // TESTED — overrides base
private:
    double radius_;
};

// ── Rectangle ─────────────────────────────────────────────────────────────

class Rectangle : public Shape
{
public:
    Rectangle(double width, double height);

    double area()      const override;   // TESTED
    double perimeter() const override;   // TESTED
    // describe() NOT overridden → base Shape::describe() will be called — TESTED
private:
    double width_;
    double height_;
};

// ── Triangle — NOT TESTED (intentional gap) ───────────────────────────────

class Triangle : public Shape
{
public:
    Triangle(double a, double b, double c);

    double area()      const override;   // NOT TESTED
    double perimeter() const override;   // NOT TESTED
    std::string describe() const override; // NOT TESTED
private:
    double a_, b_, c_;
};
