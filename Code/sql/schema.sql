-- ============================================================================
-- SQLite: результаты пайплайна деградации WABT (scripts/run_pipeline.py).
-- Имя датасета = имя файла data_*.xlsx. Сводка для Streamlit — v_dataset_summary.
-- ============================================================================

-- Один набор данных (один Excel-файл) и его технологический лимит WABT.
CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Суррогатный ключ
    name TEXT NOT NULL UNIQUE,             -- Имя файла, напр. data_1.xlsx
    wabt_limit REAL NOT NULL,              -- Лимит с листа «Ограничение»
    created_at TEXT DEFAULT CURRENT_TIMESTAMP  -- Время записи (UTC по настройкам SQLite)
);

-- Кусочные периоды, которые нашёл детектор; на каждом — одна подобранная модель.
CREATE TABLE IF NOT EXISTS periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL,           -- Ссылка на datasets.id
    start_index INTEGER NOT NULL,          -- Начальный индекс точки в CSV (включительно)
    end_index INTEGER NOT NULL,            -- Конечный индекс (включительно), ось как у CLI
    model_type TEXT NOT NULL,              -- linear | exponential | logarithmic
    formula TEXT NOT NULL,                 -- Текст формулы для отображения (как в JSON CLI)
    rmse REAL NOT NULL,                    -- RMSE на отрезке; при null в JSON писали -1.0
    FOREIGN KEY(dataset_id) REFERENCES datasets(id)
);

-- Агрегат по датасету: последнее WABT и прогноз шагов до лимита (как в JSON degradation_cli).
CREATE TABLE IF NOT EXISTS forecasts (
    dataset_id INTEGER PRIMARY KEY,        -- Ровно одна строка на datasets.id
    last_value REAL NOT NULL,              -- WABT последней точки ряда
    forecast_steps_to_limit REAL NOT NULL, -- Шаги по оси t; 0 — у/выше лимита; -1 — не вычислено
    FOREIGN KEY(dataset_id) REFERENCES datasets(id)
);

-- Удобная выборка для UI: лимит, прогноз, число периодов и средний RMSE.
CREATE VIEW IF NOT EXISTS v_dataset_summary AS
SELECT
    d.name,
    d.wabt_limit,
    f.last_value,
    f.forecast_steps_to_limit,
    COUNT(p.id) AS period_count,
    AVG(p.rmse) AS avg_rmse
FROM datasets d
LEFT JOIN forecasts f ON f.dataset_id = d.id
LEFT JOIN periods p ON p.dataset_id = d.id
GROUP BY d.id, d.name, d.wabt_limit, f.last_value, f.forecast_steps_to_limit;
