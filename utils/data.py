import json
import os
import datetime
import asyncio
import scheduler
from .constants import DATA_FILE, CHAT_DATA_FILE

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
        except json.JSONDecodeError:
            print("Failed to decode reminders.json")
            return {}
    return {}

def load_chat_data():
    if os.path.exists(CHAT_DATA_FILE):
        try:
            with open(CHAT_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Failed to decode chat_data.json")
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