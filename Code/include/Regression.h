/// @file Regression.h
/// @brief Подгонка линейной, экспоненциальной и логарифмической моделей WABT(t) на индексном отрезке.

#pragma once

#include "DegradationTypes.h"

#include <vector>

namespace degr {

/// Набор методов регрессии по выборке `samples` на индексах `[start_idx, end_idx]`.
class Regression {
public:
    /// @param samples Полный ряд точек.
    /// @param start_idx Начало отрезка (включительно).
    /// @param end_idx Конец отрезка (включительно).
    /// @return Результат линейной модели \( y = a t + b \); `valid_t == false` при вырожденной системе.
    [[nodiscard]] FitResult fit_linear(const std::vector<Sample>& samples,
                                       std::size_t start_idx,
                                       std::size_t end_idx) const;

    /// @param samples Полный ряд точек.
    /// @param start_idx Начало отрезка (включительно).
    /// @param end_idx Конец отрезка (включительно).
    /// @return Экспоненциальная модель после линеаризации по `ln(y)`; малые/нулевые y подрезаются для устойчивости.
    [[nodiscard]] FitResult fit_exponential(const std::vector<Sample>& samples,
                                              std::size_t start_idx,
                                              std::size_t end_idx) const;

    /// @param samples Полный ряд точек.
    /// @param start_idx Начало отрезка (включительно).
    /// @param end_idx Конец отрезка (включительно).
    /// @return Логарифмическая модель \( y = a \ln(t+1) + b \).
    [[nodiscard]] FitResult fit_logarithmic(const std::vector<Sample>& samples,
                                            std::size_t start_idx,
                                            std::size_t end_idx) const;

    /// @param samples Полный ряд точек.
    /// @param start_idx Начало отрезка (включительно).
    /// @param end_idx Конец отрезка (включительно).
    /// @return Модель с минимальным RMSE среди трёх (только с `valid_t`).
    [[nodiscard]] FitResult fit_best(const std::vector<Sample>& samples,
                                     std::size_t start_idx,
                                     std::size_t end_idx) const;

    /// @param samples Полный ряд точек.
    /// @param start_idx Начало отрезка (включительно).
    /// @param end_idx Конец отрезка (включительно).
    /// @param policy_t Режим: авто или фиксированный тип модели.
    /// @return Подгонка согласно политике.
    [[nodiscard]] FitResult fit_for_policy(const std::vector<Sample>& samples,
                                           std::size_t start_idx,
                                           std::size_t end_idx,
                                           DegradationPolicy policy_t) const;

private:
};

}  // namespace degr
