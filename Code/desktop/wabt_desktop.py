"""
Десктоп-приложение (Tkinter + matplotlib): график WABT и вызов ядра деградации.

Поток данных: Excel → сглаженный ряд (rolling) → временный CSV с индексами t=0,1,… →
`degradation_cli` → JSON с периодами и прогнозом → отрисовка (опционально сырой ряд,
сглаженный, лимит, прогноз по последнему периоду).

PyInstaller one-file: CLI вшит в архив (`sys._MEIPASS`); exe и data_*.xlsx лежат в **Solution/**.

В режиме разработки приложение читает xlsx из каталога Solution и ищет CLI в Solution/build/Release.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# Кортеж (аргумент для CLI, текст в комбобоксе).
DEGRADATION_MODES: list[tuple[str, str]] = [
    ("auto", "Авто — на каждом периоде лучшая из трёх (RMSE)"),
    ("linear", "Линейная: WABT = a·t + b"),
    ("exponential", "Экспоненциальная: WABT = a·e^(b·t)"),
    ("logarithmic", "Логарифмическая: WABT = a·ln(t+1) + b"),
]


def code_root() -> Path:
    """Каталог Code/ (на уровень выше `desktop/`)."""
    return Path(__file__).resolve().parent.parent


def solution_dir() -> Path:
    """Каталог Solution: Excel, WABTViewer.exe, out-of-source сборка `build/`."""
    return (code_root().parent / "Solution").resolve()


def app_base_dir() -> Path:
    """Frozen — каталог с exe; разработка — тот же Solution, что у конечной поставки."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return solution_dir()


def find_degradation_cli() -> Path | None:
    """Сначала встроенный CLI, затем Solution/build/Release, затем копия рядом с exe."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "degradation_cli.exe"
        if bundled.is_file():
            return bundled
    sol = solution_dir()
    base = app_base_dir()
    for p in (
        sol / "build" / "Release" / "degradation_cli.exe",
        sol / "build" / "degradation_cli.exe",
        base / "degradation_cli.exe",
        base / "degradation_cli",
        sol / "degradation_cli.exe",
    ):
        if p.is_file():
            return p
    return None


def list_xlsx(base: Path) -> list[Path]:
    """Все `data_*.xlsx` в каталоге, отсортированные по имени."""
    return sorted(base.glob("data_*.xlsx"))


def read_wabt_and_limit(xlsx: Path) -> tuple[pd.DataFrame, float]:
    """Лист WABT (дата + WABT) и числовой лимит с листа «Ограничение» (ячейка B первой строки)."""
    df = pd.read_excel(xlsx, sheet_name="WABT", engine="openpyxl")
    if df.shape[1] < 2:
        raise ValueError("На листе WABT нужны минимум 2 колонки")
    c0, c1 = df.columns[0], df.columns[1]
    df = df.rename(columns={c0: "d", c1: "WABT"})
    df["d"] = pd.to_datetime(df["d"], errors="coerce")
    df = df.dropna(subset=["d", "WABT"]).sort_values("d").reset_index(drop=True)

    lim_df = pd.read_excel(xlsx, sheet_name="Ограничение", header=None, engine="openpyxl")
    raw = str(lim_df.iloc[0, 1]).replace(",", ".")
    limit = float(raw)
    return df, limit


def datetime_at_index(df: pd.DataFrame, t: float) -> pd.Timestamp:
    """Индекс ряда (0 … n-1 и далее для прогноза) в дату по линейной интерполяции/экстраполяции шага."""
    n = len(df)
    if n == 0:
        raise ValueError("пустой ряд")
    d = df["d"]
    if n == 1:
        return pd.Timestamp(d.iloc[0])
    if t <= 0:
        return pd.Timestamp(d.iloc[0])
    imax = n - 1
    if t >= imax:
        delta_s = (pd.Timestamp(d.iloc[-1]) - pd.Timestamp(d.iloc[-2])).total_seconds()
        if delta_s <= 0:
            delta_s = 3600.0
        return pd.Timestamp(d.iloc[-1]) + pd.Timedelta(seconds=delta_s * (t - imax))
    i = int(math.floor(t))
    f = t - i
    t0 = pd.Timestamp(d.iloc[i])
    t1 = pd.Timestamp(d.iloc[i + 1])
    return t0 + (t1 - t0) * f


def hours_per_step(df: pd.DataFrame) -> float:
    """Оценка часов на один шаг оси t по последним точкам времени (fallback: 1.0 ч)."""
    if len(df) < 2:
        return 1.0
    tail = df["d"].iloc[-min(len(df), 24) :]
    diffs_h = tail.diff().dropna().dt.total_seconds() / 3600.0
    positive = diffs_h[diffs_h > 0]
    if positive.empty:
        return 1.0
    return float(positive.median())


def forecast_style_for_model(model: str) -> tuple[str, str, str]:
    """Цвет, стиль линии и подпись легенды для кривой прогноза по типу функции деградации."""
    m = (model or "").lower().strip()
    if m == "linear":
        return "#1565c0", "-.", "Прогноз (линейная)"
    if m == "exponential":
        return "#e65100", "--", "Прогноз (экспонента)"
    if m == "logarithmic":
        return "#6a1b9a", ":", "Прогноз (логарифм)"
    return "#424242", "--", "Прогноз"


def predict_wabt(model: str, a: float | None, b: float | None, t: float) -> float | None:
    """Та же формула, что в C++ ядре, для отрисовки прогноза (linear / exponential / logarithmic)."""
    if a is None or b is None:
        return None
    if not (math.isfinite(a) and math.isfinite(b)):
        return None
    if model == "linear":
        return a * t + b
    if model == "exponential":
        try:
            return a * math.exp(b * t)
        except OverflowError:
            return None
    if model == "logarithmic":
        return a * math.log(t + 1.0) + b
    return None


def write_series_csv(path: Path, wabt_values: list[float]) -> None:
    """CSV для CLI: колонки t (0..n-1) и wabt — обычно сглаженные значения."""
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t", "wabt"])
        for i, val in enumerate(wabt_values):
            w.writerow([i, val])


class WabtViewerApp:
    """Главное окно: выбор файла, параметры сглаживания и режима ядра, график и метрики."""

    def __init__(self) -> None:
        self.base = app_base_dir()
        self.root = tk.Tk()
        self.root.title("Цифровая нефть — WABT и деградация")
        self.root.minsize(960, 640)
        self.root.geometry("1160x780")

        self._rolling = tk.IntVar(value=168)
        self._show_raw = tk.BooleanVar(value=True)
        self._show_smooth = tk.BooleanVar(value=True)
        self._show_forecast = tk.BooleanVar(value=True)
        self._file_var = tk.StringVar()
        self._degradation_label = tk.StringVar(value=DEGRADATION_MODES[0][1])

        self._core_payload: dict | None = None
        self._cli_path = find_degradation_cli()
        self._debounce_id: str | None = None  # id для after() / after_cancel()

        self._label_to_key = {lbl: key for key, lbl in DEGRADATION_MODES}
        self._key_to_label = {key: lbl for key, lbl in DEGRADATION_MODES}

        self._build_ui()
        self._refresh_file_list()
        self._rolling.trace_add("write", lambda *_: self._schedule_pipeline())
        self._schedule_pipeline()

    def _degradation_key(self) -> str:
        """Ключ стратегии для CLI по выбранной подписи комбобокса."""
        lbl = self._degradation_label.get()
        return self._label_to_key.get(lbl, "auto")

    def _build_ui(self) -> None:
        """Собирает панель управления, подписи метрик и область matplotlib."""
        pad = {"padx": 8, "pady": 5}
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, **pad)

        ttk.Label(top, text="Файл:", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.combo = ttk.Combobox(top, textvariable=self._file_var, width=34, state="readonly")
        self.combo.pack(side=tk.LEFT, padx=(6, 10))
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._schedule_pipeline())

        ttk.Button(top, text="Обновить список", command=self._refresh_files_and_recalc).pack(side=tk.LEFT)

        ttk.Label(top, text="Сглаживание (ч):").pack(side=tk.LEFT, padx=(12, 4))
        ttk.Spinbox(top, from_=1, to=720, textvariable=self._rolling, width=5).pack(side=tk.LEFT)

        ttk.Checkbutton(top, text="Показать исходный ряд", variable=self._show_raw, command=self._redraw).pack(
            side=tk.LEFT, padx=(10, 0)
        )
        ttk.Checkbutton(top, text="Сглаженный ряд", variable=self._show_smooth, command=self._redraw).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Checkbutton(top, text="Прогноз", variable=self._show_forecast, command=self._redraw).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        row2 = ttk.Frame(self.root)
        row2.pack(fill=tk.X, **pad)

        ttk.Label(row2, text="Функция деградации (ядро C++):", font=("Segoe UI", 10, "bold")).pack(
            side=tk.LEFT
        )
        strat = ttk.Combobox(
            row2,
            textvariable=self._degradation_label,
            width=52,
            state="readonly",
            values=[lbl for _, lbl in DEGRADATION_MODES],
        )
        strat.pack(side=tk.LEFT, padx=(8, 12))
        strat.bind("<<ComboboxSelected>>", lambda e: self._schedule_pipeline())

        ttk.Button(row2, text="Пересчитать сейчас", command=self._run_pipeline_now).pack(side=tk.LEFT)

        self.lbl_status = ttk.Label(row2, text="", font=("Segoe UI", 9), foreground="#0c6e6e")
        self.lbl_status.pack(side=tk.LEFT, padx=(16, 0))

        if self._cli_path is None:
            ttk.Label(row2, text="Ядро не найдено", foreground="#a00").pack(side=tk.LEFT, padx=(8, 0))

        metrics = ttk.Frame(self.root)
        metrics.pack(fill=tk.X, **pad)
        self.lbl_last = ttk.Label(metrics, text="—", font=("Segoe UI", 10))
        self.lbl_last.pack(side=tk.LEFT, padx=(0, 14))
        self.lbl_limit = ttk.Label(metrics, text="—", font=("Segoe UI", 10))
        self.lbl_limit.pack(side=tk.LEFT, padx=(0, 14))
        self.lbl_margin = ttk.Label(metrics, text="—", font=("Segoe UI", 10))
        self.lbl_margin.pack(side=tk.LEFT, padx=(0, 14))
        self.lbl_forecast = ttk.Label(metrics, text="—", font=("Segoe UI", 10))
        self.lbl_forecast.pack(side=tk.LEFT)

        plot_frame = ttk.Frame(self.root)
        plot_frame.pack(fill=tk.BOTH, expand=True, **pad)

        self.fig = Figure(figsize=(10, 5.2), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()

        bundled = "встроено в .exe" if getattr(sys, "frozen", False) else "рядом / build/Release"
        foot = ttk.Label(
            self.root,
            text=f"Данные: {self.base}  |  Ядро: {bundled}  |  CLI: {self._cli_path or '—'}",
            font=("Segoe UI", 8),
            foreground="#555",
        )
        foot.pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=3)

    def _schedule_pipeline(self) -> None:
        """Откладывает пересчёт ядра (~420 ms), чтобы не дергать CLI на каждый шаг спинбокса."""
        if self._debounce_id is not None:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = self.root.after(420, self._run_pipeline_impl)

    def _run_pipeline_now(self) -> None:
        """Немедленный пересчёт (сброс отложенного вызова)."""
        if self._debounce_id is not None:
            self.root.after_cancel(self._debounce_id)
            self._debounce_id = None
        self._run_pipeline_impl()

    def _refresh_files_and_recalc(self) -> None:
        """Обновить список xlsx на диске и заново запланировать расчёт."""
        self._refresh_file_list()
        self._schedule_pipeline()

    def _refresh_file_list(self) -> None:
        """Заполняет комбобокс именами `data_*.xlsx` из каталога приложения."""
        files = list_xlsx(self.base)
        names = [p.name for p in files]
        self.combo["values"] = names
        if names:
            if self._file_var.get() not in names:
                self._file_var.set(names[0])
        else:
            self._file_var.set("")

    def _run_pipeline_impl(self) -> None:
        """Читает Excel, строит сглаженный ряд, вызывает CLI, сохраняет JSON в `_core_payload`."""
        self._debounce_id = None
        name = self._file_var.get()
        if not name:
            self._core_payload = None
            self.ax.clear()
            self.ax.text(
                0.5,
                0.5,
                "Положите рядом с программой файлы data_*.xlsx",
                ha="center",
                va="center",
                transform=self.ax.transAxes,
            )
            self.canvas.draw()
            self.lbl_status.config(text="")
            self.lbl_last.config(text="Нет файлов")
            self.lbl_limit.config(text="")
            self.lbl_margin.config(text="")
            self.lbl_forecast.config(text="")
            return

        if self._cli_path is None:
            self._core_payload = None
            self.lbl_status.config(text="Нет CLI — только график")
            self._redraw()
            return

        path = self.base / name
        try:
            df, limit = read_wabt_and_limit(path)
        except Exception as e:
            messagebox.showerror("Ошибка чтения", str(e))
            return

        w = int(self._rolling.get())
        smooth = df["WABT"].rolling(window=w, center=True, min_periods=1).mean()
        series = [float(x) for x in smooth.tolist()]
        if any(not math.isfinite(x) for x in series):
            messagebox.showerror("Данные", "В сглаженном ряду есть нечисловые значения.")
            self._core_payload = None
            self._redraw()
            return

        self.lbl_status.config(text="Считаю ядро…")
        self.root.update_idletasks()

        tmp = Path(tempfile.mkstemp(suffix=".csv", prefix="wabt_core_")[1])
        try:
            write_series_csv(tmp, series)
            strat = self._degradation_key()
            proc = subprocess.run(
                [str(self._cli_path), str(tmp), str(limit), strat],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode != 0:
                self._core_payload = None
                messagebox.showerror("Ядро", proc.stderr or f"Код выхода {proc.returncode}")
            else:
                self._core_payload = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            self._core_payload = None
            messagebox.showerror("Ядро", f"Некорректный JSON:\n{e}")
        except Exception as e:
            self._core_payload = None
            messagebox.showerror("Ядро", str(e))
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

        self.lbl_status.config(text="Готово" if self._core_payload else "")
        self._redraw()

    def _plot_forecast(self, df: pd.DataFrame, limit: float):
        """Кривая прогноза: модель последнего периода от end_index на forecast_steps_to_limit шагов по t.

        Возвращает (Line2D, подпись легенды) или (None, None), если прогноза нет или он неположительный.
        """
        if not self._core_payload:
            return None, None
        periods = self._core_payload.get("periods") or []
        if not periods:
            return None, None
        fc_raw = self._core_payload.get("forecast_steps_to_limit")
        if fc_raw is None or not isinstance(fc_raw, (int, float)) or not math.isfinite(fc_raw):
            return None, None
        forecast_steps = float(fc_raw)
        if forecast_steps <= 0:
            return None, None

        last = periods[-1]
        e = int(last["end_index"])
        model = str(last.get("model", ""))
        a, b = last.get("a"), last.get("b")
        if e < 0 or e >= len(df):
            return None, None

        color, linestyle, leg = forecast_style_for_model(model)

        t0 = float(e)
        t1 = t0 + forecast_steps

        n_pts = min(160, max(24, int(abs(t1 - t0)) + 2))
        xs: list[float] = []
        ys: list[float] = []
        for j in range(n_pts):
            u = t0 + (t1 - t0) * (j / max(n_pts - 1, 1))
            y = predict_wabt(model, a, b, u)
            if y is None or not math.isfinite(y):
                break
            if y > limit * 1.02 and u > t0 + 1e-6:
                xs.append(u)
                ys.append(y)
                break
            xs.append(u)
            ys.append(y)

        if len(xs) < 2:
            return None, None
        dates = [datetime_at_index(df, u) for u in xs]
        (ln,) = self.ax.plot(
            dates,
            ys,
            color=color,
            linewidth=2.0,
            linestyle=linestyle,
            alpha=0.95,
        )
        return ln, leg

    def _redraw(self) -> None:
        """Перерисовка графика по текущему файлу и флажкам видимости (без повторного вызова CLI)."""
        name = self._file_var.get()
        if not name:
            return

        path = self.base / name
        try:
            df, limit = read_wabt_and_limit(path)
        except Exception:
            return

        w = int(self._rolling.get())
        smooth = df["WABT"].rolling(window=w, center=True, min_periods=1).mean()

        self.ax.clear()
        line_raw = None
        if self._show_raw.get():
            line_raw = self.ax.plot(df["d"], df["WABT"], color="green", alpha=0.45, linewidth=1)[0]
        line_smooth = None
        if self._show_smooth.get():
            line_smooth = self.ax.plot(df["d"], smooth, color="darkgreen", linewidth=2)[0]

        line_limit = self.ax.axhline(limit, color="#c62828", linestyle="--", linewidth=1.5)

        line_forecast = None
        forecast_legend = None
        if self._show_forecast.get():
            line_forecast, forecast_legend = self._plot_forecast(df, limit)

        last_raw = float(df["WABT"].iloc[-1])
        last_s = float(smooth.iloc[-1])
        lo = min(float(df["WABT"].min()), limit)
        hi = max(float(df["WABT"].max()), limit)
        if self._show_smooth.get():
            lo = min(lo, float(smooth.min()))
            hi = max(hi, float(smooth.max()))
        if line_forecast is not None:
            fy = line_forecast.get_ydata()
            if len(fy) > 0:
                lo = min(lo, float(min(fy)), limit)
                hi = max(hi, float(max(fy)), limit)
        pad_y = max((hi - lo) * 0.06, 1.0)
        self.ax.set_ylim(lo - pad_y, hi + pad_y)

        self.ax.set_xlabel("Дата")
        self.ax.set_ylabel("WABT, °C")
        title = f"{name} — {len(df)} точек"
        if self._core_payload:
            pol = self._core_payload.get("degradation_policy", "?")
            title += f" | режим: {pol}"
        self.ax.set_title(title)
        self.ax.grid(True, alpha=0.3)
        leg_h = [line_limit]
        leg_l = ["Ограничение"]
        if line_raw is not None:
            leg_h.append(line_raw)
            leg_l.append("Исходный WABT")
        if line_smooth is not None:
            leg_h.append(line_smooth)
            leg_l.append("Сглаженный WABT")
        if line_forecast is not None and forecast_legend:
            leg_h.append(line_forecast)
            leg_l.append(forecast_legend)
        self.ax.legend(leg_h, leg_l, loc="upper left", fontsize=8)
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.canvas.draw()

        self.lbl_last.config(text=f"Последний WABT (сырой): {last_raw:.2f} °C  |  сглаж.: {last_s:.2f} °C")
        self.lbl_limit.config(text=f"Ограничение WABT: {limit:g} °C")
        self.lbl_margin.config(text=f"Запас до лимита (сглаж.): {limit - last_s:.2f} °C")

        fc = "—"
        if self._core_payload:
            f = self._core_payload.get("forecast_steps_to_limit")
            if f is not None and isinstance(f, (int, float)) and math.isfinite(f):
                fc_hours = float(f) * hours_per_step(df)
                fc = f"Прогноз до лимита: {fc_hours:.1f} ч ({f:.1f} шагов)"
        self.lbl_forecast.config(text=fc)

    def run(self) -> None:
        """Запуск цикла Tkinter."""
        self.root.mainloop()


def main() -> None:
    """Точка входа при `python wabt_desktop.py`."""
    WabtViewerApp().run()


if __name__ == "__main__":
    main()
