#pragma once

#include <vector>
#include <stdexcept>
#include <cstddef>

// ═══════════════════════════════════════════════════════════════════════════
// Classic template class  template <typename T>   (C++11)
// Demonstrates per-method coverage gaps on a templated class.
// ═══════════════════════════════════════════════════════════════════════════

/// Generic LIFO stack.
/// TESTED: push, pop, top, empty, size — all exercised.
/// NOT TESTED: clear(), peek_bottom() — intentional gaps.
template <typename T>
class Stack
{
public:
    /// Push a value onto the stack.
    void push(const T& val)
    {
        data_.push_back(val);
    }

    /// Push by move.
    void push(T&& val)
    {
        data_.push_back(std::move(val));
    }

    /// Remove and return the top element.
    /// Throws std::underflow_error if empty.
    T pop()
    {
        if (data_.empty())
            throw std::underflow_error("Stack::pop() called on empty stack");
        T val = std::move(data_.back());
        data_.pop_back();
        return val;
    }

    /// Access the top element without removing it.
    /// Throws std::underflow_error if empty.
    const T& top() const
    {
        if (data_.empty())
            throw std::underflow_error("Stack::top() called on empty stack");
        return data_.back();
    }

    /// Returns true if the stack is empty.
    bool empty() const { return data_.empty(); }

    /// Returns the number of elements.
    std::size_t size() const { return data_.size(); }

    // ── NOT TESTED methods (intentional gaps) ─────────────────────────────

    /// Remove all elements. NOT TESTED.
    void clear() { data_.clear(); }

    /// Access the bottom element without removing it. NOT TESTED.
    const T& peek_bottom() const
    {
        if (data_.empty())
            throw std::underflow_error("Stack::peek_bottom() called on empty stack");
        return data_.front();
    }

private:
    std::vector<T> data_;
};
