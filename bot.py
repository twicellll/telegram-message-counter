import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен будет браться из переменной окружения
import os
TOKEN = os.getenv("BOT_TOKEN")


# Инициализация базы данных SQLite
def init_db():
    try:
        conn = sqlite3.connect('messages.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages
                     (chat_id INTEGER, user_id INTEGER, username TEXT, message_time TEXT)''')
        conn.commit()
        logger.info("База данных инициализирована")
    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных: {e}")
    finally:
        conn.close()

# Сохранение сообщения
def save_message(chat_id, user_id, username, message_time):
    try:
        conn = sqlite3.connect('messages.db')
        c = conn.cursor()
        c.execute("INSERT INTO messages (chat_id, user_id, username, message_time) VALUES (?, ?, ?, ?)",
                  (chat_id, user_id, username, message_time))
        conn.commit()
        logger.info(f"Сообщение сохранено: {username}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка сохранения: {e}")
    finally:
        conn.close()

# Команда /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот для подсчета сообщений запущен!")

# Обработчик сообщений
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.chat.type in ['group', 'supergroup']:
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        message_time = update.message.date.strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"Сообщение: chat_id={chat_id}, username={username}, text={update.message.text or '[Non-text]'}")
        save_message(chat_id, user_id, username, message_time)

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.ALL, message_handler))
    logger.info("Бот запущен")
    application.run_polling()

if __name__ == '__main__':
    main()