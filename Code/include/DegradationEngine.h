/// @file DegradationEngine.h
/// @brief Оркестрация: детектор периодов + регрессия + прогноз шагов до лимита по последнему периоду.

#pragma once

#include "PeriodDetector.h"
#include "Regression.h"

namespace degr {

/// Ядро анализа деградации WABT по одному ряду и технологическому лимиту.
class DegradationEngine {
public:
    /// @param detector Стратегия разбиения на периоды (копируется).
    /// @param regression Подгонка моделей (копируется).
    /// @param policy_t Как выбирать модель на каждом периоде.
    DegradationEngine(PeriodDetector detector = PeriodDetector(),
                      Regression regression = Regression(),
                      DegradationPolicy policy_t = DegradationPolicy::Auto);

    /// @param samples Ряд измерений; пустой ряд даёт пустой результат без исключений.
    /// @param limit Целевой верхний WABT (технологическое ограничение).
    /// @return Периоды с подгонками, последнее значение, прогноз шагов до лимита (−1 если не определён).
    [[nodiscard]] AnalysisResult analyze(const std::vector<Sample>& samples, double limit) const;

private:
    PeriodDetector detector_;
    Regression regression_;
    DegradationPolicy policy_t_;
};

}  // namespace degr
