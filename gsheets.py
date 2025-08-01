import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from config import get_google_creds


scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

credentials = Credentials.from_service_account_info(get_google_creds(), scopes=scope)
client = gspread.authorize(credentials)


def get_table() -> gspread.Spreadsheet:
    """Возвращает таблицу 'training' (уже созданную)"""
    try:
        return client.open("training")
    except Exception as e:
        print(f"❌ Ошибка при загрузке таблицы: {e}")
        raise


def add_workout(
    day_split: str,
    week_num: int,
    exercise: str,
    set_num: int,
    weight: float,
    reps: int,
    deload: bool,
) -> bool:
    """Добавляет запись о тренировке в указанный лист"""
    try:
        table = get_table()
        worksheet = table.worksheet(day_split)
        worksheet.append_row(
            [
                week_num,
                exercise,
                set_num,
                weight,
                reps,
                datetime.now().strftime("%Y-%m-%d"),
                "да" if deload else "нет",
            ]
        )
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
