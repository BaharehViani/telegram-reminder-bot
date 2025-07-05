import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BOT_USERNAME = os.getenv("SUPPORT_USERNAME")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME")

DATA_FILE = "reminders.json"
CHAT_DATA_FILE = "chat_data.json"

# State constants
WAITING_FOR_MESSAGE = "waiting_for_message"
WAITING_FOR_TIME = "waiting_for_time"
WAITING_FOR_WEEKDAYS = "waiting_for_weekdays"
WAITING_FOR_WEEKLY_DAY = "waiting_for_weekly_day"
WAITING_FOR_MONTH_DAY = "waiting_for_month_day"
WAITING_FOR_ONCE_DATE = "waiting_for_once_date"
WAITING_FOR_MULTI_DATE = "waiting_for_multi_date"
WAITING_FOR_WEEKLY_DAY_BUTTONS = "waiting_for_weekly_day_buttons"
WAITING_FOR_MONTH_DAY_BUTTONS = "waiting_for_month_day_buttons"
WAITING_FOR_WEEKDAYS_BUTTONS = "waiting_for_weekdays_buttons"
WAITING_FOR_EDIT_CHOICE = "waiting_for_edit_choice"
WAITING_FOR_EDIT_MESSAGE = "waiting_for_edit_message"
WAITING_FOR_EDIT_TIME = "waiting_for_edit_time"
WAITING_FOR_EDIT_FREQUENCY = "waiting_for_edit_frequency"
WAITING_FOR_EDIT_DESTINATION = "waiting_for_edit_destination"

FREQUENCY_TYPES = ["everyday", "weekdays", "weekly", "monthly", "once", "multi_date"]
DAYS_OF_WEEK = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]

FREQUENCY_TRANSLATIONS = {
    "everyday": "روزانه",
    "weekdays": "هفتگی - چند روز",
    "weekly": "هفتگی - یک روز",
    "monthly": "ماهانه",
    "once": "یک تاریخ مشخص",
    "multi_date": "چند تاریخ مشخص"
}