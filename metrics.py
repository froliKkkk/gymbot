import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
from functools import lru_cache
import logging
from typing import Tuple, Optional, Dict
import gspread
from google.oauth2.service_account import Credentials
from config import get_google_creds

# Настройка визуализации
sns.set_theme()
sns.set_palette("husl")
logger = logging.getLogger(__name__)

# Константы
METRIC_ICONS = {"weight": "🏋️", "reps": "🔄", "sets": "✖️", "progress": "📈"}


def load_sheet(worksheet_name: str) -> pd.DataFrame:
    """Загружает и предобрабатывает данные из Google Sheets"""
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(get_google_creds(), scopes=scope)
        sheet = gspread.authorize(creds).open("training").worksheet(worksheet_name)

        df = pd.DataFrame(sheet.get_all_records())
        numeric_cols = ["№_недели", "вес_кг", "повторения", "№_подхода"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
        return df.dropna()
    except Exception as e:
        logger.error(f"Sheet loading error: {str(e)}")
        return pd.DataFrame()


def calculate_effort(df: pd.DataFrame) -> pd.DataFrame:
    """Вычисляет условные единицы усилий с коэффициентами"""
    conditions = [
        (df["повторения"] == 1),
        (df["повторения"].between(2, 3)),
        (df["повторения"].between(4, 5)),
        (df["повторения"].between(6, 8)),
        (df["повторения"].between(9, 12)),
        (df["повторения"] >= 13),
    ]
    coefficients = np.select(conditions, [1.0, 0.95, 0.90, 0.85, 0.80, 0.75], 1.0)
    df["усл_ед"] = (df["вес_кг"] * 0.8 * df["повторения"] * coefficients).round()
    return df


def get_comparison_data(df: pd.DataFrame, period: str) -> Dict:
    """Подготавливает данные для сравнения по периодам"""
    current_week = df["№_недели"].max()

    if period == "week":
        prev_week = current_week - 1
    elif period == "month":
        prev_week = current_week - 4
    else:  # alltime
        prev_week = df["№_недели"].min()

    return {
        "current": df[df["№_недели"] == current_week],
        "previous": df[df["№_недели"] == prev_week],
    }


def generate_metrics_report(comparison_data: Dict, period_name: str) -> str:
    """Генерирует текстовый отчет с сравнением показателей"""
    report = [f"📊 <b>Аналитика за {period_name}</b>\n"]

    for exercise in comparison_data["current"]["упражнение"].unique():
        current = comparison_data["current"][
            comparison_data["current"]["упражнение"] == exercise
        ]
        previous = comparison_data["previous"][
            comparison_data["previous"]["упражнение"] == exercise
        ]

        if not previous.empty:
            # Расчет изменений
            delta_units = current["усл_ед"].sum() - previous["усл_ед"].sum()
            delta_weight = current["вес_кг"].mean() - previous["вес_кг"].mean()
            delta_reps = current["повторения"].mean() - previous["повторения"].mean()

            # Форматирование отчета
            report.append(
                f"\n{METRIC_ICONS['progress']} <b>{exercise}</b>\n"
                f"  Усл.единицы: {previous['усл_ед'].sum():.0f} → {current['усл_ед'].sum():.0f} "
                f"({delta_units:+.0f})\n"
                f"{METRIC_ICONS['weight']} Средний вес: {previous['вес_кг'].mean():.1f}кг → "
                f"{current['вес_кг'].mean():.1f}кг ({delta_weight:+.1f}кг)\n"
                f"{METRIC_ICONS['reps']} Повторения: {previous['повторения'].mean():.0f} → "
                f"{current['повторения'].mean():.0f} ({delta_reps:+.0f})\n"
                f"{METRIC_ICONS['sets']} Подходов: {len(current)}"
            )

    return "\n".join(report) if len(report) > 1 else "Недостаточно данных для сравнения"


def create_progress_plots(df: pd.DataFrame) -> BytesIO:
    """Создает визуализации прогресса"""
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 18))

    # График 1: Условные единицы по неделям
    units = df.groupby(["№_недели", "упражнение"])["усл_ед"].sum().unstack()
    units.plot(kind="line", marker="o", ax=ax1)
    ax1.set_title("Динамика условных единиц")
    ax1.grid(True)

    # График 2: Средний вес
    weights = df.groupby(["№_недели", "упражнение"])["вес_кг"].mean().unstack()
    weights.plot(kind="line", marker="o", ax=ax2)
    ax2.set_title("Средний рабочий вес (кг)")
    ax2.grid(True)

    # График 3: Средние повторения
    reps = df.groupby(["№_недели", "упражнение"])["повторения"].mean().unstack()
    reps.plot(kind="line", marker="o", ax=ax3)
    ax3.set_title("Среднее количество повторений")
    ax3.grid(True)

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close()
    return buf


def generate_progress_report(
    worksheet_name: str, period: str = "week"
) -> Tuple[str, Optional[BytesIO]]:
    """Основная функция генерации отчета"""
    try:
        period_names = {"week": "неделю", "month": "месяц", "alltime": "всё время"}

        # Загрузка и обработка данных
        df = calculate_effort(load_sheet(worksheet_name))
        if df.empty:
            return "Нет данных для анализа", None

        # Подготовка сравнения
        comparison_data = get_comparison_data(df, period)

        # Генерация отчета
        text_report = generate_metrics_report(comparison_data, period_names[period])
        plot_buffer = create_progress_plots(df)

        return text_report, plot_buffer

    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        return f"Ошибка генерации отчета: {str(e)}", None
