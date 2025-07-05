from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.constants import BOT_USERNAME
import logging

logger = logging.getLogger(__name__)

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