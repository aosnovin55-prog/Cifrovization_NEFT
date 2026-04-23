# -*- mode: python ; coding: utf-8 -*-
# Из папки Code/desktop (сначала out-of-source сборка в Solution/build):
#   cmake -S ../.. -B ../../Solution/build
#   cmake --build ../../Solution/build --config Release
#   pip install pyinstaller
#   pyinstaller wabt_viewer.spec --distpath ../../Solution --workpath ../../Solution/pyi_work
#
# Итог: Solution/WABTViewer.exe + data_*.xlsx в той же папке.

import pathlib

# PyInstaller передаёт SPEC — абсолютный путь к этому файлу
_SPEC = pathlib.Path(SPEC).resolve()
_HERE = _SPEC.parent  # Code/desktop
_CODE = _HERE.parent  # Code/
_REPO = _CODE.parent  # корень репозитория
_SOLUTION = _REPO / "Solution"
_CLI = _SOLUTION / "build" / "Release" / "degradation_cli.exe"
if not _CLI.is_file():
    _CLI = _SOLUTION / "build" / "degradation_cli.exe"
if not _CLI.is_file():
    raise RuntimeError(
        "Не найден degradation_cli.exe. Выполните из корня репозитория:\n"
        "  cmake -S . -B Solution/build\n"
        "  cmake --build Solution/build --config Release"
    )

block_cipher = None

a = Analysis(
    ["wabt_desktop.py"],
    pathex=[str(_CODE)],
    binaries=[(str(_CLI), ".")],
    datas=[],
    hiddenimports=["openpyxl", "openpyxl.cell._writer"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="WABTViewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
