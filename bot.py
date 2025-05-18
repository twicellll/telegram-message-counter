import os
import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы для состояний
WAITING_FOR_DATES = 1

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("messages.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            message_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Сохранение сообщения в БД
def save_message(chat_id, user_id, username, message_time):
    conn = sqlite3.connect("messages.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (chat_id, user_id, username, message_time)
        VALUES (?, ?, ?, ?)
    ''', (chat_id, user_id, username, message_time))
    conn.commit()
    conn.close()

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот, считающий сообщения в группе.")

# Сохраняем входящие сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message.chat.type in ['group', 'supergroup']:
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        message_time = message.date.strftime('%Y-%m-%d %H:%M:%S')
        save_message(chat_id, user_id, username, message_time)
        logger.info(f"Сообщение сохранено: {username} в {message_time}")

# /stats
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("За день", callback_data='1')],
        [InlineKeyboardButton("За 7 дней", callback_data='7')],
        [InlineKeyboardButton("За 30 дней", callback_data='30')],
        [InlineKeyboardButton("Выбрать даты", callback_data='custom')]
    ])
    await update.message.reply_text("Выбери период:", reply_markup=keyboard)

# Обработка кнопок
async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'custom':
        await query.message.reply_text("Введите даты в формате: `2024-05-01 2024-05-10`", parse_mode='Markdown')
        return WAITING_FOR_DATES

    days = int(query.data)
    since = datetime.utcnow() - timedelta(days=days)
    return await send_stats(query.message.chat_id, since, None, query)

# Обработка пользовательских дат
async def custom_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date_from_str, date_to_str = update.message.text.strip().split()
        date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d") + timedelta(days=1)
    except Exception:
        await update.message.reply_text("Неверный формат. Используй: `2024-05-01 2024-05-10`", parse_mode='Markdown')
        return WAITING_FOR_DATES

    await send_stats(update.message.chat_id, date_from, date_to, update)
    return ConversationHandler.END

# Формирование и отправка статистики
async def send_stats(chat_id, date_from, date_to, context_obj):
    date_to = date_to or datetime.utcnow()
    conn = sqlite3.connect("messages.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT username, COUNT(*) as count FROM messages
        WHERE chat_id = ? AND message_time BETWEEN ? AND ?
        GROUP BY user_id
        ORDER BY count DESC
        LIMIT 10
    ''', (chat_id, date_from.isoformat(), date_to.isoformat()))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await context_obj.message.reply_text("Нет сообщений за выбранный период.")
        return

    response = f"📊 Статистика с {date_from.strftime('%Y-%m-%d')} по {date_to.strftime('%Y-%m-%d')}:\n\n"
    for username, count in rows:
        response += f"{username} — {count} сообщений\n"

    await context_obj.message.reply_text(response)

# Главная точка входа
async def run():
    init_db()
    TOKEN = os.environ["BOT_TOKEN"]
    APP_URL = os.environ["APP_URL"]

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(stats_callback))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(stats_callback, pattern='^custom$')],
        states={WAITING_FOR_DATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_dates)]},
        fallbacks=[]
    ))

    await app.bot.delete_webhook()
    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=APP_URL + "/webhook"
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
