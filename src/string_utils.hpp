#pragma once

#include <string>
#include <algorithm>
#include <cctype>

// ═══════════════════════════════════════════════════════════════════════════
// Inline header-only string utilities
// ═══════════════════════════════════════════════════════════════════════════

/// Remove leading and trailing whitespace. TESTED (both branches).
inline std::string trim(const std::string& s)
{
    auto start = s.find_first_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) return "";      // branch: all-whitespace
    auto end = s.find_last_not_of(" \t\n\r\f\v");
    return s.substr(start, end - start + 1);
}

/// Convert to uppercase. TESTED.
inline std::string to_upper(std::string s)
{
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::toupper(c)); });
    return s;
}

/// Convert to lowercase. TESTED.
inline std::string to_lower(std::string s)
{
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

/// Returns true if s contains sub. TESTED (both branches).
inline bool contains(const std::string& s, const std::string& sub)
{
    return s.find(sub) != std::string::npos;
}

/// Returns true if s starts with prefix. NOT TESTED — intentional gap.
/// Unambiguous dead inline function.
inline bool starts_with(const std::string& s, const std::string& prefix)
{
    if (prefix.size() > s.size()) return false;
    return s.compare(0, prefix.size(), prefix) == 0;
}

/// Returns true if s ends with suffix. NOT TESTED — intentional gap.
inline bool ends_with(const std::string& s, const std::string& suffix)
{
    if (suffix.size() > s.size()) return false;
    return s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0;
}

/// Repeat a string n times. TESTED.
inline std::string repeat(const std::string& s, int n)
{
    std::string result;
    result.reserve(s.size() * static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) result += s;
    return result;
}

/// Replace all occurrences of from with to. NOT TESTED — intentional gap.
inline std::string replace_all(std::string s,
                                const std::string& from,
                                const std::string& to)
{
    if (from.empty()) return s;
    std::size_t pos = 0;
    while ((pos = s.find(from, pos)) != std::string::npos) {
        s.replace(pos, from.size(), to);
        pos += to.size();
    }
    return s;
}
