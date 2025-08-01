from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from gsheets import add_workout
from metrics import (
    load_sheet,
    generate_progress_report,
    calculate_effort,
    get_comparison_data,
    generate_metrics_report,
    create_progress_plots,
)

from config import TOKEN, ALLOWED_USER_IDS


# Состояния меню
MAIN_MENU, WORKOUT_DAY, ANALYTICS_DAY, ANALYTICS_TYPE = range(4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Добавить тренировку", callback_data="add_workout")],
        [InlineKeyboardButton("Аналитика", callback_data="show_analysis")],
    ]
    await update.message.reply_text(
        "🏋️‍♂️ Ваш персональный GymBot!", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data["menu_state"] = MAIN_MENU


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_menu":
        await show_main_menu(query)
        context.user_data["menu_state"] = MAIN_MENU
        return

    if query.data == "back":
        current_state = context.user_data.get("menu_state", MAIN_MENU)
        if current_state in [WORKOUT_DAY, ANALYTICS_DAY]:
            await show_main_menu(query)
            context.user_data["menu_state"] = MAIN_MENU
        elif current_state == ANALYTICS_TYPE:
            await show_analytics_days(query)
            context.user_data["menu_state"] = ANALYTICS_DAY
        return

    if query.data == "add_workout":
        await show_workout_days(query)
        context.user_data["menu_state"] = WORKOUT_DAY

    elif query.data == "show_analysis":
        await show_analytics_days(query)
        context.user_data["menu_state"] = ANALYTICS_DAY

    elif query.data in ["upper1", "lower1", "upper2", "lower2"]:
        context.user_data["current_day"] = query.data
        await handle_workout_day(query, context)

    elif query.data.startswith("analytics_"):
        context.user_data["analytics_day"] = query.data.replace("analytics_", "")
        await show_analytics_types(query)
        context.user_data["menu_state"] = ANALYTICS_TYPE

    elif query.data in ["week_analysis", "month_analysis", "alltime_analysis"]:
        await generate_analytics(query, context)


async def show_main_menu(query):
    keyboard = [
        [InlineKeyboardButton("Добавить тренировку", callback_data="add_workout")],
        [InlineKeyboardButton("Аналитика", callback_data="show_analysis")],
    ]
    await query.edit_message_text(
        "🏋️‍♂️ Главное меню:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_workout_days(query):
    keyboard = [
        [InlineKeyboardButton("Верх тела 1", callback_data="upper1")],
        [InlineKeyboardButton("Низ тела 1", callback_data="lower1")],
        [InlineKeyboardButton("Верх тела 2", callback_data="upper2")],
        [InlineKeyboardButton("Низ тела 2", callback_data="lower2")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")],
    ]
    await query.edit_message_text(
        "📝 Выберите день:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_analytics_days(query):
    keyboard = [
        [InlineKeyboardButton("Верх тела 1", callback_data="analytics_upper1")],
        [InlineKeyboardButton("Низ тела 1", callback_data="analytics_lower1")],
        [InlineKeyboardButton("Верх тела 2", callback_data="analytics_upper2")],
        [InlineKeyboardButton("Низ тела 2", callback_data="analytics_lower2")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")],
    ]
    await query.edit_message_text(
        "📊 Выберите день для анализа:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_analytics_types(query):
    keyboard = [
        [InlineKeyboardButton("За неделю", callback_data="week_analysis")],
        [InlineKeyboardButton("За месяц", callback_data="month_analysis")],
        [InlineKeyboardButton("За всё время", callback_data="alltime_analysis")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")],
    ]
    await query.edit_message_text(
        "📈 Выберите период:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_workout_day(query, context):
    await query.edit_message_text(
        f"Введите данные для {context.user_data['current_day']} в формате:\n"
        "№ недели, упражнение, № подхода, вес, повторения, разгрузка (да/нет)\n\n"
        "Пример: 5, Жим штанги, 1, 60, 8, нет"
    )


async def handle_workout_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "current_day" not in context.user_data:
        return

    try:
        data = update.message.text.split(",")
        if len(data) != 6:
            raise ValueError("Нужно 6 значений через запятую!")

        week_num = int(data[0].strip())
        exercise = data[1].strip()
        set_num = int(data[2].strip())
        weight = float(data[3].strip())
        reps = int(data[4].strip())
        deload = data[5].strip().lower() == "да"

        success = add_workout(
            context.user_data["current_day"],
            week_num,
            exercise,
            set_num,
            weight,
            reps,
            deload,
        )

        await update.message.reply_text(
            "✅ Данные сохранены!" if success else "❌ Ошибка!"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def generate_analytics(query, context):
    day = context.user_data["analytics_day"]
    period_map = {
        "week_analysis": "week",
        "month_analysis": "month",
        "alltime_analysis": "alltime",
    }
    period_type = period_map.get(query.data, "week")
    period_names = {"week": "неделю", "month": "месяц", "alltime": "всё время"}

    try:
        # Загружаем и обрабатываем данные
        df = calculate_effort(load_sheet(day))
        if df.empty:
            await query.edit_message_text("❌ Нет данных для анализа.")
            return

        # Получаем данные для сравнения
        comparison_data = get_comparison_data(df, period_type)

        # Генерируем текстовый отчет
        text_report = generate_metrics_report(
            comparison_data, period_names[period_type]
        )

        # Создаем графики
        plot_buffer = create_progress_plots(df)

        # Клавиатура с кнопками навигации
        keyboard = [
            [InlineKeyboardButton("🔙 Назад к периодам", callback_data="back")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем графики с текстовым отчетом и кнопками
        if plot_buffer:
            await query.message.reply_photo(
                photo=plot_buffer,
                caption=text_report,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        else:
            await query.message.reply_text(
                text_report, reply_markup=reply_markup, parse_mode="HTML"
            )

    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_workout_data)
    )
    app.run_polling()


if __name__ == "__main__":
    main()
