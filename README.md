# Degradation Forecast Core

Прогноз деградации для данных `data_*.xlsx`:

- ядро на C++ (детектор периодов, регрессии, движок);
- Python-скрипты извлечения и пайплайна;
- SQLite-схема в `Code/sql/schema.sql`;
- **`CMakeLists.txt`** в корне репозитория, C++ тесты в `tests/`.

## Структура репозитория

- **`CMakeLists.txt`** — сборка ядра и CLI (исходники в `Code/`).
- **`Code/`** — весь код без тестов: `include/`, `src/`, `scripts/`, `ui/`, `desktop/`, `sql/`, `requirements.txt`, `.streamlit/`.
- **`tests/`** — только GTest-исходники.
- **`Solution/`** — каталог поставки: положите сюда `data_*.xlsx`, здесь же out-of-source сборка `build/`, БД, `artifacts/`, при необходимости `WABTViewer.exe` (см. `Solution/README.txt`).

## Сборка C++ (из `Solution/`)

```bash
cd Solution
cmake -S .. -B build
cmake --build build --config Release
ctest --test-dir build --output-on-failure -C Release
```

## Пайплайн

Из каталога **`Solution`** (Excel-файлы должны лежать здесь):

```bash
cd Solution
python ../Code/scripts/run_pipeline.py --build_dir build
```

Опция **`--strategy`**: `auto` (по умолчанию), `linear`, `exponential`, `logarithmic`.

Три отдельные БД:

```bash
cd Solution
python ../Code/scripts/run_three_solutions.py
```

Результаты: `Solution/artifacts/*`, `Solution/degradation_results.db` (и доп. `.db` для трёх стратегий).

## Веб-интерфейс (Streamlit)

```bash
pip install -r Code/requirements.txt
streamlit run Code/ui/app.py
```

По умолчанию UI читает `data_*.xlsx` и `degradation_results.db` из **`Solution/`**.

## Окно Windows (Tkinter)

Исходник: `Code/desktop/wabt_desktop.py`. В режиме разработки данные и `Solution/build/.../degradation_cli.exe` берутся из **`Solution/`**.

**Сборка одного exe** (сначала CLI в `Solution/build`):

```bash
cd Solution
cmake -S .. -B build
cmake --build build --config Release
cd ../Code/desktop
pip install pyinstaller pandas openpyxl matplotlib
pyinstaller wabt_viewer.spec --distpath ../../Solution --workpath ../../Solution/pyi_work
```

На Windows: **`Code/desktop/build_exe.bat`** — кладёт **`Solution/WABTViewer.exe`**; рядом нужны только **`data_*.xlsx`**.

## Графики WABT

```bash
python Code/scripts/plot_wabt.py
```

Читает `Solution/data_*.xlsx`, пишет PNG в `Solution/plots/wabt_datetime/`.
