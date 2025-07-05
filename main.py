from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, filters
from telegram.request import HTTPXRequest
import logging
import scheduler
from utils.constants import TELEGRAM_TOKEN
from handlers.commands import start_command, help_command, new_reminder_command, show_reminder_command, list_reminders_command, support_command
from handlers.callbacks import frequency_callback, day_selection_callback, action_callback, destination_callback
from handlers.messages import handle_message, label_router
from handlers.chat_member import chat_member_added

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def on_startup(app: Application):
    await scheduler.schedule_all_reminders()
    scheduler.scheduler.start()
    logger.info("Scheduler started")

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