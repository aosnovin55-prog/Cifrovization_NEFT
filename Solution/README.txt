Каталог поставки (out-of-source): сюда кладите data_*.xlsx, здесь же появятся сборка и артефакты.

Сборка C++ CLI (CMakeLists.txt в корне репозитория):
  cmake -S .. -B build
  cmake --build build --config Release

Пайплайн (из этой папки):
  python ..\Code\scripts\run_pipeline.py --build_dir build

БД по умолчанию: degradation_results.db в этой папке.
Промежуточные CSV: artifacts\

Веб-UI (из корня репозитория):
  pip install -r Code\requirements.txt
  streamlit run Code\ui\app.py

Десктоп .exe: Code\desktop\build_exe.bat — положит WABTViewer.exe сюда.
