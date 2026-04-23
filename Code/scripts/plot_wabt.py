"""Графики WABT: pandas + сглаживание (rolling 168), лимит из листа «Ограничение»."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from extract_xlsx import parse_limit_sheet  # noqa: E402


def _remove_legacy_plot_pngs(root: Path) -> None:
    """Удаляет старые графики в plots/*.png (не из подпапок)."""
    plots_root = root / "plots"
    if not plots_root.is_dir():
        return
    for png in plots_root.glob("*.png"):
        try:
            png.unlink()
            print(f"Удалён старый график: {png.relative_to(root)}")
        except OSError as e:
            print(f"Не удалось удалить {png}: {e}")


def _normalize_wabt_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Переименовывает первые две колонки в d и WABT (если заголовки другие)."""
    if df.shape[1] < 2:
        raise ValueError("На листе WABT ожидаются минимум 2 колонки")
    out = df.copy()
    cols = list(out.columns)
    out = out.rename(columns={cols[0]: "d", cols[1]: "WABT"})
    return out


def plot_one_xlsx(xlsx: Path, out_dir: Path, rolling_window: int, show: bool) -> None:
    """Строит график сырого и сглаженного WABT + лимит; сохраняет PNG в out_dir."""
    df_wabt = pd.read_excel(xlsx, sheet_name="WABT", engine="openpyxl")
    df_wabt = _normalize_wabt_columns(df_wabt)
    df_wabt["d"] = pd.to_datetime(df_wabt["d"], errors="coerce")
    df_wabt = df_wabt.dropna(subset=["d", "WABT"]).sort_values("d")

    df_wabt["WABT_сглаженный"] = (
        df_wabt["WABT"].rolling(window=rolling_window, center=True, min_periods=1).mean()
    )

    limit = parse_limit_sheet(xlsx)

    fig, ax = plt.subplots(figsize=(14, 6), dpi=120)
    ax.plot(
        df_wabt["d"],
        df_wabt["WABT"],
        color="green",
        alpha=0.5,
        linewidth=1,
    )
    ax.plot(
        df_wabt["d"],
        df_wabt["WABT_сглаженный"],
        color="darkgreen",
        linewidth=2,
    )
    ax.axhline(
        limit,
        color="#d62728",
        linestyle="--",
        linewidth=1.2,
    )

    w_min = float(df_wabt["WABT"].min())
    w_max = float(df_wabt["WABT"].max())
    w_smin = float(df_wabt["WABT_сглаженный"].min())
    w_smax = float(df_wabt["WABT_сглаженный"].max())
    lo = min(w_min, w_smin, limit)
    hi = max(w_max, w_smax, limit)
    pad = max((hi - lo) * 0.06, 1.0)
    ax.set_ylim(lo - pad, hi + pad)

    ax.set_xlabel("Дата")
    ax.set_ylabel("WABT, °C")
    ax.set_title(f"Сглаживание WABT: скользящее среднее ({rolling_window} часов) — {xlsx.name}")
    ax.grid(True, alpha=0.3)
    locator = ax.xaxis.get_major_locator()
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    fig.autofmt_xdate()
    fig.tight_layout()

    png = out_dir / f"{xlsx.stem}_wabt.png"
    fig.savefig(png, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Графики WABT (pandas + сглаживание)")
    parser.add_argument(
        "--rolling",
        type=int,
        default=168,
        help="Окно скользящего среднего (часов), по умолчанию 168",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Показать окно matplotlib после сохранения",
    )
    args = parser.parse_args()

    code_root = Path(__file__).resolve().parent.parent
    solution = code_root.parent / "Solution"
    _remove_legacy_plot_pngs(solution)

    out_dir = solution / "plots" / "wabt_datetime"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(solution.glob("data_*.xlsx"))
    if not files:
        print("Не найдено data_*.xlsx в", solution)
        return

    for xlsx in files:
        try:
            plot_one_xlsx(xlsx, out_dir, args.rolling, args.show)
            print(f"Сохранено: {(out_dir / f'{xlsx.stem}_wabt.png').relative_to(solution)}")
        except Exception as e:
            print(f"Ошибка {xlsx.name}: {e}")

    print(f"Готово, каталог: {out_dir}")


if __name__ == "__main__":
    main()
