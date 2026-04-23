"""
Полный цикл: CMake-сборка ядра (out-of-source), извлечение xlsx → CSV, сглаживание,
вызов degradation_cli, запись результатов в SQLite.

Рекомендуется запускать из каталога **Solution** (там же кладите data_*.xlsx и появится .exe):

    cd Solution
    cmake -S .. -B build
    cmake --build build --config Release
    python ../Code/scripts/run_pipeline.py --build_dir build

Или одной командой пайплайн сам вызовет CMake, если CLI ещё не собран.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

# Папка Code/ (скрипты, sql); корень репозитория — родитель Code/.
CODE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = CODE_ROOT.parent


def run(cmd, cwd=None):
    """Запуск внешней команды; при ошибке — исключение, иначе stdout."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout


def load_schema(conn: sqlite3.Connection, schema_path: Path):
    """Применяет sql/schema.sql к открытому соединению."""
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def insert_result(conn: sqlite3.Connection, dataset_name: str, limit: float, payload: dict):
    """Сохраняет один JSON-ответ CLI: датасет, периоды, последняя точка и прогноз шагов."""
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO datasets(name, wabt_limit) VALUES (?, ?)",
        (dataset_name, limit),
    )
    dataset_id = cur.execute("SELECT id FROM datasets WHERE name = ?", (dataset_name,)).fetchone()[0]
    cur.execute("DELETE FROM periods WHERE dataset_id = ?", (dataset_id,))
    cur.execute("DELETE FROM forecasts WHERE dataset_id = ?", (dataset_id,))

    for period in payload.get("periods", []):
        rmse = period.get("rmse")
        if rmse is None:
            rmse = -1.0
        cur.execute(
            """
            INSERT INTO periods(dataset_id, start_index, end_index, model_type, formula, rmse)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                period["start_index"],
                period["end_index"],
                period["model"],
                period["formula"],
                rmse,
            ),
        )

    cur.execute(
        """
        INSERT INTO forecasts(dataset_id, last_value, forecast_steps_to_limit)
        VALUES (?, ?, ?)
        """,
        (dataset_id, payload["last_value"], payload["forecast_steps_to_limit"]),
    )
    conn.commit()


def main():
    """Обходит все xlsx в data_dir, наполняет БД."""
    parser = argparse.ArgumentParser(description="Run C++ degradation core on xlsx datasets")
    parser.add_argument(
        "--build_dir",
        type=Path,
        default=Path("build"),
        help="Каталог сборки CMake (относительно текущего cwd), напр. build внутри Solution",
    )
    parser.add_argument(
        "--data_dir",
        type=Path,
        default=Path("."),
        help="Каталог с data_*.xlsx (обычно Solution)",
    )
    parser.add_argument("--db", type=Path, default=Path("degradation_results.db"))
    parser.add_argument(
        "--schema",
        type=Path,
        default=CODE_ROOT / "sql" / "schema.sql",
    )
    parser.add_argument("--data_glob", default="data_*.xlsx")
    parser.add_argument(
        "--strategy",
        default="auto",
        choices=["auto", "linear", "exponential", "logarithmic"],
        help="Функция деградации: auto — лучшая по RMSE; иначе только выбранная модель на всех периодах",
    )
    parser.add_argument(
        "--rolling",
        type=int,
        default=168,
        help="Скользящее среднее по индексу ряда перед ядром; 1 — без сглаживания",
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    build_dir = args.build_dir if args.build_dir.is_absolute() else (cwd / args.build_dir).resolve()
    data_dir = args.data_dir if args.data_dir.is_absolute() else (cwd / args.data_dir).resolve()
    db_path = args.db if args.db.is_absolute() else (cwd / args.db).resolve()
    schema_path = args.schema if args.schema.is_absolute() else (cwd / args.schema).resolve()

    build_dir.mkdir(parents=True, exist_ok=True)
    run(["cmake", "-S", str(REPO_ROOT), "-B", str(build_dir)])
    run(["cmake", "--build", str(build_dir), "--config", "Release"])

    candidates = [
        build_dir / "degradation_cli.exe",
        build_dir / "Release" / "degradation_cli.exe",
        build_dir / "degradation_cli",
    ]
    cli = next((p for p in candidates if p.exists()), None)
    if cli is None:
        raise FileNotFoundError("Cannot find built degradation_cli executable")

    work = data_dir / "artifacts"
    work.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    load_schema(conn, schema_path)

    extract_script = CODE_ROOT / "scripts" / "extract_xlsx.py"
    for xlsx in sorted(data_dir.glob(args.data_glob)):
        csv_path = work / f"{xlsx.stem}_wabt.csv"
        limit_path = work / f"{xlsx.stem}_limit.txt"
        run(
            [
                sys.executable,
                str(extract_script),
                str(xlsx),
                str(csv_path),
                "--limit_out",
                str(limit_path),
            ]
        )
        limit = float(limit_path.read_text(encoding="utf-8").strip())
        if args.rolling > 1:
            df = pd.read_csv(csv_path)
            df["wabt"] = df["wabt"].rolling(window=args.rolling, center=True, min_periods=1).mean()
            df.to_csv(csv_path, index=False)
        output = run([str(cli), str(csv_path), str(limit), args.strategy])
        payload = json.loads(output)
        insert_result(conn, xlsx.name, limit, payload)
        print(f"[OK] {xlsx.name}: periods={len(payload.get('periods', []))}")

    conn.close()
    print(f"Results saved to {db_path}")


if __name__ == "__main__":
    main()
