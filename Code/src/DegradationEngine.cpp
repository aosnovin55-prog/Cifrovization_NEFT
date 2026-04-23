/// @file DegradationEngine.cpp
/// @brief Анализ ряда: периоды, подгонки, экстраполяция до лимита по последнему сегменту.

#include "DegradationEngine.h"

#include <cmath>
#include <limits>

namespace degr {

DegradationEngine::DegradationEngine(PeriodDetector detector, Regression regression, DegradationPolicy policy_t)
    : detector_(std::move(detector)),
      regression_(std::move(regression)),
      policy_t_(policy_t) {}

AnalysisResult DegradationEngine::analyze(const std::vector<Sample>& samples, double limit) const {
    AnalysisResult result;
    result.limit_t = limit;
    if (samples.empty()) {
        return result;
    }

    result.last_value_t = samples.back().wabt_t;
    const auto periods = detector_.detect(samples);
    result.periods_t.reserve(periods.size());

    for (const auto& period : periods) {
        PeriodAnalysis item;
        item.period_t = period;
        item.best_fit_t =
            regression_.fit_for_policy(samples, period.start_index_t, period.end_index_t, policy_t_);
        result.periods_t.push_back(item);
    }

    if (!result.periods_t.empty()) {
        const auto& last_period = result.periods_t.back();
        const auto& fit = last_period.best_fit_t;
        if (fit.valid_t) {
            const double t0 = samples[last_period.period_t.end_index_t].time_step_t;
            const double y0 = fit.predict(t0);
            if (limit > y0) {
                if (fit.model_type_t == ModelType::Linear && fit.a_t > 1e-10) {
                    result.forecast_steps_to_limit_t = (limit - fit.b_t) / fit.a_t - t0;
                } else if (fit.model_type_t == ModelType::Exponential && fit.a_t > 0.0 && fit.b_t > 1e-10) {
                    result.forecast_steps_to_limit_t = std::log(limit / fit.a_t) / fit.b_t - t0;
                } else if (fit.model_type_t == ModelType::Logarithmic && fit.a_t > 1e-10) {
                    result.forecast_steps_to_limit_t = std::exp((limit - fit.b_t) / fit.a_t) - 1.0 - t0;
                }
            } else {
                result.forecast_steps_to_limit_t = 0.0;
            }
        }
    }

    if (!std::isfinite(result.forecast_steps_to_limit_t)) {
        result.forecast_steps_to_limit_t = -1.0;
    }
    return result;
}

}  // namespace degr
