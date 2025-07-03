from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup)
from telegram.ext import (Application, CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, filters, ContextTypes)
from telegram.request import HTTPXRequest
import datetime, logging, os, json, asyncio, scheduler
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

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_user_data(user_id):
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            user_data = data.get(str(user_id), {})
            reminders = user_data.get("reminders", [])
            for reminder in reminders:
                if "time" in reminder:
                    try:
                        reminder["time"] = datetime.datetime.strptime(reminder["time"], "%H:%M").time()
                    except:
                        reminder["time"] = None
            return user_data
        except json.JSONDecodeDecodeError:
            logger.error("Failed to decode reminders.json")
            return {}
    return {}

def load_chat_data():
    if os.path.exists(CHAT_DATA_FILE):
        try:
            with open(CHAT_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Failed to decode chat_data.json")
            return {}
    return {}

def save_chat_data(chat_data):
    with open(CHAT_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=2)

def save_user_data(user_id, user_data):
    all_data = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                all_data = json.load(f)
        except json.JSONDecodeError:
            all_data = {}

    reminders = user_data.get("reminders", [])
    serializable_reminders = []
    for reminder in reminders:
        serializable_reminder = {}
        for key, value in reminder.items():
            if key == "time" and isinstance(value, datetime.time):
                serializable_reminder[key] = value.strftime("%H:%M")
            elif isinstance(value, set):
                serializable_reminder[key] = list(value)
            else:
                serializable_reminder[key] = value
        serializable_reminders.append(serializable_reminder)

    all_data[str(user_id)] = {"reminders": serializable_reminders}

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    asyncio.create_task(scheduler.schedule_all_reminders())

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

async def get_admin_chats(context, user_id):
    chat_data = load_chat_data()
    admin_chats = []
    updated_chat_data = {}
    for chat_id, chat_info in chat_data.items():
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            admin_ids = [admin.user.id for admin in admins]
            if user_id in admin_ids and context.bot.id in admin_ids:
                title = chat_info.get("title", "بدون نام")
                last_used = chat_info.get("last_used", "1970-01-01T00:00:00")
                admin_chats.append((chat_id, title, last_used))
                updated_chat_data[chat_id] = chat_info
        except Exception as e:
            logger.error(f"Error checking admins for chat {chat_id}: {e}")
    save_chat_data(updated_chat_data)  # فقط چت‌های معتبر ذخیره می‌شن
    return admin_chats

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

# Start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    await update.message.reply_text(
        "سلام! من یک ربات یادآور هستم.\n"
        "برای انتخاب هر گزینه، روی دکمه‌ها کلیک کن:",
        reply_markup=get_main_keyboard()
    )
    save_user_data(user_id, context.user_data)
    logger.info(f"User {user_id} started the bot")

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    help_text = (
        "🤖 راهنمای استفاده از ربات یادآور\n\n"
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
        "4️⃣ به چت ربات برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود (ممکن است چند ثانیه طول بکشد).\n"
        "⚠️ نکته: اگر گروه/کانال در لیست ظاهر نشد، مطمئن شوید که هم شما و هم ربات همچنان ادمین هستید."
    )
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard(), parse_mode="HTML")
    save_user_data(user_id, context.user_data)
    logger.info(f"User {user_id} accessed help")

# New Reminder command
async def new_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))
    reminders = context.user_data.get("reminders", [])
    new_id = max([r["id"] for r in reminders], default=0) + 1
    new_reminder = {"id": new_id}
    reminders.append(new_reminder)
    context.user_data["reminders"] = reminders
    context.user_data["current_reminder_id"] = new_id
    context.user_data[WAITING_FOR_MESSAGE] = True
    await update.message.reply_text(
        f"یادآور جدید با شناسه {new_id} ایجاد شد. لطفاً متن پیام یادآوری را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    save_user_data(user_id, context.user_data)
    logger.info(f"User {user_id} created new reminder with ID {new_id}")

# List Reminders command
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
        freq_translated = FREQUENCY_TRANSLATIONS.get(freq, "⛔ تنظیم نشده")

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

# Delete Reminder
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

# Edit Reminder
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
    context.user_data[WAITING_FOR_EDIT_CHOICE] = True
    await update.callback_query.edit_message_text(
        "کدام بخش از یادآور را می‌خواهید ویرایش کنید؟",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ویرایش پیام", callback_data="edit:message")],
            [InlineKeyboardButton("ویرایش زمان", callback_data="edit:time")],
            [InlineKeyboardButton("ویرایش الگوی تکرار", callback_data="edit:frequency")],
            [InlineKeyboardButton("ویرایش مقصد", callback_data="edit:destination")],
            [InlineKeyboardButton("تایید و ذخیره", callback_data="edit:confirm")]
        ])
    )
    logger.info(f"User {user_id} started editing reminder {reminder_id}")

async def send_weekly_day_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(day, callback_data=f"weekly_day:{day}")] for day in DAYS_OF_WEEK]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("✅ روز هفته مورد نظر رو انتخاب کن:", reply_markup=reply_markup)
    context.user_data[WAITING_FOR_WEEKLY_DAY_BUTTONS] = True
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
    context.user_data[WAITING_FOR_MONTH_DAY_BUTTONS] = True
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
    context.user_data[WAITING_FOR_WEEKDAYS_BUTTONS] = True
    logger.info(f"User {update.effective_user.id} is selecting weekdays for reminder {current_id}")

def build_weekdays_keyboard(selected_days):
    keyboard = []
    for day in DAYS_OF_WEEK:
        label = f"✅ {day}" if day in selected_days else day
        keyboard.append([InlineKeyboardButton(label, callback_data=f"toggle_weekday:{day}")])
    keyboard.append([InlineKeyboardButton("✅ تایید", callback_data="confirm_weekdays")])
    return InlineKeyboardMarkup(keyboard)

async def day_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
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
        context.user_data[WAITING_FOR_WEEKLY_DAY_BUTTONS] = False
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
                "4️⃣ (ممکن است چند ثانیه طول بکشد) به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
            )
            await query.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
        logger.info(f"User {user_id} set weekly day {day} for reminder {current_id}")
    elif data.startswith("month_day:"):
        day = int(data.split(":")[1])
        reminder["monthly_day"] = day
        context.user_data[WAITING_FOR_MONTH_DAY_BUTTONS] = False
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
                "4️⃣ (ممکن است چند ثانیه طول بکشد) به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
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
            context.user_data[WAITING_FOR_WEEKDAYS_BUTTONS] = False
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
                    "4️⃣ (ممکن است چند ثانیه طول بکشد) به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
                )
                await query.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
            logger.info(f"User {user_id} confirmed weekdays {selected} for reminder {current_id}")
        else:
            await query.answer("حداقل یک روز انتخاب کن.", show_alert=True)
            logger.warning(f"User {user_id} tried to confirm empty weekdays for reminder {current_id}")

    save_user_data(user_id, context.user_data)

async def destination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
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

    is_editing = context.user_data.get(WAITING_FOR_EDIT_DESTINATION, False)

    if data == "dest:private":
        reminder["chat_id"] = user_id
        context.user_data[WAITING_FOR_EDIT_DESTINATION] = False
        if is_editing:
            context.user_data[WAITING_FOR_EDIT_CHOICE] = True
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
        await query.edit_message_text(
            "📢 مقصد جدید را انتخاب کنید:\n"
            "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
            "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
            "2️⃣ ربات را ادمین کنید.\n"
            "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
            "4️⃣ (ممکن است چند ثانیه طول بکشد) به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n",
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
                context.user_data[WAITING_FOR_EDIT_DESTINATION] = False
                chat = await context.bot.get_chat(chat_id)
                chat_data = load_chat_data()
                chat_data[str(chat_id)] = {"title": chat.title, "last_used": datetime.datetime.now().isoformat()}
                save_chat_data(chat_data)
                if is_editing:
                    context.user_data[WAITING_FOR_EDIT_CHOICE] = True
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
    save_user_data(user_id, context.user_data)

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
                "4️⃣ (ممکن است چند ثانیه طول بکشد) به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
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
        context.user_data[WAITING_FOR_ONCE_DATE] = True
        await query.message.reply_text("📌 تاریخ مشخص رو وارد کن (مثلاً 1404/04/10):", reply_markup=get_cancel_keyboard())
        await query.edit_message_text("✅ الگوی تکرار: یک تاریخ مشخص")
        logger.info(f"User {user_id} selected once frequency for reminder {current_id}")
    elif freq == "multi_date":
        context.user_data[WAITING_FOR_MULTI_DATE] = True
        await query.message.reply_text("📌 تاریخ‌ها رو با کاما جدا کن (مثلاً 1404/04/10, 1404/05/01):", reply_markup=get_cancel_keyboard())
        await query.edit_message_text("✅ الگوی تکرار: چند تاریخ مشخص")
        logger.info(f"User {user_id} selected multi_date frequency for reminder {current_id}")

    save_user_data(user_id, context.user_data)

async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    context.user_data.update(load_user_data(user_id))

    if data.startswith("delete:"):
        reminder_id = int(data.split(":")[1])
        await delete_reminder(update, context, reminder_id)
    elif data.startswith("edit:"):
        if data == "edit:message":
            context.user_data[WAITING_FOR_EDIT_MESSAGE] = True
            await query.edit_message_text("لطفاً پیام جدید را بنویسید:")
            logger.info(f"User {user_id} is editing message for reminder")
        elif data == "edit:time":
            context.user_data[WAITING_FOR_EDIT_TIME] = True
            await query.edit_message_text("⏰ زمان جدید را با فرمت 24 ساعته وارد کنید (HH:MM):")
            logger.info(f"User {user_id} is editing time for reminder")
        elif data == "edit:frequency":
            context.user_data[WAITING_FOR_EDIT_FREQUENCY] = True
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
            context.user_data[WAITING_FOR_EDIT_DESTINATION] = True
            admin_chats = await get_admin_chats(context, user_id)
            keyboard = get_destination_keyboard(admin_chats)
            await query.edit_message_text(
                "📢 مقصد جدید را انتخاب کنید:\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ (ممکن است چند ثانیه طول بکشد) به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n",
                reply_markup=keyboard
            )
            logger.info(f"User {user_id} is editing destination for reminder")
        elif data == "edit:confirm":
            context.user_data[WAITING_FOR_EDIT_CHOICE] = False
            context.user_data.pop(WAITING_FOR_EDIT_MESSAGE, None)
            context.user_data.pop(WAITING_FOR_EDIT_TIME, None)
            context.user_data.pop(WAITING_FOR_EDIT_FREQUENCY, None)
            context.user_data.pop(WAITING_FOR_EDIT_DESTINATION, None)
            await query.edit_message_text("✅ ویرایش یادآور ذخیره شد.")
            await query.message.reply_text("برای دیدن لیست جدید، /listReminders را بزنید.", reply_markup=get_main_keyboard())
            save_user_data(user_id, context.user_data)
            logger.info(f"User {user_id} confirmed edit for reminder")
        else:
            reminder_id = int(data.split(":")[1])
            await edit_reminder(update, context, reminder_id)

    save_user_data(user_id, context.user_data)

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
    freq_translated = FREQUENCY_TRANSLATIONS.get(freq, "⛔ تنظیم نشده")

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
            context.user_data.pop(WAITING_FOR_MESSAGE, None)
            context.user_data.pop(WAITING_FOR_TIME, None)
            context.user_data.pop(WAITING_FOR_ONCE_DATE, None)
            context.user_data.pop(WAITING_FOR_MULTI_DATE, None)
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

    if context.user_data.get(WAITING_FOR_MESSAGE):
        reminder["message"] = txt
        context.user_data[WAITING_FOR_MESSAGE] = False
        context.user_data[WAITING_FOR_TIME] = True
        await update.message.reply_text("✅ پیام ذخیره شد. حالا زمان را با فرمت 24 ساعته با اعداد انگلیسی وارد کنید (HH:MM):", reply_markup=get_cancel_keyboard())
        save_user_data(user_id, context.user_data)
        logger.info(f"User {user_id} set message for reminder {current_id}")
    elif context.user_data.get(WAITING_FOR_TIME):
        try:
            t = datetime.datetime.strptime(txt, "%H:%M").time()
            reminder["time"] = t
            context.user_data[WAITING_FOR_TIME] = False
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
    elif context.user_data.get(WAITING_FOR_ONCE_DATE):
        reminder["once_date"] = txt
        context.user_data[WAITING_FOR_ONCE_DATE] = False
        await update.message.reply_text(f"✅ تاریخ ذخیره شد: {txt}")
        save_user_data(user_id, context.user_data)
        if context.user_data.get(WAITING_FOR_EDIT_FREQUENCY):
            context.user_data[WAITING_FOR_EDIT_FREQUENCY] = False
            await update.message.reply_text("✅ الگوی تکرار جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
        else:
            text = (
                "📢 یادآوری کجا ارسال شود؟\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ (ممکن است چند ثانیه طول بکشد) به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
            )
            await update.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
        logger.info(f"User {user_id} set once date {txt} for reminder {current_id}")
    elif context.user_data.get(WAITING_FOR_MULTI_DATE):
        dates = [d.strip() for d in txt.split(",")]
        reminder["multi_dates"] = dates
        context.user_data[WAITING_FOR_MULTI_DATE] = False
        await update.message.reply_text(f"✅ تاریخ‌ها ذخیره شدند.")
        save_user_data(user_id, context.user_data)
        if context.user_data.get(WAITING_FOR_EDIT_FREQUENCY):
            context.user_data[WAITING_FOR_EDIT_FREQUENCY] = False
            await update.message.reply_text("✅ الگوی تکرار جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
        else:
            text = (
                "📢 یادآوری کجا ارسال شود؟\n"
                "⚠️ اگر گروه یا کانال مورد نظرتان در لیست نیست:\n"
                "1️⃣ ربات را به گروه/کانال اضافه کنید.\n"
                "2️⃣ ربات را ادمین کنید.\n"
                "3️⃣ در گروه/کانال، روی دکمه «ثبت گروه/کانال» در پیام ارسال شده توسط ربات کلیک کنید.\n"
                "4️⃣ (ممکن است چند ثانیه طول بکشد) به اینجا برگردید و «به‌روزرسانی لیست» را بزنید تا گروه/کانال جدید نمایش داده شود.\n"
            )
            await update.message.reply_text(text, reply_markup=get_destination_keyboard(await get_admin_chats(context, user_id)))
        logger.info(f"User {user_id} set multi dates {dates} for reminder {current_id}")
    elif context.user_data.get(WAITING_FOR_EDIT_MESSAGE):
        reminder["message"] = txt
        context.user_data[WAITING_FOR_EDIT_MESSAGE] = False
        await update.message.reply_text("✅ پیام جدید ذخیره شد. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
        save_user_data(user_id, context.user_data)
        logger.info(f"User {user_id} edited message for reminder {current_id}")
    elif context.user_data.get(WAITING_FOR_EDIT_TIME):
        try:
            t = datetime.datetime.strptime(txt, "%H:%M").time()
            reminder["time"] = t
            context.user_data[WAITING_FOR_EDIT_TIME] = False
            await update.message.reply_text(f"✅ زمان جدید ذخیره شد: {t.strftime('%H:%M')}. بخش دیگری را ویرایش یا تایید کنید:", reply_markup=get_edit_choice_keyboard())
            save_user_data(user_id, context.user_data)
            logger.info(f"User {user_id} edited time to {t.strftime('%H:%M')} for reminder {current_id}")
        except:
            await update.message.reply_text("⛔ فرمت اشتباه. ساعت رو مثل 14:30 وارد کن.", reply_markup=get_cancel_keyboard())
            logger.warning(f"User {user_id} provided invalid time format during edit for reminder {current_id}")
    else:
        await update.message.reply_text("⛔ من متوجه نشدم. لطفاً از دستورات استفاده کن.", reply_markup=get_main_keyboard())
        logger.warning(f"User {user_id} sent unhandled message")

    save_user_data(user_id, context.user_data)

async def chat_member_added(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    new_members = update.my_chat_member.new_chat_member
    old_members = update.my_chat_member.old_chat_member

    if new_members.status in ["member", "administrator"] and old_members.status in ["left", "kicked"]:
        if new_members.user.id == context.bot.id:
            keyboard = [
                [InlineKeyboardButton("ثبت گروه/کانال", callback_data=f"register_chat:{chat_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"سلام! من {BOT_USERNAME} هستم.\nآیا می‌خواهید این گروه/کانال را ثبت کنم؟",
                reply_markup=reply_markup
            )
            logger.info(f"Bot added to chat {chat_id}, sent registration message")

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        "برای ارتباط با پشتیبانی ربات به آیدی زیر پیام دهید.\n"
        f"{SUPPORT_USERNAME}",
        reply_markup=get_main_keyboard()
    )
    logger.info(f"User {user_id} accessed support")

async def on_startup(app: Application):
    await scheduler.schedule_all_reminders()
    scheduler.scheduler.start()
    logger.info("Scheduler started")

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

if __name__ == '__main__':
    logger.info("Bot started...")
    request = HTTPXRequest(connect_timeout=10.0, read_timeout=20.0)
    app = Application.builder().token(TELEGRAM_TOKEN).request(request).build()

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(یادآور جدید|نمایش آخرین یادآور|نمایش همه یادآورها|راهنما|پشتیبانی)$"), label_router))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("newreminder", new_reminder_command))
    app.add_handler(CommandHandler("showreminder", show_reminder_command))
    app.add_handler(CommandHandler("listreminders", list_reminders_command))
    app.add_handler(CommandHandler("support", support_command))
    app.add_handler(CallbackQueryHandler(frequency_callback, pattern="^freq:"))
    app.add_handler(CallbackQueryHandler(day_selection_callback, pattern="^(weekly_day|month_day|toggle_weekday|confirm_weekdays):?"))
    app.add_handler(CallbackQueryHandler(action_callback, pattern="^(edit|delete):"))
    app.add_handler(CallbackQueryHandler(destination_callback, pattern="^(dest|register_chat):"))
    app.add_handler(ChatMemberHandler(chat_member_added, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    app.post_init = on_startup

    logger.info("Bot is polling...")
    app.run_polling()
    logger.info("Bot stopped.")