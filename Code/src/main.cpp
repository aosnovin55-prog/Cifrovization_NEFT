/// @file main.cpp
/// @brief CLI `degradation_cli`: чтение CSV, запуск ядра, печать результата в JSON в stdout.

#include "DegradationEngine.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

/// Печатает число или JSON `null` для не-конечных значений.
/// @param out Поток вывода.
/// @param v Значение для сериализации.
void print_json_number(std::ostream& out, double v) {
    if (std::isfinite(v)) {
        out << v;
    } else {
        out << "null";
    }
}

/// Экранирование строки для поля JSON.
/// @param s Исходная строка (формула и т.п.).
/// @return Строка с экранированными кавычками и управляющими символами.
[[nodiscard]] std::string json_escape(const std::string& s) {
    std::string r;
    r.reserve(s.size() + 8);
    for (const char c : s) {
        switch (c) {
            case '"':
                r += "\\\"";
                break;
            case '\\':
                r += "\\\\";
                break;
            case '\n':
                r += "\\n";
                break;
            case '\r':
                r += "\\r";
                break;
            case '\t':
                r += "\\t";
                break;
            default:
                r += c;
        }
    }
    return r;
}

/// Разбор одной строки CSV по запятым (без кавычечного экранирования).
/// @param line Строка файла.
/// @return Список полей.
std::vector<std::string> split_csv(const std::string& line) {
    std::vector<std::string> out;
    std::stringstream ss(line);
    std::string item;
    while (std::getline(ss, item, ',')) {
        out.push_back(item);
    }
    return out;
}

/// Загрузка ряда из CSV с заголовком `t,wabt`.
/// @param path Путь к файлу.
/// @param[out] samples Накопление точек (обычно передают пустой вектор).
/// @return `true`, если прочитана хотя бы одна точка.
bool load_series(const std::string& path, std::vector<degr::Sample>& samples) {
    std::ifstream in(path);
    if (!in) {
        return false;
    }

    std::string line;
    std::getline(in, line);  // header
    while (std::getline(in, line)) {
        if (line.empty()) {
            continue;
        }
        auto cols = split_csv(line);
        if (cols.size() < 2) {
            continue;
        }
        degr::Sample s;
        s.time_step_t = std::stod(cols[0]);
        s.wabt_t = std::stod(cols[1]);
        samples.push_back(s);
    }
    return !samples.empty();
}

/// Разбор аргумента политики из командной строки.
/// @param arg Строка после пути к CSV и лимита.
/// @return Соответствующая `DegradationPolicy`; неизвестные имена трактуются как Auto.
[[nodiscard]] degr::DegradationPolicy parse_policy(const char* arg) {
    std::string s(arg);
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (s == "linear" || s == "linear_only") {
        return degr::DegradationPolicy::LinearOnly;
    }
    if (s == "exponential" || s == "exponential_only" || s == "exp") {
        return degr::DegradationPolicy::ExponentialOnly;
    }
    if (s == "logarithmic" || s == "logarithmic_only" || s == "log") {
        return degr::DegradationPolicy::LogarithmicOnly;
    }
    return degr::DegradationPolicy::Auto;
}

}  // namespace

/// Точка входа CLI.
/// @param argc Число аргументов.
/// @param argv `argv[1]` — CSV, `argv[2]` — лимит WABT, `argv[3]` — опционально политика.
/// @return 0 при успехе; 1 при неверном использовании; 2 при ошибке чтения CSV.
int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: degradation_cli <series.csv> <wabt_limit> [policy]\n";
        std::cerr << "CSV format: t,wabt\n";
        std::cerr << "policy: auto | linear | exponential | logarithmic (default: auto)\n";
        return 1;
    }

    std::vector<degr::Sample> samples;
    if (!load_series(argv[1], samples)) {
        std::cerr << "Cannot read input CSV: " << argv[1] << "\n";
        return 2;
    }

    const double limit = std::stod(argv[2]);
    const degr::DegradationPolicy policy = (argc >= 4) ? parse_policy(argv[3]) : degr::DegradationPolicy::Auto;
    degr::DegradationEngine engine(degr::PeriodDetector(), degr::Regression(), policy);
    const auto result = engine.analyze(samples, limit);

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "{\n";
    std::cout << "  \"degradation_policy\": \"" << degr::to_string(policy) << "\",\n";
    std::cout << "  \"limit\": ";
    print_json_number(std::cout, result.limit_t);
    std::cout << ",\n";
    std::cout << "  \"last_value\": ";
    print_json_number(std::cout, result.last_value_t);
    std::cout << ",\n";
    std::cout << "  \"forecast_steps_to_limit\": ";
    print_json_number(std::cout, result.forecast_steps_to_limit_t);
    std::cout << ",\n";
    std::cout << "  \"periods\": [\n";
    for (std::size_t i = 0; i < result.periods_t.size(); ++i) {
        const auto& p = result.periods_t[i];
        std::cout << "    {\n";
        std::cout << "      \"start_index\": " << p.period_t.start_index_t << ",\n";
        std::cout << "      \"end_index\": " << p.period_t.end_index_t << ",\n";
        std::cout << "      \"model\": \"" << degr::to_string(p.best_fit_t.model_type_t) << "\",\n";
        std::cout << "      \"formula\": \"" << json_escape(p.best_fit_t.formula()) << "\",\n";
        std::cout << "      \"rmse\": ";
        print_json_number(std::cout, p.best_fit_t.rmse_t);
        std::cout << ",\n";
        std::cout << "      \"a\": ";
        print_json_number(std::cout, p.best_fit_t.a_t);
        std::cout << ",\n";
        std::cout << "      \"b\": ";
        print_json_number(std::cout, p.best_fit_t.b_t);
        std::cout << "\n";
        std::cout << "    }" << (i + 1 == result.periods_t.size() ? "" : ",") << "\n";
    }
    std::cout << "  ]\n";
    std::cout << "}\n";
    return 0;
}
