@echo off
set "DESKTOP=%~dp0"
set "REPO=%DESKTOP%..\.."
set "SOLUTION=%REPO%\Solution"
cd /d "%DESKTOP%"
if not exist "%SOLUTION%\build\Release\degradation_cli.exe" (
  echo ERROR: %SOLUTION%\build\Release\degradation_cli.exe not found.
  echo From repo root run:
  echo   cmake -S . -B Solution\build
  echo   cmake --build Solution\build --config Release
  pause
  exit /b 1
)
echo Installing PyInstaller if needed...
python -m pip install -q pyinstaller pandas openpyxl matplotlib
echo Building WABTViewer.exe into Solution\ ...
python -m PyInstaller wabt_viewer.spec --distpath "%SOLUTION%" --workpath "%SOLUTION%\pyi_work" --noconfirm
if %ERRORLEVEL% neq 0 exit /b 1
echo.
echo Done: %SOLUTION%\WABTViewer.exe
echo Place data_*.xlsx in Solution\ next to the exe.
pause
