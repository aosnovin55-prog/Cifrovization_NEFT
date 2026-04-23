/// @file Regression.cpp
/// @brief Реализация регрессий и методов `FitResult`.

#include "Regression.h"

#include <cmath>
#include <limits>
#include <sstream>

namespace degr {

/// @param x Аргумент \(t\) в том же масштабе, что у обучающих точек.
/// @return Значение выбранной модели; при невалидной подгонке — quiet NaN.
double FitResult::predict(double x) const {
    if (!valid_t) {
        return std::numeric_limits<double>::quiet_NaN();
    }
    if (model_type_t == ModelType::Linear) {
        return a_t * x + b_t;
    }
    if (model_type_t == ModelType::Exponential) {
        return a_t * std::exp(b_t * x);
    }
    return a_t * std::log(x + 1.0) + b_t;
}

/// @return Строка с подставленными коэффициентами для отчёта/JSON.
std::string FitResult::formula() const {
    std::ostringstream oss;
    if (model_type_t == ModelType::Linear) {
        oss << "WABT(t) = " << a_t << " * t + " << b_t;
    } else if (model_type_t == ModelType::Exponential) {
        oss << "WABT(t) = " << a_t << " * exp(" << b_t << " * t)";
    } else {
        oss << "WABT(t) = " << a_t << " * ln(t + 1) + " << b_t;
    }
    return oss.str();
}

namespace {

/// МНК для \( y \approx k x + c \).
/// @param x,y Одинаковая длина, не меньше двух точек.
/// @param k,c Выход: наклон и сдвиг.
/// @return `true` при невырожденной задаче.
bool fit_simple_linear(const std::vector<double>& x,
                       const std::vector<double>& y,
                       double& k,
                       double& c) {
    if (x.size() != y.size() || x.size() < 2) {
        return false;
    }
    double sum_x = 0.0;
    double sum_y = 0.0;
    double sum_xx = 0.0;
    double sum_xy = 0.0;
    const double n = static_cast<double>(x.size());

    for (std::size_t i = 0; i < x.size(); ++i) {
        sum_x += x[i];
        sum_y += y[i];
        sum_xx += x[i] * x[i];
        sum_xy += x[i] * y[i];
    }

    const double denom = (n * sum_xx - sum_x * sum_x);
    if (std::abs(denom) < 1e-12) {
        return false;
    }
    k = (n * sum_xy - sum_x * sum_y) / denom;
    c = (sum_y - k * sum_x) / n;
    return true;
}

/// RMSE подгонки на индексах `[start_idx, end_idx]`.
/// @param samples Исходный ряд.
/// @param start_idx,end_idx Границы включительно.
/// @param fit Уже обученная модель.
/// @return Корень из среднего квадрата ошибки; бесконечность при нуле точек.
double calc_rmse(const std::vector<Sample>& samples,
                 std::size_t start_idx,
                 std::size_t end_idx,
                 const FitResult& fit) {
    double sum_sq = 0.0;
    std::size_t n = 0;
    for (std::size_t i = start_idx; i <= end_idx; ++i) {
        const double y_hat = fit.predict(samples[i].time_step_t);
        const double err = samples[i].wabt_t - y_hat;
        sum_sq += err * err;
        ++n;
    }
    return n > 0 ? std::sqrt(sum_sq / static_cast<double>(n)) : std::numeric_limits<double>::infinity();
}

}  // namespace

FitResult Regression::fit_linear(const std::vector<Sample>& samples,
                                 std::size_t start_idx,
                                 std::size_t end_idx) const {
    FitResult fit;
    fit.model_type_t = ModelType::Linear;

    std::vector<double> x;
    std::vector<double> y;
    x.reserve(end_idx - start_idx + 1);
    y.reserve(end_idx - start_idx + 1);
    for (std::size_t i = start_idx; i <= end_idx; ++i) {
        x.push_back(samples[i].time_step_t);
        y.push_back(samples[i].wabt_t);
    }

    fit.valid_t = fit_simple_linear(x, y, fit.a_t, fit.b_t);
    if (fit.valid_t) {
        fit.rmse_t = calc_rmse(samples, start_idx, end_idx, fit);
    }
    return fit;
}

FitResult Regression::fit_exponential(const std::vector<Sample>& samples,
                                      std::size_t start_idx,
                                      std::size_t end_idx) const {
    FitResult fit;
    fit.model_type_t = ModelType::Exponential;

    std::vector<double> x;
    std::vector<double> y_log;
    x.reserve(end_idx - start_idx + 1);
    y_log.reserve(end_idx - start_idx + 1);

    for (std::size_t i = start_idx; i <= end_idx; ++i) {
        x.push_back(samples[i].time_step_t);
        const double y_pos = std::max(samples[i].wabt_t, 1e-9);
        y_log.push_back(std::log(y_pos));
    }

    double k = 0.0;
    double c = 0.0;
    fit.valid_t = fit_simple_linear(x, y_log, k, c);
    if (fit.valid_t) {
        fit.a_t = std::exp(c);
        fit.b_t = k;
        fit.rmse_t = calc_rmse(samples, start_idx, end_idx, fit);
    }
    return fit;
}

FitResult Regression::fit_logarithmic(const std::vector<Sample>& samples,
                                      std::size_t start_idx,
                                      std::size_t end_idx) const {
    FitResult fit;
    fit.model_type_t = ModelType::Logarithmic;

    std::vector<double> x_log;
    std::vector<double> y;
    x_log.reserve(end_idx - start_idx + 1);
    y.reserve(end_idx - start_idx + 1);

    for (std::size_t i = start_idx; i <= end_idx; ++i) {
        x_log.push_back(std::log(samples[i].time_step_t + 1.0));
        y.push_back(samples[i].wabt_t);
    }

    fit.valid_t = fit_simple_linear(x_log, y, fit.a_t, fit.b_t);
    if (fit.valid_t) {
        fit.rmse_t = calc_rmse(samples, start_idx, end_idx, fit);
    }
    return fit;
}

FitResult Regression::fit_best(const std::vector<Sample>& samples,
                               std::size_t start_idx,
                               std::size_t end_idx) const {
    const FitResult linear = fit_linear(samples, start_idx, end_idx);
    const FitResult exponential = fit_exponential(samples, start_idx, end_idx);
    const FitResult logarithmic = fit_logarithmic(samples, start_idx, end_idx);

    FitResult best;
    best.valid_t = false;
    best.rmse_t = std::numeric_limits<double>::infinity();
    for (const auto& candidate : {linear, exponential, logarithmic}) {
        if (candidate.valid_t && candidate.rmse_t < best.rmse_t) {
            best = candidate;
        }
    }
    return best;
}

FitResult Regression::fit_for_policy(const std::vector<Sample>& samples,
                                     std::size_t start_idx,
                                     std::size_t end_idx,
                                     DegradationPolicy policy_t) const {
    switch (policy_t) {
        case DegradationPolicy::Auto:
            return fit_best(samples, start_idx, end_idx);
        case DegradationPolicy::LinearOnly:
            return fit_linear(samples, start_idx, end_idx);
        case DegradationPolicy::ExponentialOnly:
            return fit_exponential(samples, start_idx, end_idx);
        case DegradationPolicy::LogarithmicOnly:
            return fit_logarithmic(samples, start_idx, end_idx);
    }
    return fit_best(samples, start_idx, end_idx);
}

}  // namespace degr
