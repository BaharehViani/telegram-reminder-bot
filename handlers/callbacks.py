from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.data import load_user_data, save_user_data, load_chat_data, save_chat_data
from utils.keyboards import get_destination_keyboard, get_edit_choice_keyboard, build_weekdays_keyboard, get_main_keyboard, get_cancel_keyboard
from utils.constants import DAYS_OF_WEEK, WAITING_FOR_EDIT_FREQUENCY, BOT_USERNAME
import logging
import datetime

logger = logging.getLogger(__name__)

async def get_admin_chats(context, user_id):
    chat_data = load_chat_data()
    admin_chats = []
    updated_chat_data = {}
    for chat_id, chat_info in chat_data.items():
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            admin_ids = [admin.user.id for admin in admins]
            if user_id in admin_ids and context.bot.id in admin_ids:
                chat = await context.bot.get_chat(chat_id)
                title = chat.title if chat.title else "بدون نام"
                last_used = chat_info.get("last_used", datetime.datetime.now().isoformat())
                admin_chats.append((chat_id, title, last_used))
                updated_chat_data[chat_id] = {"title": title, "last_used": last_used}
        except Exception as e:
            logger.error(f"Error checking admins for chat {chat_id}: {e}")
    save_chat_data(updated_chat_data)
    return admin_chats

async def frequency_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    freq = query.data.split(":")[1]
    user_id = query.from_user.id
    context.user_data.update(load_user_data(user_id))
    current_id = context.user_data.get("current_reminder_id")
    reminders = context.user_data.get("reminders", [])
    reminder = next((r for r in reminders if r["id"] == current_id), None)

    if not reminder:
        await query.edit_message_text("یادآور فعلی پیدا نشد.")
        logger.error(f"Reminder {current_id} not found for user {user_id}")
        return

    if context.user_data.get(WAITING_FOR_EDIT_FREQUENCY):
        for key in ["weekly_day", "monthly_day", "once_date", "multi_dates", "weekdays"]:
            reminder.pop(key, None)
        logger.info(f"User {user_id} cleared previous frequency keys for reminder {current_id}")

    reminder["frequency"] = freq
    save_user_data(user_id, context.user_data)

    if freq == "everyday":
        await query.edit_message_text("✅ تنظیم شد: هر روز")
        if context.user_data.get(WAITING_FOR_EDIT_FREQUENCY):
            context.user_data[WAITING_FOR_EDIT_FREQUENCY] = False
            await query.message.reply_text("✅ الگوی تکرار جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
        else:
            text = (
                "📢 یادآوری کجا ارسال شود؟\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
            )
            await query.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
        logger.info(f"User {user_id} set frequency to everyday for reminder {current_id}")
    elif freq == "weekdays":
        await send_weekdays_buttons(update, context)
        logger.info(f"User {user_id} selected weekdays frequency for reminder {current_id}")
    elif freq == "weekly":
        await send_weekly_day_buttons(update, context)
        logger.info(f"User {user_id} selected weekly frequency for reminder {current_id}")
    elif freq == "monthly":
        await send_month_day_buttons(update, context)
        logger.info(f"User {user_id} selected monthly frequency for reminder {current_id}")
    elif freq == "once":
        context.user_data["waiting_for_once_date"] = True
        await query.message.reply_text("📌 تاریخ مشخص رو وارد کن (مثلاً 1404/04/10):", reply_markup=get_cancel_keyboard())
        await query.edit_message_text("✅ الگوی تکرار: یک تاریخ مشخص")
        logger.info(f"User {user_id} selected once frequency for reminder {current_id}")
    elif freq == "multi_date":
        context.user_data["waiting_for_multi_date"] = True
        await query.message.reply_text("📌 تاریخ‌ها رو با کاما جدا کن (مثلاً 1404/04/10, 1404/05/01):", reply_markup=get_cancel_keyboard())
        await query.edit_message_text("✅ الگوی تکرار: چند تاریخ مشخص")
        logger.info(f"User {user_id} selected multi_date frequency for reminder {current_id}")

async def send_weekly_day_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(day, callback_data=f"weekly_day:{day}")] for day in DAYS_OF_WEEK]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("✅ روز هفته مورد نظر رو انتخاب کن:", reply_markup=reply_markup)
    context.user_data["waiting_for_weekly_day_buttons"] = True
    logger.info(f"User {update.effective_user.id} is selecting weekly day")

async def send_month_day_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    row = []
    for i in range(1, 32):
        row.append(InlineKeyboardButton(str(i), callback_data=f"month_day:{i}"))
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("✅ روز مورد نظر از ماه رو انتخاب کن:", reply_markup=reply_markup)
    context.user_data["waiting_for_month_day_buttons"] = True
    logger.info(f"User {update.effective_user.id} is selecting monthly day")

async def send_weekdays_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_id = context.user_data.get("current_reminder_id")
    reminders = context.user_data.get("reminders", [])
    if not reminders or not any(r["id"] == current_id for r in reminders):
        await update.callback_query.edit_message_text("یادآور فعلی پیدا نشد.")
        logger.error(f"Reminder {current_id} not found for user {update.effective_user.id}")
        return
    reminder = next((r for r in reminders if r["id"] == current_id), None)
    if reminder:
        context.user_data["selected_weekdays"] = set(reminder.get("weekdays", []))
    else:
        context.user_data["selected_weekdays"] = set()
    markup = build_weekdays_keyboard(context.user_data["selected_weekdays"])
    await update.callback_query.edit_message_text("✅ روزهای مورد نظر رو انتخاب کن (با زدن روی هر دکمه اضافه/حذف می‌شن):", reply_markup=markup)
    context.user_data["waiting_for_weekdays_buttons"] = True
    logger.info(f"User {update.effective_user.id} is selecting weekdays for reminder {current_id}")

async def day_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    context.user_data.update(load_user_data(user_id))
    current_id = context.user_data.get("current_reminder_id")
    reminders = context.user_data.get("reminders", [])
    reminder = next((r for r in reminders if r["id"] == current_id), None)

    if not reminder:
        await query.edit_message_text("یادآور فعلی پیدا نشد.")
        logger.error(f"Reminder {current_id} not found for user {user_id}")
        return

    if data.startswith("weekly_day:"):
        day = data.split(":")[1]
        reminder["weekly_day"] = day
        context.user_data["waiting_for_weekly_day_buttons"] = False
        await query.edit_message_text(f"✅ روز هفته تنظیم شد: {day}")
        save_user_data(user_id, context.user_data)
        if context.user_data.get(WAITING_FOR_EDIT_FREQUENCY):
            context.user_data[WAITING_FOR_EDIT_FREQUENCY] = False
            await query.message.reply_text("✅ الگوی تکرار جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
        else:
            text = (
                "📢 یادآوری کجا ارسال شود؟\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
            )
            await query.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
        logger.info(f"User {user_id} set weekly day {day} for reminder {current_id}")
    elif data.startswith("month_day:"):
        day = int(data.split(":")[1])
        reminder["monthly_day"] = day
        context.user_data["waiting_for_month_day_buttons"] = False
        await query.edit_message_text(f"✅ روز ماه تنظیم شد: {day}")
        save_user_data(user_id, context.user_data)
        if context.user_data.get(WAITING_FOR_EDIT_FREQUENCY):
            context.user_data[WAITING_FOR_EDIT_FREQUENCY] = False
            await query.message.reply_text("✅ الگوی تکرار جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
        else:
            text = (
                "📢 یادآوری کجا ارسال شود؟\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
            )
            await query.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
        logger.info(f"User {user_id} set monthly day {day} for reminder {current_id}")
    elif data.startswith("toggle_weekday:"):
        day = data.split(":")[1]
        selected = context.user_data.get("selected_weekdays", set())
        if isinstance(selected, list):
            selected = set(selected)
        if day in selected:
            selected.remove(day)
        else:
            selected.add(day)
        context.user_data["selected_weekdays"] = selected
        markup = build_weekdays_keyboard(selected)
        await query.edit_message_reply_markup(reply_markup=markup)
        save_user_data(user_id, context.user_data)
        logger.info(f"User {user_id} toggled weekday {day} for reminder {current_id}")
    elif data == "confirm_weekdays":
        selected = context.user_data.get("selected_weekdays", set())
        if selected:
            reminder["weekdays"] = list(selected)
            context.user_data["waiting_for_weekdays_buttons"] = False
            context.user_data.pop("selected_weekdays", None)
            await query.edit_message_text(f"✅ روزهای انتخاب‌شده ذخیره شدند: {', '.join(selected)}")
            save_user_data(user_id, context.user_data)
            if context.user_data.get(WAITING_FOR_EDIT_FREQUENCY):
                context.user_data[WAITING_FOR_EDIT_FREQUENCY] = False
                await query.message.reply_text("✅ الگوی تکرار جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
            else:
                text = (
                    "📢 یادآوری کجا ارسال شود؟\n"
                    "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                    "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                    "2️⃣ ربات را ادمین کنید.\n"
                    "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                    "4️⃣ به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
                )
                await query.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
            logger.info(f"User {user_id} confirmed weekdays {selected} for reminder {current_id}")
        else:
            await query.answer("حداقل یک روز انتخاب کن.", show_alert=True)
            logger.warning(f"User {user_id} tried to confirm empty weekdays for reminder {current_id}")

async def destination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    context.user_data.update(load_user_data(user_id))

    if data.startswith("register_chat:"):
        chat_id = int(data.split(":")[1])
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            admin_ids = [admin.user.id for admin in admins]
            if query.from_user.id in admin_ids and context.bot.id in admin_ids:
                chat = await context.bot.get_chat(chat_id)
                chat_data = load_chat_data()
                chat_data[str(chat_id)] = {"title": chat.title, "last_used": datetime.datetime.now().isoformat()}
                save_chat_data(chat_data)
                await query.edit_message_text(f"✅ گروه/کانال '{chat.title}' با موفقیت ثبت شد.")
                logger.info(f"User {query.from_user.id} registered chat {chat_id} ({chat.title})")
            else:
                await query.edit_message_text(f"⛔ شما یا ربات {BOT_USERNAME} باید ادمین این گروه/کانال باشید.")
                logger.warning(f"User {query.from_user.id} or bot not admin in chat {chat_id}")
        except Exception as e:
            await query.edit_message_text(f"⛔ خطا در ثبت گروه/کانال: {str(e)}")
            logger.error(f"Error registering chat {chat_id} for user {query.from_user.id}: {str(e)}")
        return

    current_id = context.user_data.get("current_reminder_id")
    reminders = context.user_data.get("reminders", [])
    reminder = next((r for r in reminders if r["id"] == current_id), None)

    if not reminder:
        await query.edit_message_text("یادآور فعلی پیدا نشد.")
        logger.error(f"Reminder {current_id} not found for user {user_id}")
        return

    is_editing = context.user_data.get("waiting_for_edit_destination", False)

    if data == "dest:private":
        reminder["chat_id"] = user_id
        context.user_data["waiting_for_edit_destination"] = False
        if is_editing:
            context.user_data["waiting_for_edit_choice"] = True
            await query.edit_message_text("✅ مقصد تنظیم شد: چت خصوصی. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
            logger.info(f"User {user_id} set destination to private chat for reminder {current_id} (edit mode)")
        else:
            await query.edit_message_text("✅ مقصد تنظیم شد: چت خصوصی")
            await query.message.reply_text("تنظیمات یادآور کامل شد.", reply_markup=get_main_keyboard())
            logger.info(f"User {user_id} set destination to private chat for reminder {current_id} (new reminder)")
        save_user_data(user_id, context.user_data)
    elif data == "dest:reload":
        admin_chats = await get_admin_chats(context, user_id)
        keyboard = get_destination_keyboard(admin_chats)
        if is_editing:
            await query.edit_message_text(
                "📢 مقصد جدید را انتخاب کنید:\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n",
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text(
                "📢 یادآوری کجا ارسال شود؟\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n",
                reply_markup=keyboard
            )
        logger.info(f"User {user_id} reloaded destination list for reminder {current_id}")
    elif data.startswith("dest:"):
        chat_id = int(data.split(":")[1])
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            admin_ids = [admin.user.id for admin in admins]
            if user_id in admin_ids and context.bot.id in admin_ids:
                reminder["chat_id"] = chat_id
                context.user_data["waiting_for_edit_destination"] = False
                chat = await context.bot.get_chat(chat_id)
                chat_data = load_chat_data()
                chat_data[str(chat_id)] = {"title": chat.title, "last_used": datetime.datetime.now().isoformat()}
                save_chat_data(chat_data)
                if is_editing:
                    context.user_data["waiting_for_edit_choice"] = True
                    await query.edit_message_text(f"✅ مقصد تنظیم شد: {chat.title}. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
                    logger.info(f"User {user_id} set destination to chat {chat_id} ({chat.title}) for reminder {current_id} (edit mode)")
                else:
                    await query.edit_message_text(f"✅ مقصد تنظیم شد: {chat.title}")
                    await query.message.reply_text("تنظیمات یادآور کامل شد.", reply_markup=get_main_keyboard())
                    logger.info(f"User {user_id} set destination to chat {chat_id} ({chat.title}) for reminder {current_id} (new reminder)")
                save_user_data(user_id, context.user_data)
            else:
                await query.edit_message_text(f"⛔ شما یا ربات {BOT_USERNAME} در این گروه/کانال ادمین نیستید.")
                logger.warning(f"User {user_id} or bot not admin in chat {chat_id} for reminder {current_id}")
        except Exception as e:
            await query.edit_message_text(f"⛔ خطا: {str(e)}")
            logger.error(f"Error setting destination chat {chat_id} for user {user_id}: {str(e)}")

async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    context.user_data.update(load_user_data(user_id))

    if data.startswith("delete:"):
        reminder_id = int(data.split(":")[1])
        await delete_reminder(update, context, reminder_id)
    elif data.startswith("edit:"):
        if data == "edit:message":
            context.user_data["waiting_for_edit_message"] = True
            await query.edit_message_text("لطفاً پیام جدید را بنویسید:")
            logger.info(f"User {user_id} is editing message for reminder")
        elif data == "edit:time":
            context.user_data["waiting_for_edit_time"] = True
            await query.edit_message_text("⏰ زمان جدید را با فرمت 24 ساعته وارد کنید (HH:MM):")
            logger.info(f"User {user_id} is editing time for reminder")
        elif data == "edit:frequency":
            context.user_data["waiting_for_edit_frequency"] = True
            keyboard = [
                [InlineKeyboardButton("روزانه", callback_data="freq:everyday")],
                [InlineKeyboardButton("هفتگی - یک روز", callback_data="freq:weekly")],
                [InlineKeyboardButton("هفتگی - چند روز", callback_data="freq:weekdays")],
                [InlineKeyboardButton("ماهانه", callback_data="freq:monthly")],
                [InlineKeyboardButton("یک تاریخ مشخص", callback_data="freq:once")],
                [InlineKeyboardButton("چند تاریخ مشخص", callback_data="freq:multi_date")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🔁 نوع تکرار جدید را انتخاب کنید:", reply_markup=reply_markup)
            logger.info(f"User {user_id} is editing frequency for reminder")
        elif data == "edit:destination":
            context.user_data["waiting_for_edit_destination"] = True
            admin_chats = await get_admin_chats(context, user_id)
            keyboard = get_destination_keyboard(admin_chats)
            await query.edit_message_text(
                "📢 مقصد جدید را انتخاب کنید:\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n",
                reply_markup=keyboard
            )
            logger.info(f"User {user_id} is editing destination for reminder")
        elif data == "edit:confirm":
            context.user_data["waiting_for_edit_choice"] = False
            context.user_data.pop("waiting_for_edit_message", None)
            context.user_data.pop("waiting_for_edit_time", None)
            context.user_data.pop("waiting_for_edit_frequency", None)
            context.user_data.pop("waiting_for_edit_destination", None)
            await query.edit_message_text("✅ ویرایش یادآور ذخیره شد.")
            await query.message.reply_text("برای دیدن لیست جدید، /listReminders را بزنید.", reply_markup=get_main_keyboard())
            save_user_data(user_id, context.user_data)
            logger.info(f"User {user_id} confirmed edit for reminder")
        else:
            reminder_id = int(data.split(":")[1])
            await edit_reminder(update, context, reminder_id)

async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE, reminder_id: int):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    reminders = context.user_data.get("reminders", [])
    
    reminders = [r for r in reminders if r["id"] != reminder_id]
    
    for i, reminder in enumerate(reminders, 1):
        reminder["id"] = i
    
    context.user_data["reminders"] = reminders

    save_user_data(user_id, context.user_data)
    await update.callback_query.edit_message_text(f"✅ یادآور شماره {reminder_id} حذف شد.")
    await update.callback_query.message.reply_text("برای دیدن لیست جدید، /listReminders را بزنید.", reply_markup=get_main_keyboard())
    logger.info(f"User {user_id} deleted reminder {reminder_id}")

async def edit_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE, reminder_id: int):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    reminders = context.user_data.get("reminders", [])
    reminder = next((r for r in reminders if r["id"] == reminder_id), None)
    
    if not reminder:
        await update.callback_query.edit_message_text("یادآور مورد نظر پیدا نشد.")
        logger.error(f"Reminder {reminder_id} not found for user {user_id}")
        return
    
    context.user_data["current_reminder_id"] = reminder_id
    context.user_data["waiting_for_edit_choice"] = True
    await update.callback_query.edit_message_text(
        "کدام بخش از یادآور را می‌خواهید ویرایش کنید؟",
        reply_markup=get_edit_choice_keyboard()
    )
    logger.info(f"User {user_id} started editing reminder {reminder_id}")