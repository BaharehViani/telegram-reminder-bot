import json
import os
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from persiantools.jdatetime import JalaliDate
from telegram import Bot
from utils.constants import TELEGRAM_TOKEN
from utils.constants import DATA_FILE

bot = Bot(token=TELEGRAM_TOKEN)
scheduler = AsyncIOScheduler(timezone="Asia/Tehran")

def load_all_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

async def send_reminder(chat_id, reminder_id, message):
    print(f"Attempting to send reminder {reminder_id} to chat {chat_id} with message: {message}")
    try:
        await bot.send_message(chat_id=chat_id, text=f"🔔 یادآوری: {message}")
        print(f"Successfully sent reminder {reminder_id} to chat {chat_id}")
    except Exception as e:
        print(f"Error sending reminder {reminder_id} to chat {chat_id}: {e}")

def schedule_monthly_jalali(chat_id, reminder_id, message, jalali_day, t):
    today = JalaliDate.today()
    year, month = today.year, today.month
    for i in range(12):
        m = month + i
        y = year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        try:
            j_date = JalaliDate(y, m, jalali_day)
        except ValueError:
            continue
        g_date = j_date.to_gregorian()
        run_dt = datetime.datetime.combine(g_date, t)
        if run_dt > datetime.datetime.now():
            scheduler.add_job(
                send_reminder,
                DateTrigger(run_date=run_dt),
                args=[chat_id, reminder_id, message],
                id=f"{chat_id}_{reminder_id}_monthly_{y}_{m}"
            )
            print(f"Scheduled monthly (Jalali) reminder {reminder_id} for chat {chat_id}: {j_date} at {t}")

async def schedule_all_reminders():
    scheduler.remove_all_jobs()
    data = load_all_data()
    weekday_map = {
        "دوشنبه": 0,
        "سه‌شنبه": 1,
        "چهارشنبه": 2,
        "پنج‌شنبه": 3,
        "جمعه": 4,
        "شنبه": 5,
        "یک‌شنبه": 6
    }

    for user_id, info in data.items():
        user_id = int(user_id)
        reminders = info.get("reminders", [])
        
        for reminder in reminders:
            reminder_id = reminder.get("id")
            message = reminder.get("message")
            time = reminder.get("time")
            frequency = reminder.get("frequency")
            chat_id = reminder.get("chat_id", user_id)

            if not (reminder_id and message and time and frequency and chat_id):
                print(f"Skipping incomplete reminder {reminder_id} for user {user_id} in chat {chat_id}")
                continue

            try:
                if isinstance(time, str):
                    t = datetime.datetime.strptime(time, "%H:%M").time()
                else:
                    t = time
            except:
                print(f"Invalid time format for reminder {reminder_id} for user {user_id} in chat {chat_id}: {time}")
                continue

            if frequency == "everyday":
                scheduler.add_job(
                    send_reminder,
                    CronTrigger(hour=t.hour, minute=t.minute),
                    args=[chat_id, reminder_id, message],
                    id=f"{chat_id}_{reminder_id}_everyday"
                )
                print(f"Scheduled everyday reminder {reminder_id} for chat {chat_id} at {t.strftime('%H:%M')}")

            elif frequency == "weekdays":
                weekdays = reminder.get("weekdays", [])
                for day_name in weekdays:
                    if day_name in weekday_map:
                        scheduler.add_job(
                            send_reminder,
                            CronTrigger(day_of_week=weekday_map[day_name], hour=t.hour, minute=t.minute),
                            args=[chat_id, reminder_id, message],
                            id=f"{chat_id}_{reminder_id}_weekdays_{day_name}"
                        )
                        print(f"Scheduled weekdays reminder {reminder_id} for chat {chat_id} on {day_name} at {t.strftime('%H:%M')}")
                    else:
                        print(f"Invalid weekday name for reminder {reminder_id} for chat {chat_id}: {day_name}")

            elif frequency == "weekly":
                day_name = reminder.get("weekly_day")
                if day_name in weekday_map:
                    scheduler.add_job(
                        send_reminder,
                        CronTrigger(day_of_week=weekday_map[day_name], hour=t.hour, minute=t.minute),
                        args=[chat_id, reminder_id, message],
                        id=f"{chat_id}_{reminder_id}_weekly"
                    )
                    print(f"Scheduled weekly reminder {reminder_id} for chat {chat_id} on {day_name} at {t.strftime('%H:%M')}")

            elif frequency == "monthly":
                day = reminder.get("monthly_day")
                if isinstance(day, int):
                    schedule_monthly_jalali(chat_id, reminder_id, message, day, t)
                    print(f"Scheduled monthly reminder {reminder_id} for chat {chat_id} on day {day} at {t.strftime('%H:%M')}")

            elif frequency == "once":
                jalali_str = reminder.get("once_date")
                try:
                    jalali_date = JalaliDate.strptime(jalali_str, "%Y/%m/%d")
                    g_date = jalali_date.to_gregorian()
                    dt = datetime.datetime.combine(g_date, t)
                    if dt > datetime.datetime.now():
                        scheduler.add_job(
                            send_reminder,
                            DateTrigger(run_date=dt),
                            args=[chat_id, reminder_id, message],
                            id=f"{chat_id}_{reminder_id}_once"
                        )
                        print(f"Scheduled one-time reminder {reminder_id} for chat {chat_id} on {jalali_str} at {t.strftime('%H:%M')}")
                except:
                    print(f"Invalid date format for reminder {reminder_id} for chat {chat_id}: {jalali_str}")
                    continue

            elif frequency == "multi_date":
                dates = reminder.get("multi_dates", [])
                for i, d in enumerate(dates):
                    try:
                        jalali_date = JalaliDate.strptime(d, "%Y/%m/%d")
                        g_date = jalali_date.to_gregorian()
                        dt = datetime.datetime.combine(g_date, t)
                        if dt > datetime.datetime.now():
                            scheduler.add_job(
                                send_reminder,
                                DateTrigger(run_date=dt),
                                args=[chat_id, reminder_id, message],
                                id=f"{chat_id}_{reminder_id}_multi_{i}"
                            )
                            print(f"Scheduled multi-date reminder {reminder_id} for chat {chat_id} on {d} at {t.strftime('%H:%M')}")
                    except:
                        print(f"Invalid date format for reminder {reminder_id} for chat {chat_id}: {d}")
                        continue