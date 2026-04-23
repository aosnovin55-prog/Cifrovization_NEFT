/// @file PeriodDetector.cpp
/// @brief Детектор границ периодов и слияние коротких сегментов.

#include "PeriodDetector.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

namespace {

/// Сшивает отрезки короче порога с соседним, чтобы стабилизировать регрессию.
/// @param[in,out] periods Список периодов (индексы в ряде).
/// @param window_size Используется для вычисления минимальной длины сегмента.
void merge_short_periods(std::vector<degr::Period>& periods, std::size_t window_size) {
    if (periods.size() <= 1) {
        return;
    }
    const std::size_t min_len = std::max<std::size_t>(window_size / 2, 32);
    bool changed = true;
    while (changed) {
        changed = false;
        for (std::size_t i = 0; i < periods.size(); ++i) {
            const std::size_t len = periods[i].end_index_t - periods[i].start_index_t + 1;
            if (len >= min_len) {
                continue;
            }
            if (i + 1 < periods.size()) {
                periods[i].end_index_t = periods[i + 1].end_index_t;
                periods.erase(periods.begin() + static_cast<std::ptrdiff_t>(i) + 1);
            } else if (i > 0) {
                periods[i - 1].end_index_t = periods[i].end_index_t;
                periods.erase(periods.begin() + static_cast<std::ptrdiff_t>(i));
            } else {
                break;
            }
            changed = true;
            break;
        }
    }
}

}  // namespace

namespace degr {

PeriodDetector::PeriodDetector(std::size_t window_size, double slope_jump_threshold)
    : window_size_(std::max<std::size_t>(window_size, 8)),
      slope_jump_threshold_(slope_jump_threshold) {}

std::vector<Period> PeriodDetector::detect(const std::vector<Sample>& samples) const {
    std::vector<Period> periods;
    if (samples.size() < window_size_ + 2) {
        periods.push_back({0, samples.empty() ? 0 : samples.size() - 1});
        return periods;
    }

    std::vector<std::size_t> boundaries;
    boundaries.push_back(0);

    const std::size_t half = window_size_ / 2;
    for (std::size_t i = half; i + half < samples.size(); ++i) {
        const double left_dt = samples[i].time_step_t - samples[i - half].time_step_t;
        const double right_dt = samples[i + half].time_step_t - samples[i].time_step_t;
        if (left_dt <= 0.0 || right_dt <= 0.0) {
            continue;
        }
        const double left_slope = (samples[i].wabt_t - samples[i - half].wabt_t) / left_dt;
        const double right_slope = (samples[i + half].wabt_t - samples[i].wabt_t) / right_dt;
        if (std::abs(right_slope - left_slope) >= slope_jump_threshold_) {
            if (boundaries.empty() || (i - boundaries.back()) > window_size_) {
                boundaries.push_back(i);
            }
        }
    }

    boundaries.push_back(samples.size() - 1);
    for (std::size_t i = 0; i + 1 < boundaries.size(); ++i) {
        std::size_t start = boundaries[i];
        std::size_t end = boundaries[i + 1];
        if (i + 2 < boundaries.size()) {
            end -= 1;
        }
        if (end > start) {
            periods.push_back({start, end});
        }
    }

    if (periods.empty()) {
        periods.push_back({0, samples.size() - 1});
    }
    merge_short_periods(periods, window_size_);
    return periods;
}

}  // namespace degr
