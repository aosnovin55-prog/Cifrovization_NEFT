"""
Веб-интерфейс (Streamlit): выбор data_*.xlsx, график WABT и лимита (Plotly),
метрики, сводка из degradation_results.db после run_pipeline.

Запуск из корня репозитория: streamlit run Code/ui/app.py

Данные и БД по умолчанию — каталог **Solution/** (data_*.xlsx, degradation_results.db).
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

CODE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = CODE_ROOT.parent
SOLUTION = REPO_ROOT / "Solution"
SCRIPTS = CODE_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from extract_xlsx import parse_limit_sheet  # noqa: E402

DB_PATH = SOLUTION / "degradation_results.db"
BUILD_CLI_CANDIDATES = [
    SOLUTION / "build" / "Release" / "degradation_cli.exe",
    SOLUTION / "build" / "degradation_cli.exe",
    SOLUTION / "build" / "degradation_cli",
]


def _find_cli() -> Path | None:
    """Первый существующий путь к degradation_cli (Windows/Linux)."""
    for p in BUILD_CLI_CANDIDATES:
        if p.is_file():
            return p
    return None


def _normalize_wabt_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Первые две колонки листа WABT → имена `d` и `WABT` для единообразия."""
    if df.shape[1] < 2:
        raise ValueError("На листе WABT нужны минимум 2 колонки")
    out = df.copy()
    c0, c1 = out.columns[0], out.columns[1]
    return out.rename(columns={c0: "d", c1: "WABT"})


def _load_wabt_frame(xlsx: Path) -> tuple[pd.DataFrame, float]:
    """Датафрейм WABT (отсортированный по дате) и лимит из того же xlsx."""
    df = pd.read_excel(xlsx, sheet_name="WABT", engine="openpyxl")
    df = _normalize_wabt_columns(df)
    df["d"] = pd.to_datetime(df["d"], errors="coerce")
    df = df.dropna(subset=["d", "WABT"]).sort_values("d")
    limit = parse_limit_sheet(xlsx)
    return df, limit


def _hours_per_step(df: pd.DataFrame) -> float:
    """Оценка часов на один индексный шаг по датам ряда (fallback: 1.0 ч)."""
    if len(df) < 2:
        return 1.0
    tail = df["d"].iloc[-min(len(df), 24) :]
    diffs_h = tail.diff().dropna().dt.total_seconds() / 3600.0
    positive = diffs_h[diffs_h > 0]
    if positive.empty:
        return 1.0
    return float(positive.median())


def _inject_styles() -> None:
    """Лёгкое оформление метрик и отступов через кастомный CSS."""
    st.markdown(
        """
        <style>
            /* Карточки и отступы */
            div[data-testid="stMetric"] {
                background: #ffffff;
                border: 1px solid #dce4ee;
                border-radius: 12px;
                padding: 12px 16px;
                box-shadow: 0 1px 2px rgba(21, 34, 56, 0.06);
            }
            div[data-testid="stMetric"] label {
                color: #5c6f82 !important;
            }
            .block-container {
                padding-top: 2rem;
                padding-bottom: 3rem;
            }
            h1 { letter-spacing: -0.02em; }
            .hero-sub {
                color: #5c6f82;
                font-size: 1.05rem;
                margin-top: -0.5rem;
                margin-bottom: 1.5rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _build_figure(df: pd.DataFrame, rolling: int, limit: float, show_raw: bool) -> go.Figure:
    """Линия лимита (две точки по краям), опционально сырой ряд, сглаженный ряд; легенда сверху."""
    smooth = df["WABT"].rolling(window=rolling, center=True, min_periods=1).mean()
    fig = go.Figure()
    d0, d1 = df["d"].iloc[0], df["d"].iloc[-1]
    fig.add_trace(
        go.Scatter(
            x=[d0, d1],
            y=[limit, limit],
            mode="lines",
            name="Ограничение",
            line=dict(color="#b71c1c", dash="dash", width=2),
            hovertemplate=f"Ограничение: {limit:g}<extra></extra>",
        )
    )
    if show_raw:
        fig.add_trace(
            go.Scatter(
                x=df["d"],
                y=df["WABT"],
                mode="lines",
                name="Исходный WABT",
                line=dict(color="rgba(46, 125, 50, 0.45)", width=1),
                hovertemplate="%{x|%Y-%m-%d %H:%M}<br>WABT: %{y:.3f}<extra></extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=df["d"],
            y=smooth,
            mode="lines",
            name="Сглаженный WABT",
            line=dict(color="#1b5e20", width=2.5),
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Сглаженный: %{y:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_white",
        height=520,
        margin=dict(l=48, r=32, t=48, b=48),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
        xaxis_title="Дата",
        yaxis_title="WABT, °C",
        title=dict(text="Динамика WABT и технологическое ограничение", font=dict(size=18)),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e8eef4")
    fig.update_yaxes(showgrid=True, gridcolor="#e8eef4")
    return fig


def _load_summary() -> pd.DataFrame | None:
    """Строки из представления v_dataset_summary или None, если БД нет/ошибка чтения."""
    if not DB_PATH.is_file():
        return None
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(DB_PATH)
        return pd.read_sql_query("SELECT * FROM v_dataset_summary", conn)
    except Exception:
        return None
    finally:
        if conn is not None:
            conn.close()


def _prepare_summary_with_units(summary: pd.DataFrame, step_hours: float) -> pd.DataFrame:
    """Готовит таблицу сводки: человекочитаемые названия и единицы измерения."""
    out = summary.copy()
    if "forecast_steps_to_limit" in out.columns:
        out["forecast_to_limit_h"] = out["forecast_steps_to_limit"] * step_hours
    rename_map = {
        "name": "Датасет",
        "wabt_limit": "Лимит WABT, °C",
        "last_value": "Последний WABT, °C",
        "forecast_steps_to_limit": "Прогноз до лимита, шаги",
        "forecast_to_limit_h": "Прогноз до лимита, ч",
        "period_count": "Периодов, шт",
        "avg_rmse": "Средний RMSE, °C",
    }
    return out.rename(columns=rename_map)


def main() -> None:
    """Собирает страницу Streamlit: сайдбар, график, вкладки сводки и описания."""
    st.set_page_config(
        page_title="Цифровая нефть — WABT",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()

    st.title("Мониторинг деградации по WABT")
    st.markdown(
        '<p class="hero-sub">Просмотр рядов из Excel, сглаживание скользящим средним, '
        "лимит из листа «Ограничение» и сводка по расчёту ядра (при наличии БД).</p>",
        unsafe_allow_html=True,
    )

    xlsx_files = sorted(SOLUTION.glob("data_*.xlsx"))
    if not xlsx_files:
        st.error(f"В каталоге Solution не найдены файлы data_*.xlsx: `{SOLUTION}`")
        st.stop()

    with st.sidebar:
        st.header("Параметры")
        choice = st.selectbox(
            "Датасет",
            options=xlsx_files,
            format_func=lambda p: p.name,
            index=min(5, len(xlsx_files) - 1),
        )
        rolling = st.slider(
            "Окно сглаживания (часов)",
            min_value=1,
            max_value=720,
            value=168,
            step=1,
            help="Скользящее среднее по времени; 168 ч ≈ одна неделя при почасовых данных.",
        )
        show_raw = st.toggle("Показывать исходный ряд", value=True)
        st.divider()
        st.subheader("Расчёт ядра")
        cli = _find_cli()
        if cli is not None:
            st.caption(f"Собранный CLI: `{cli.relative_to(REPO_ROOT)}`")
        else:
            st.caption("Пайплайн сам вызовет CMake и соберёт `degradation_cli` при первом запуске.")
        if st.button("Запустить полный пайплайн", type="primary"):
            with st.spinner("Сборка и расчёт…"):
                try:
                    subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPTS / "run_pipeline.py"),
                            "--build_dir",
                            str(SOLUTION / "build"),
                            "--data_dir",
                            str(SOLUTION),
                            "--db",
                            str(DB_PATH),
                        ],
                        cwd=str(SOLUTION),
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    st.success("Пайплайн завершён. Обновите вкладку «Сводка».")
                except subprocess.CalledProcessError as e:
                    st.error(e.stderr or str(e))

    try:
        df, limit = _load_wabt_frame(choice)
    except Exception as e:
        st.error(f"Не удалось прочитать файл: {e}")
        st.stop()

    last_w = float(df["WABT"].iloc[-1])
    step_hours = _hours_per_step(df)
    smooth_last = float(df["WABT"].rolling(window=rolling, center=True, min_periods=1).mean().iloc[-1])
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Последний WABT, °C", f"{last_w:.2f}", delta=None)
    col2.metric("Ограничение WABT, °C", f"{limit:g}")
    col3.metric("Запас до лимита, °C", f"{limit - last_w:.2f}")
    col4.metric("Точек в ряду, шт", f"{len(df):,}".replace(",", " "))

    fig = _build_figure(df, rolling, limit, show_raw)
    st.plotly_chart(fig, use_container_width=True)

    tab1, tab2 = st.tabs(["Сводка по модели", "О проекте"])
    with tab1:
        summary = _load_summary()
        if summary is None or summary.empty:
            st.info(
                "База `degradation_results.db` не найдена или пуста. "
                "Запустите `python scripts/run_pipeline.py` или кнопку «Запустить полный пайплайн» в боковой панели."
            )
        else:
            st.caption(f"Прогноз в часах: 1 шаг ≈ {step_hours:.2f} ч (оценка по последним датам ряда).")
            st.dataframe(_prepare_summary_with_units(summary, step_hours), use_container_width=True, hide_index=True)
    with tab2:
        st.markdown(
            """
            **Состав решения**
            - Ядро на C++: периоды деградации, подбор функции (линейная / экспонента / логарифм), прогноз до лимита.
            - Python: извлечение из `.xlsx`, пайплайн, SQLite.
            - Тесты: GoogleTest (`degradation_tests`).
            """
        )


if __name__ == "__main__":
    main()
