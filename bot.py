import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
import sqlite3

# --- Настройка ---
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # например: https://telegram-message-counter.onrender.com

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- База данных ---
def init_db():
    with sqlite3.connect("messages.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                chat_id INTEGER,
                user_id INTEGER,
                username TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()

init_db()

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я считаю сообщения.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("1 день", callback_data="1"),
            InlineKeyboardButton("7 дней", callback_data="7"),
            InlineKeyboardButton("30 дней", callback_data="30"),
        ]
    ]
    await update.message.reply_text(
        "Выбери период для статистики:", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type in ['group', 'supergroup']:
        data = (
            update.message.chat.id,
            update.message.from_user.id,
            update.message.from_user.username or update.message.from_user.full_name,
            update.message.date.strftime('%Y-%m-%d %H:%M:%S')
        )
        with sqlite3.connect("messages.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages VALUES (?, ?, ?, ?)", data)
            conn.commit()

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    days = int(query.data)
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

    with sqlite3.connect("messages.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, COUNT(*) as count FROM messages
            WHERE chat_id = ? AND timestamp >= ?
            GROUP BY user_id
            ORDER BY count DESC
            LIMIT 10
        """, (query.message.chat.id, since))
        rows = cursor.fetchall()

    if not rows:
        await query.message.reply_text("Нет сообщений за выбранный период.")
        return

    text = f"📊 Статистика за {days} дней:\n\n"
    for username, count in rows:
        text += f"{username}: {count} сообщений\n"

    await query.message.reply_text(text)

# --- Основной запуск ---
async def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    await application.bot.delete_webhook()
    await application.bot.set_webhook(f"{APP_URL}/webhook")
    await application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=f"{APP_URL}/webhook"
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
