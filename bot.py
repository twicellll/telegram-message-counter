import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы состояний
CUSTOM_RANGE = 1

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            chat_id INTEGER, user_id INTEGER, username TEXT, message_time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Сохраняем каждое сообщение
async def save_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.chat.type in ['group', 'supergroup']:
        conn = sqlite3.connect("messages.db")
        c = conn.cursor()
        c.execute("INSERT INTO messages VALUES (?, ?, ?, ?)", (
            update.message.chat_id,
            update.message.from_user.id,
            update.message.from_user.username or update.message.from_user.first_name,
            update.message.date.strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я считаю сообщения. Напиши /stats чтобы посмотреть статистику.")

# /stats
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1 день", callback_data="1")],
        [InlineKeyboardButton("7 дней", callback_data="7")],
        [InlineKeyboardButton("30 дней", callback_data="30")],
        [InlineKeyboardButton("Выбрать даты", callback_data="custom")]
    ]
    await update.message.reply_text("Выбери период:", reply_markup=InlineKeyboardMarkup(keyboard))

# обработка inline-кнопок
async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()

    if query.data == "custom":
        await query.message.reply_text("Введи даты в формате: 2024-05-01 2024-05-10")
        return CUSTOM_RANGE

    days = int(query.data)
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        SELECT username, COUNT(*) FROM messages
        WHERE chat_id = ? AND message_time >= ?
        GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 10
    """, (chat_id, since))
    rows = c.fetchall()
    conn.close()

    if rows:
        response = f"📊 Статистика за последние {days} дней:\n"
        response += '\n'.join([f"{u} — {c}" for u, c in rows])
    else:
        response = "Нет сообщений за этот период."

    await query.message.reply_text(response)
    return ConversationHandler.END

# Обработка пользовательского диапазона
async def custom_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_date, end_date = update.message.text.split()
        chat_id = update.message.chat_id
        conn = sqlite3.connect("messages.db")
        c = conn.cursor()
        c.execute("""
            SELECT username, COUNT(*) FROM messages
            WHERE chat_id = ? AND message_time BETWEEN ? AND ?
            GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 10
        """, (chat_id, start_date + " 00:00:00", end_date + " 23:59:59"))
        rows = c.fetchall()
        conn.close()

        if rows:
            response = f"📊 Статистика с {start_date} по {end_date}:\n"
            response += '\n'.join([f"{u} — {c}" for u, c in rows])
        else:
            response = "Нет сообщений за этот период."

        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text("Неверный формат. Попробуй ещё раз: `2024-05-01 2024-05-10`", parse_mode='Markdown')

    return ConversationHandler.END

# 🚀 Запуск приложения
app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_message))

conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(stats_callback)],
    states={CUSTOM_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_range)]},
    fallbacks=[],
)
app.add_handler(conv_handler)

if __name__ == "__main__":
    import asyncio
    async def run():
        await app.bot.delete_webhook()
        await app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 10000)),
            webhook_url=os.environ["APP_URL"] + "/webhook"
        )
    asyncio.get_event_loop().run_until_complete(run())
