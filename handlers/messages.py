from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from utils.data import load_user_data, save_user_data
from utils.keyboards import get_main_keyboard, get_cancel_keyboard, get_destination_keyboard, get_edit_choice_keyboard
from handlers.commands import new_reminder_command, show_reminder_command, list_reminders_command, help_command, support_command
import logging
import datetime

logger = logging.getLogger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    txt = update.message.text.strip() if update.message.text else None

    if txt == "لغو ایجاد یادآور جدید":
        if context.user_data.get("current_reminder_id"):
            current_id = context.user_data["current_reminder_id"]
            reminders = context.user_data.get("reminders", [])
            reminders = [r for r in reminders if r["id"] != current_id]
            context.user_data["reminders"] = reminders
            context.user_data.pop("current_reminder_id", None)
            context.user_data.pop("waiting_for_message", None)
            context.user_data.pop("waiting_for_time", None)
            context.user_data.pop("waiting_for_once_date", None)
            context.user_data.pop("waiting_for_multi_date", None)
            await update.message.reply_text("ایجاد یادآور لغو شد.", reply_markup=get_main_keyboard())
            save_user_data(user_id, context.user_data)
            logger.info(f"User {user_id} cancelled creating reminder {current_id}")
        else:
            await update.message.reply_text("شما در حال ایجاد یادآور نیستید.", reply_markup=get_main_keyboard())
        return

    if txt in LABEL_TO_HANDLER:
        return

    current_id = context.user_data.get("current_reminder_id")
    if not current_id:
        await update.message.reply_text("لطفاً ابتدا یک یادآور جدید ایجاد کنید با /newReminder", reply_markup=get_main_keyboard())
        logger.warning(f"User {user_id} sent message without current reminder")
        return
    reminders = context.user_data.get("reminders", [])
    reminder = next((r for r in reminders if r["id"] == current_id), None)
    if not reminder:
        await update.message.reply_text("یادآور فعلی پیدا نشد.", reply_markup=get_main_keyboard())
        logger.error(f"Reminder {current_id} not found for user {user_id}")
        return

    if context.user_data.get("waiting_for_message"):
        reminder["message"] = txt
        context.user_data["waiting_for_message"] = False
        context.user_data["waiting_for_time"] = True
        await update.message.reply_text("✅ پیام ذخیره شد. حالا زمان را با فرمت 24 ساعته با اعداد انگلیسی وارد کنید (HH:MM):", reply_markup=get_cancel_keyboard())
        save_user_data(user_id, context.user_data)
        logger.info(f"User {user_id} set message for reminder {current_id}")
    elif context.user_data.get("waiting_for_time"):
        try:
            t = datetime.datetime.strptime(txt, "%H:%M").time()
            reminder["time"] = t
            context.user_data["waiting_for_time"] = False
            await update.message.reply_text(f"✅ زمان ذخیره شد: {t.strftime('%H:%M')}.\n"
                                           "الگوی تکرار را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("روزانه", callback_data="freq:everyday")],
                [InlineKeyboardButton("هفتگی - یک روز", callback_data="freq:weekly")],
                [InlineKeyboardButton("هفتگی - چند روز", callback_data="freq:weekdays")],
                [InlineKeyboardButton("ماهانه", callback_data="freq:monthly")],
                [InlineKeyboardButton("یک تاریخ مشخص", callback_data="freq:once")],
                [InlineKeyboardButton("چند تاریخ مشخص", callback_data="freq:multi_date")],
            ]))
            save_user_data(user_id, context.user_data)
            logger.info(f"User {user_id} set time {t.strftime('%H:%M')} for reminder {current_id}")
        except:
            await update.message.reply_text("⛔ فرمت اشتباه است. ساعت رو مثل 14:30 وارد کن.", reply_markup=get_cancel_keyboard())
            logger.warning(f"User {user_id} provided invalid time format for reminder {current_id}")
    elif context.user_data.get("waiting_for_once_date"):
        reminder["once_date"] = txt
        context.user_data["waiting_for_once_date"] = False
        await update.message.reply_text(f"✅ تاریخ ذخیره شد: {txt}")
        save_user_data(user_id, context.user_data)
        if context.user_data.get("waiting_for_edit_frequency"):
            context.user_data["waiting_for_edit_frequency"] = False
            await update.message.reply_text("✅ الگوی تکرار جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
        else:
            from handlers.callbacks import get_admin_chats
            text = (
                "📢 یادآوری کجا ارسال شود؟\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
            )
            await update.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
        logger.info(f"User {user_id} set once date {txt} for reminder {current_id}")
    elif context.user_data.get("waiting_for_multi_date"):
        dates = [d.strip() for d in txt.split(",")]
        reminder["multi_dates"] = dates
        context.user_data["waiting_for_multi_date"] = False
        await update.message.reply_text(f"✅ تاریخ‌ها ذخیره شدند.")
        save_user_data(user_id, context.user_data)
        if context.user_data.get("waiting_for_edit_frequency"):
            context.user_data["waiting_for_edit_frequency"] = False
            await update.message.reply_text("✅ الگوی تکرار جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
        else:
            from handlers.callbacks import get_admin_chats
            text = (
                "📢 یادآوری کجا ارسال شود؟\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
            )
            await update.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
        logger.info(f"User {user_id} set multi dates {dates} for reminder {current_id}")
    elif context.user_data.get("waiting_for_edit_message"):
        reminder["message"] = txt
        context.user_data["waiting_for_edit_message"] = False
        await update.message.reply_text("✅ پیام جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
        save_user_data(user_id, context.user_data)
        logger.info(f"User {user_id} edited message for reminder {current_id}")
    elif context.user_data.get("waiting_for_edit_time"):
        try:
            t = datetime.datetime.strptime(txt, "%H:%M").time()
            reminder["time"] = t
            context.user_data["waiting_for_edit_time"] = False
            await update.message.reply_text(f"✅ زمان جدید ذخیره شد: {t.strftime('%H:%M')}. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
            save_user_data(user_id, context.user_data)
            logger.info(f"User {user_id} edited time to {t.strftime('%H:%M')} for reminder {current_id}")
        except:
            await update.message.reply_text("⛔ فرمت اشتباه. ساعت رو مثل 14:30 وارد کن.", reply_markup=get_cancel_keyboard())
            logger.warning(f"User {user_id} provided invalid time format during edit for reminder {current_id}")
    else:
        await update.message.reply_text("⛔ من متوجه نشدم. لطفاً از دستورات استفاده کن.", reply_markup=get_main_keyboard())
        logger.warning(f"User {user_id} sent unhandled message")

LABEL_TO_HANDLER = {
    "یادآور جدید": new_reminder_command,
    "نمایش آخرین یادآور": show_reminder_command,
    "نمایش همه یادآورها": list_reminders_command,
    "راهنما": help_command,
    "پشتیبانی": support_command,
}

async def label_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text in LABEL_TO_HANDLER:
        handler = LABEL_TO_HANDLER[text]
        if handler:
            await handler(update, context)
        else:
            await update.message.reply_text("این بخش هنوز پیاده‌سازی نشده است.", reply_markup=get_main_keyboard())
            logger.warning(f"User {update.effective_user.id} triggered unimplemented label {text}")
        return