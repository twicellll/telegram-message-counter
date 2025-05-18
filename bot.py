import os
import sqlite3
import logging
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ConversationHandler
)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен из переменной окружения
TOKEN = os.getenv("BOT_TOKEN")

# Стейт для пользовательского ввода
WAITING_FOR_DATES = range(1)

# Инициализация базы
def init_db():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            message_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Сохраняем сообщения
def save_message(chat_id, user_id, username, message_time):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages VALUES (?, ?, ?, ?)", (chat_id, user_id, username, message_time))
    conn.commit()
    conn.close()

# /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я считаю сообщения в группе 📊")

# Счётчик сообщений
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.chat.type in ['group', 'supergroup']:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.full_name
        message_time = update.message.date.strftime('%Y-%m-%d %H:%M:%S')
        save_message(chat_id, user_id, username, message_time)

# /stats показывает клавиатуру
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 1 день", callback_data="1d"),
         InlineKeyboardButton("📆 7 дней", callback_data="7d")],
        [InlineKeyboardButton("📊 30 дней", callback_data="30d"),
         InlineKeyboardButton("📌 Выбрать период", callback_data="custom")]
    ])
    await update.message.reply_text("Выбери период статистики:", reply_markup=keyboard)

# Обработка кнопки
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if query.data == "custom":
        await query.message.reply_text("Отправь даты в формате: `2024-05-01 2024-05-10`", parse_mode='Markdown')
        return WAITING_FOR_DATES

    days = int(query.data.replace("d", ""))
    since = datetime.utcnow() - timedelta(days=days)
    return await send_stats(query.message, chat_id, since)

# Ввод дат от пользователя
async def handle_custom_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date_from_str, date_to_str = update.message.text.strip().split()
        date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d") + timedelta(days=1)
    except Exception:
        await update.message.reply_text("Неверный формат. Попробуй так: `2024-05-01 2024-05-10`", parse_mode='Markdown')
        return WAITING_FOR_DATES

    return await send_stats(update.message, update.message.chat.id, date_from, date_to)

# Функция вывода статистики
async def send_stats(message, chat_id, date_from, date_to=None):
    date_to = date_to or datetime.utcnow()

    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''
        SELECT username, COUNT(*) FROM messages
        WHERE chat_id = ? AND message_time >= ? AND message_time < ?
        GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 10
    ''', (chat_id, date_from.isoformat(), date_to.isoformat()))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await message.reply_text("Нет сообщений за указанный период.")
        return ConversationHandler.END

    if date_to - date_from >= timedelta(days=30):
        period_text = f"с {date_from.strftime('%Y-%m-%d')} по {(date_to - timedelta(days=1)).strftime('%Y-%m-%d')}"
    else:
        period_text = f"за период"

    text = f"📊 Статистика сообщений {period_text}:\n\n"
    for username, count in rows:
        text += f"— {username}: {count} сообщений\n"

    await message.reply_text(text)
    return ConversationHandler.END

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

# main
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(handle_callback))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_callback, pattern="custom")],
        states={WAITING_FOR_DATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_dates)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)

    app.add_handler(MessageHandler(filters.ALL, message_handler))
    logger.info("Бот запущен")
    app.run_polling()

if __name__ == '__main__':
    main()
