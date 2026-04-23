/// @file PeriodDetector.h
/// @brief Детектор смены режима по скачку наклона WABT; склейка слишком коротких периодов.

#pragma once

#include "DegradationTypes.h"

#include <vector>

namespace degr {

/// Разбиение ряда на периоды почти постоянного тренда между «разрывами» наклона.
class PeriodDetector {
public:
    /// @param window_size Размер окна (точек) для оценки левого/правого наклона; не меньше 8.
    /// @param slope_jump_threshold Минимальный |Δнаклона| для фиксации границы режима.
    PeriodDetector(std::size_t window_size = 56, double slope_jump_threshold = 0.03);

    /// @param samples Входной ряд (монотонный `time_step_t` предпочтителен для корректных dt).
    /// @return Список непересекающихся периодов, покрывающих индексы от 0 до n−1 после слияния коротких отрезков.
    [[nodiscard]] std::vector<Period> detect(const std::vector<Sample>& samples) const;

private:
    std::size_t window_size_;       ///< Сглаженное окно для сравнения наклонов.
    double slope_jump_threshold_;   ///< Порог разницы наклонов для новой границы.
};

}  // namespace degr
