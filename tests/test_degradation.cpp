/// @file test_degradation.cpp
/// @brief GTest: деградация WABT, детектор периодов, граничные случаи.

#include "DegradationEngine.h"

#include <cmath>
#include <vector>

#include <gtest/gtest.h>

namespace {

/// Сравнение вещественных с допуском.
/// @param a,b Сравниваемые значения.
/// @param eps Допуск по модулю разности.
/// @return `true`, если \( |a-b| \le \varepsilon \).
bool near(double a, double b, double eps = 1e-3) {
    return std::abs(a - b) <= eps;
}

}  // namespace

/// Линейный рост: ожидается линейная модель и неотрицательный прогноз до лимита.
TEST(DegradationEngine, LinearSeriesFitsLinearModelAndPositiveForecast) {
    std::vector<degr::Sample> samples;
    for (int i = 0; i < 200; ++i) {
        const double t = static_cast<double>(i);
        const double y = 0.08 * t + 360.0;
        samples.push_back({t, y});
    }
    degr::DegradationEngine engine(degr::PeriodDetector(20, 0.8), degr::Regression());
    const auto result = engine.analyze(samples, 380.0);

    ASSERT_FALSE(result.periods_t.empty());
    const auto& fit = result.periods_t.back().best_fit_t;
    EXPECT_EQ(fit.model_type_t, degr::ModelType::Linear);
    EXPECT_TRUE(near(fit.a_t, 0.08, 0.01));
    EXPECT_GE(result.forecast_steps_to_limit_t, 0.0);
}

/// Два режима наклона: граница периода должна лежать около смены тренда (индекс ~120).
TEST(PeriodDetector, TwoRegimesSplitsNearIndex120) {
    std::vector<degr::Sample> samples;
    for (int i = 0; i < 240; ++i) {
        const double t = static_cast<double>(i);
        const double y = (i < 120) ? 360.0 + 0.05 * t : 366.0 + 0.2 * (t - 120.0);
        samples.push_back({t, y});
    }
    degr::PeriodDetector detector(24, 0.08);
    const auto periods = detector.detect(samples);

    ASSERT_GE(periods.size(), 2u);
    bool boundary_near_120 = false;
    for (std::size_t k = 0; k + 1 < periods.size(); ++k) {
        const std::size_t split = periods[k].end_index_t;
        if (split >= 105 && split <= 135) {
            boundary_near_120 = true;
            break;
        }
    }
    EXPECT_TRUE(boundary_near_120);
    EXPECT_EQ(periods.front().start_index_t, 0u);
    EXPECT_EQ(periods.back().end_index_t, samples.size() - 1);
}

/// Пустой ввод: нет периодов, `last_value` — NaN, лимит сохраняется.
TEST(DegradationEngine, EmptySamplesNoPeriodsAndNaNLastValue) {
    std::vector<degr::Sample> samples;
    degr::DegradationEngine engine;
    const auto result = engine.analyze(samples, 380.0);

    EXPECT_TRUE(result.periods_t.empty());
    EXPECT_TRUE(std::isnan(result.last_value_t));
    EXPECT_DOUBLE_EQ(result.limit_t, 380.0);
}

/// Политика только линейная: все периоды с линейной подгонкой.
TEST(DegradationEngine, LinearOnlyPolicyKeepsLinearFit) {
    std::vector<degr::Sample> samples;
    for (int i = 0; i < 200; ++i) {
        const double t = static_cast<double>(i);
        const double y = 0.08 * t + 360.0;
        samples.push_back({t, y});
    }
    degr::DegradationEngine engine(
        degr::PeriodDetector(20, 0.8),
        degr::Regression(),
        degr::DegradationPolicy::LinearOnly);
    const auto result = engine.analyze(samples, 380.0);
    ASSERT_FALSE(result.periods_t.empty());
    for (const auto& p : result.periods_t) {
        EXPECT_EQ(p.best_fit_t.model_type_t, degr::ModelType::Linear);
    }
}

/// Ряд выше лимита: прогноз шагов до лимита должен быть нулём.
TEST(DegradationEngine, LimitAlreadyExceededYieldsZeroForecast) {
    std::vector<degr::Sample> samples;
    for (int i = 0; i < 50; ++i) {
        samples.push_back({static_cast<double>(i), 400.0});
    }
    degr::DegradationEngine engine;
    const auto result = engine.analyze(samples, 380.0);

    EXPECT_DOUBLE_EQ(result.forecast_steps_to_limit_t, 0.0);
}
