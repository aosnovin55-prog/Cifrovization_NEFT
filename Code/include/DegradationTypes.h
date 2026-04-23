/// @file DegradationTypes.h
/// @brief Доменные типы ряда WABT, периодов, моделей деградации и результата анализа.

#pragma once

#include <cstddef>
#include <limits>
#include <string>
#include <vector>

namespace degr {

/// Одна точка входного ряда (строка CSV `t,wabt`).
struct Sample {
    double time_step_t = std::numeric_limits<double>::quiet_NaN();  ///< Ось времени (обычно 0,1,2,… или произвольный шаг).
    double wabt_t = std::numeric_limits<double>::quiet_NaN();       ///< Значение WABT в этой точке.
};

/// Закрытый интервал индексов `[start_index_t, end_index_t]` в массиве `samples`.
struct Period {
    std::size_t start_index_t = 0;  ///< Индекс первой точки периода.
    std::size_t end_index_t = 0;    ///< Индекс последней точки периода.
};

/// Вид аппроксимации WABT(t) на периоде.
enum class ModelType {
    Linear,       ///< \( WABT = a t + b \)
    Exponential,  ///< \( WABT = a e^{b t} \)
    Logarithmic   ///< \( WABT = a \ln(t+1) + b \)
};

/// Режим выбора функции деградации на каждом периоде.
enum class DegradationPolicy {
    Auto,               ///< На каждом периоде выбирается модель с минимальным RMSE среди трёх.
    LinearOnly,         ///< Только линейная модель.
    ExponentialOnly,    ///< Только экспоненциальная.
    LogarithmicOnly     ///< Только логарифмическая.
};

/// @param policy_t Политика из перечисления.
/// @return Строка для JSON/CLI: `auto`, `linear_only`, …
[[nodiscard]] inline std::string to_string(DegradationPolicy policy_t) {
    switch (policy_t) {
        case DegradationPolicy::Auto:
            return "auto";
        case DegradationPolicy::LinearOnly:
            return "linear_only";
        case DegradationPolicy::ExponentialOnly:
            return "exponential_only";
        case DegradationPolicy::LogarithmicOnly:
            return "logarithmic_only";
    }
    return "unknown";
}

/// @param model_type_t Тип модели.
/// @return Строка для JSON: `linear`, `exponential`, `logarithmic`.
[[nodiscard]] inline std::string to_string(ModelType model_type_t) {
    switch (model_type_t) {
        case ModelType::Linear:
            return "linear";
        case ModelType::Exponential:
            return "exponential";
        case ModelType::Logarithmic:
            return "logarithmic";
    }
    return "unknown";
}

/// Результат подгонки одной модели на отрезке: коэффициенты, RMSE, пригодность.
struct FitResult {
    ModelType model_type_t = ModelType::Linear;                     ///< Выбранный тип модели.
    double a_t = std::numeric_limits<double>::quiet_NaN();          ///< Коэффициент `a` (смысл зависит от model_type_t).
    double b_t = std::numeric_limits<double>::quiet_NaN();          ///< Свободный член / второй параметр.
    double rmse_t = std::numeric_limits<double>::quiet_NaN();        ///< RMSE на отрезке; осмысленно при valid_t.
    bool valid_t = false;                                           ///< Удалось ли устойчиво оценить параметры.

    /// @param x Аргумент той же оси, что и `Sample::time_step_t`.
    /// @return Предсказанное WABT; при `!valid_t` — quiet NaN.
    [[nodiscard]] double predict(double x) const;

    /// @return Текстовая формула для отображения (не для вычислений).
    [[nodiscard]] std::string formula() const;
};

/// Один период и лучшая подгонка на нём (согласно политике движка).
struct PeriodAnalysis {
    Period period_t;        ///< Границы периода по индексам.
    FitResult best_fit_t;   ///< Итоговая модель и метрики.
};

/// Полный ответ ядра анализа по одному ряду и лимиту.
struct AnalysisResult {
    std::vector<PeriodAnalysis> periods_t;                          ///< Периоды с подобранными моделями.
    double limit_t = std::numeric_limits<double>::quiet_NaN();       ///< Поданный на вход технологический лимит WABT.
    double last_value_t = std::numeric_limits<double>::quiet_NaN(); ///< WABT последней точки ряда.
    /// Шагов по оси `t` до достижения лимита по модели последнего периода; `0` — уже у лимита/выше; `-1` — не вычислено.
    double forecast_steps_to_limit_t = std::numeric_limits<double>::quiet_NaN();
};

}  // namespace degr
