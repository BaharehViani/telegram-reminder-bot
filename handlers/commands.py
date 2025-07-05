from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.data import load_user_data, save_user_data
from utils.keyboards import get_main_keyboard, get_cancel_keyboard
from utils.data import load_chat_data
from utils.constants import SUPPORT_USERNAME
import logging
import datetime

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "دوست عزیز"
    context.user_data.update(load_user_data(user_id))
    await update.message.reply_text(
        f"سلام {first_name} 👋\n"
        "من «یادت نره» هستم، یه دستیار یادآور! 🤖\n"
        "میتونم بهت کمک کنم انواع یادآوری‌ها رو تنظیم کنی تا هیچ کاری رو فراموش نکنی.\n\n"
        "برای شروع، فقط کافیه یکی از دکمه‌های زیر رو بزنی 👇",
        reply_markup=get_main_keyboard()
    )
    save_user_data(user_id, context.user_data)
    logger.info(f"User {user_id} started the bot")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    help_text = (
        "🤖 راهنمای استفاده از بات یادآور «یادت نره»\n\n"
        "🟢 برای شروع، از منوی پایین یا دستورات زیر استفاده کنید:\n\n"
        "📌 /newReminder - ایجاد یادآور جدید\n"
        "📋 /showReminder - نمایش آخرین یادآور\n"
        "📋 /listReminders - نمایش همه یادآورها\n"
        "🚀 /start - بازنشانی منو و شروع دوباره\n\n"
        "📝 در لیست یادآورها، می‌توانید با دکمه‌های «ویرایش» و «حذف»، یادآورها را تغییر دهید یا حذف کنید.\n\n"
        "📢 برای افزودن گروه/کانال به لیست مقصدها:\n"
        "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
        "2️⃣ ربات را ادمین کنید.\n"
        "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
        "4️⃣ به چت ربات برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
        "⚠️ نکته: اگر گروه/کانال در لیست ظاهر نشد، مطمئن شوید که هم شما و هم ربات همچنان ادمین هستید."
    )
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard(), parse_mode="HTML")
    save_user_data(user_id, context.user_data)
    logger.info(f"User {user_id} accessed help")

async def new_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    reminders = context.user_data.get("reminders", [])
    new_id = max([r["id"] for r in reminders], default=0) + 1
    new_reminder = {"id": new_id}
    reminders.append(new_reminder)
    context.user_data["reminders"] = reminders
    context.user_data["current_reminder_id"] = new_id
    context.user_data["waiting_for_message"] = True
    await update.message.reply_text(
        f"یادآور جدید با شناسه {new_id} ایجاد شد. لطفاً متن پیام یادآوری را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    save_user_data(user_id, context.user_data)
    logger.info(f"User {user_id} created new reminder with ID {new_id}")

async def show_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    reminders = context.user_data.get("reminders", [])
    if not reminders:
        await update.message.reply_text("شما هنوز یادآوری تنظیم نکرده‌اید.", reply_markup=get_main_keyboard())
        logger.info(f"User {user_id} has no reminders to show")
        return
    reminder = reminders[-1]
    msg = reminder.get("message", "⛔ تنظیم نشده")
    time = reminder.get("time", "⛔ تنظیم نشده")
    freq = reminder.get("frequency", "⛔ تنظیم نشده")
    chat_id = reminder.get("chat_id", user_id)
    chat_data = load_chat_data()
    destination = "چت خصوصی" if chat_id == user_id else chat_data.get(str(chat_id), {}).get("title", "گروه/کانال ناشناس")
    formatted_time = time.strftime("%H:%M") if isinstance(time, datetime.time) else time
    freq_translated = {"everyday": "روزانه", "weekdays": "هفتگی - چند روز", "weekly": "هفتگی - یک روز", "monthly": "ماهانه", "once": "یک تاریخ مشخص", "multi_date": "چند تاریخ مشخص"}.get(freq, "⛔ تنظیم نشده")

    details = ""
    if freq == "weekdays":
        details = f"روزها: {', '.join(reminder.get('weekdays', []))}"
    elif freq == "weekly":
        details = f"روز هفته: {reminder.get('weekly_day', '⛔')}"
    elif freq == "monthly":
        details = f"روز ماه: {reminder.get('monthly_day', '⛔')}"
    elif freq == "once":
        details = f"تاریخ: {reminder.get('once_date', '⛔')}"
    elif freq == "multi_date":
        details = f"تاریخ‌ها: {', '.join(reminder.get('multi_dates', []))}"

    keyboard = [
        [InlineKeyboardButton("حذف", callback_data=f"delete:{reminder['id']}"),
         InlineKeyboardButton("ویرایش", callback_data=f"edit:{reminder['id']}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if freq == "everyday":
        message_text = (
            f"📋 اطلاعات آخرین یادآوری شما (شناسه {reminder['id']}):\n\n"
            f"📝 پیام: {msg}\n"
            f"⏰ زمان: {formatted_time}\n"
            f"🔁 الگوی تکرار: {freq_translated}\n"
            f"📢 مقصد: {destination}"
        )
    else:
        message_text = (
            f"📋 اطلاعات آخرین یادآوری شما (شناسه {reminder['id']}):\n\n"
            f"📝 پیام: {msg}\n"
            f"⏰ زمان: {formatted_time}\n"
            f"🔁 الگوی تکرار: {freq_translated}\n"
            f"📅 {details}\n"
            f"📢 مقصد: {destination}"
        )

    await update.message.reply_text(message_text, reply_markup=reply_markup)
    logger.info(f"User {user_id} showed last reminder {reminder['id']}")

async def list_reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    reminders = context.user_data.get("reminders", [])
    if not reminders:
        await update.message.reply_text("شما هنوز یادآوری تنظیم نکرده‌اید.", reply_markup=get_main_keyboard())
        logger.info(f"User {user_id} has no reminders")
        return
    chat_data = load_chat_data()
    for reminder in reminders:
        msg = reminder.get("message", "⛔ تنظیم نشده")
        time = reminder.get("time", "⛔ تنظیم نشده")
        freq = reminder.get("frequency", "⛔ تنظیم نشده")
        chat_id = reminder.get("chat_id", user_id)
        destination = "چت خصوصی" if chat_id == user_id else chat_data.get(str(chat_id), {}).get("title", "گروه/کانال ناشناس")
        formatted_time = time.strftime("%H:%M") if isinstance(time, datetime.time) else time
        freq_translated = {"everyday": "روزانه", "weekdays": "هفتگی - چند روز", "weekly": "هفتگی - یک روز", "monthly": "ماهانه", "once": "یک تاریخ مشخص", "multi_date": "چند تاریخ مشخص"}.get(freq, "⛔ تنظیم نشده")

        details = ""
        if freq == "weekdays":
            details = f"روزها: {', '.join(reminder.get('weekdays', []))}"
        elif freq == "weekly":
            details = f"روز هفته: {reminder.get('weekly_day', '⛔')}"
        elif freq == "monthly":
            details = f"روز ماه: {reminder.get('monthly_day', '⛔')}"
        elif freq == "once":
            details = f"تاریخ: {reminder.get('once_date', '⛔')}"
        elif freq == "multi_date":
            details = f"تاریخ‌ها: {', '.join(reminder.get('multi_dates', []))}"

        keyboard = [
            [InlineKeyboardButton("حذف", callback_data=f"delete:{reminder['id']}"),
             InlineKeyboardButton("ویرایش", callback_data=f"edit:{reminder['id']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if freq == "everyday":
            message_text = (
                f"📋 یادآوری شماره {reminder['id']}\n\n"
                f"📝 پیام: {msg}\n"
                f"⏰ زمان: {formatted_time}\n"
                f"🔁 الگوی تکرار: {freq_translated}\n"
                f"📢 مقصد: {destination}"
            )
        else:
            message_text = (
                f"📋 یادآوری شماره {reminder['id']}\n\n"
                f"📝 پیام: {msg}\n"
                f"⏰ زمان: {formatted_time}\n"
                f"🔁 الگوی تکرار: {freq_translated}\n"
                f"📅 {details}\n"
                f"📢 مقصد: {destination}"
            )

        await update.message.reply_text(message_text, reply_markup=reply_markup)
    logger.info(f"User {user_id} listed reminders")

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        "برای ارتباط با پشتیبانی ربات به آیدی زیر پیام دهید.\n"
        f"{SUPPORT_USERNAME}",
        reply_markup=get_main_keyboard()
    )
    logger.info(f"User {user_id} accessed support")