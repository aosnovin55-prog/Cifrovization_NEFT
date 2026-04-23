# Degradation Forecast Core

Хакатон-проект по прогнозу деградации WABT для наборов `data_*.xlsx`.

## Структура репозитория

- `CMakeLists.txt` — корневая CMake-конфигурация.
- `Code/` — весь рабочий код без тестов (`src`, `include`, `scripts`, `ui`, `desktop`, `sql`).
- `tests/` — C++ тесты (GoogleTest).
- `Solution/` — папка поставки/запуска: `data_*.xlsx`, `WABTViewer.exe`, `build/`, БД, артефакты.

## Сборка C++ (out-of-source)

```bash
cd Solution
cmake -S .. -B build
cmake --build build --config Release
ctest --test-dir build --output-on-failure -C Release
```

## Пайплайн

```bash
cd Solution
python ../Code/scripts/run_pipeline.py --build_dir build
```

## GUI (WABTViewer.exe)

```bash
cd Code/desktop
pyinstaller wabt_viewer.spec --distpath ../../Solution --workpath ../../Solution/pyi_work
```

## Веб-интерфейс

```bash
pip install -r Code/requirements.txt
streamlit run Code/ui/app.py
```
