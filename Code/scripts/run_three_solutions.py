"""
Три прогона пайплайна с разными стратегиями и отдельными SQLite в каталоге Solution.
Запуск из Solution: python ../Code/scripts/run_three_solutions.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = CODE_ROOT.parent
SOLUTION = REPO_ROOT / "Solution"

SOLUTIONS: list[tuple[str, str]] = [
    ("degradation_solution_linear.db", "linear"),
    ("degradation_solution_exponential.db", "exponential"),
    ("degradation_solution_logarithmic.db", "logarithmic"),
]


def main() -> None:
    """Три вызова run_pipeline с --db в Solution и сборкой Solution/build."""
    if not SOLUTION.is_dir():
        raise SystemExit(f"Нет каталога Solution: {SOLUTION}")
    for db_name, strategy in SOLUTIONS:
        db_path = SOLUTION / db_name
        print(f"\n=== Strategy: {strategy} -> {db_name} ===")
        subprocess.run(
            [
                sys.executable,
                str(CODE_ROOT / "scripts" / "run_pipeline.py"),
                "--db",
                str(db_path),
                "--build_dir",
                str(SOLUTION / "build"),
                "--data_dir",
                str(SOLUTION),
                "--strategy",
                strategy,
            ],
            cwd=str(SOLUTION),
            check=True,
        )
    print("\nDone. SQLite DB files:", [s[0] for s in SOLUTIONS])


if __name__ == "__main__":
    main()
