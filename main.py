import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import sqlite3
import json
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
BOTNAME = os.getenv('BOT_NAME')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('digital_imprints.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            imprint_id TEXT UNIQUE,
            name TEXT,
            creation_date TEXT,
            last_update TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            timestamp TEXT,
            type TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    conn.commit()
    conn.close()

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('digital_imprints.db')
    c = conn.cursor()
    
    # Проверяем, существует ли уже пользователь
    c.execute('SELECT imprint_id FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    if not result:
        # Создаем новый imprint_id
        imprint_id = str(uuid.uuid4())
        c.execute('''
            INSERT INTO users (user_id, imprint_id, name, creation_date, last_update)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, imprint_id, update.effective_user.full_name, 
              datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
    else:
        imprint_id = result[0]
    
    conn.close()
    
    welcome_message = (
        "Добро пожаловать в бота 'Посмертие'!\n\n"
        "Здесь вы можете создать цифровой слепок своей личности, "
        "сохраняя свои мысли, интересы и знания.\n\n"
        "Команды:\n"
        "/add_memory - Добавить новое воспоминание или мысль\n"
        "/view_memories - Просмотреть сохраненные воспоминания\n"
        "/get_link - Получить ссылку на ваш цифровой слепок\n"
        "/help - Показать это сообщение"
    )
    
    await update.message.reply_text(welcome_message)

# Обработчик команды /add_memory
async def add_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отправьте мне текст, ссылки или любую информацию, "
        "которую хотите сохранить в своем цифровом слепке."
    )
    context.user_data['waiting_for_memory'] = True

# Обработчик для сохранения воспоминаний
async def save_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_memory'):
        return
    
    user_id = update.effective_user.id
    content = update.message.text
    
    conn = sqlite3.connect('digital_imprints.db')
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO memories (user_id, content, timestamp, type)
        VALUES (?, ?, ?, ?)
    ''', (user_id, content, datetime.now().isoformat(), 'text'))
    
    c.execute('''
        UPDATE users 
        SET last_update = ? 
        WHERE user_id = ?
    ''', (datetime.now().isoformat(), user_id))
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        "Ваша мысль сохранена! Продолжайте делиться или используйте /done, "
        "когда закончите."
    )

# Обработчик команды /view_memories
async def view_memories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('digital_imprints.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT content, timestamp 
        FROM memories 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 5
    ''', (user_id,))
    
    memories = c.fetchall()
    conn.close()
    
    if not memories:
        await update.message.reply_text(
            "У вас пока нет сохраненных воспоминаний. "
            "Используйте /add_memory, чтобы добавить первое!"
        )
        return
    
    message = "Ваши последние воспоминания:\n\n"
    for memory in memories:
        content, timestamp = memory
        date = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
        message += f"📝 {date}\n{content}\n\n"
    
    await update.message.reply_text(message)

# Обработчик команды /get_link
async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('digital_imprints.db')
    c = conn.cursor()
    
    c.execute('SELECT imprint_id FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        imprint_id = result[0]
        link = f"t.me/{BOTNAME}?start={imprint_id}"
        await update.message.reply_text(
            f"Ссылка на ваш цифровой слепок:\n{link}\n\n"
            "По этой ссылке другие пользователи смогут общаться с ботом, "
            "который будет отвечать на основе сохраненной вами информации."
        )
    else:
        await update.message.reply_text(
            "Произошла ошибка. Пожалуйста, начните заново с команды /start"
        )

# Обработчик команды /done
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'waiting_for_memory' in context.user_data:
        del context.user_data['waiting_for_memory']
    await update.message.reply_text(
        "Сохранение воспоминаний завершено. "
        "Используйте /view_memories, чтобы просмотреть сохраненное, "
        "или /add_memory, чтобы добавить что-то еще."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Доступные команды:\n\n"
        "/start - Начать работу с ботом\n"
        "/add_memory - Добавить новое воспоминание\n"
        "/view_memories - Просмотреть сохраненные воспоминания\n"
        "/get_link - Получить ссылку на ваш цифровой слепок\n"
        "/done - Завершить добавление воспоминаний\n"
        "/help - Показать это сообщение"
    )
    await update.message.reply_text(help_text)

def main():
    # Инициализация базы данных
    init_db()
    
    # Создание приложения
    application = Application.builder().token(TOKEN).build()
    
    # Добавление обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_memory", add_memory))
    application.add_handler(CommandHandler("view_memories", view_memories))
    application.add_handler(CommandHandler("get_link", get_link))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_memory))
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()