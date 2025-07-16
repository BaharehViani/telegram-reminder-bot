from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from .constants import DAYS_OF_WEEK

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["یادآور جدید"],
            ["نمایش آخرین یادآور"],
            ["نمایش همه یادآورها"],
            ["پشتیبانی", "راهنما"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        [["لغو ایجاد یادآور جدید"]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_edit_choice_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ویرایش پیام", callback_data="edit:message")],
        [InlineKeyboardButton("ویرایش زمان", callback_data="edit:time")],
        [InlineKeyboardButton("ویرایش الگوی تکرار", callback_data="edit:frequency")],
        [InlineKeyboardButton("ویرایش مقصد", callback_data="edit:destination")],
        [InlineKeyboardButton("تایید و ذخیره", callback_data="edit:confirm")]
    ])

def get_destination_keyboard(admin_chats, include_private=True):
    keyboard = []
    if include_private:
        keyboard.append([InlineKeyboardButton("چت خصوصی من", callback_data="dest:private")])
    if admin_chats:
        recent_chats = sorted(admin_chats, key=lambda x: x[2], reverse=True)
        for chat_id, title, _ in recent_chats:
            keyboard.append([InlineKeyboardButton(title, callback_data=f"dest:{chat_id}")])
    keyboard.append([InlineKeyboardButton("به‌روزرسانی لیست", callback_data="dest:reload")])
    return InlineKeyboardMarkup(keyboard)

def build_weekdays_keyboard(selected_days):
    keyboard = []
    for day in DAYS_OF_WEEK:
        label = f"✅ {day}" if day in selected_days else day
        keyboard.append([InlineKeyboardButton(label, callback_data=f"toggle_weekday:{day}")])
    keyboard.append([InlineKeyboardButton("✅ تایید", callback_data="confirm_weekdays")])
    return InlineKeyboardMarkup(keyboard)

def get_try_again_keyboard(chat_id):
    keyboard = [[InlineKeyboardButton("تلاش مجدد", callback_data=f"register_chat:{chat_id}")]]
    return InlineKeyboardMarkup(keyboard)