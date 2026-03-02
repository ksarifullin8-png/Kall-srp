import sqlite3
import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import InlineKeyboardButton, Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8455546096:AAHNDMnlpoHPHgQ62k5M_Yno2tWj7QNDxcU"
ADMIN_GROUP_ID = -1003882599068
INITIAL_ADMIN_ID = 7546928092

# ========== СОСТОЯНИЯ ==========
class BroadcastStates(StatesGroup):
    waiting_for_message = State()

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logging.basicConfig(level=logging.INFO)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        is_blocked INTEGER DEFAULT 0
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        added_by INTEGER
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message_type TEXT,
        caption TEXT,
        file_id TEXT,
        forwarded_message_id INTEGER
    )''')
    
    conn.commit()
    conn.close()
    print("✅ База данных создана")

# ========== ДОБАВЛЕНИЕ ПЕРВОГО АДМИНА ==========
def add_initial_admin():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admins")
    count = cursor.fetchone()[0]
    
    if count == 0:
        cursor.execute("INSERT INTO admins (user_id, added_by) VALUES (?, ?)",
                      (INITIAL_ADMIN_ID, INITIAL_ADMIN_ID))
        print(f"✅ Первый администратор добавлен: {INITIAL_ADMIN_ID}")
    conn.commit()
    conn.close()

# ========== ФУНКЦИИ ==========
def add_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, first_name, last_name, is_blocked) VALUES (?, ?, ?, ?, 0)",
                      (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone() is not None
    conn.close()
    return result

def is_blocked(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def block_user(user_id, admin_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def unblock_user(user_id, admin_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_admin(user_id, added_by):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO admins (user_id, added_by) VALUES (?, ?)",
                  (user_id, added_by))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def save_message(user_id, message_type, caption, file_id, forwarded_message_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (user_id, message_type, caption, file_id, forwarded_message_id) VALUES (?, ?, ?, ?, ?)",
                  (user_id, message_type, caption, file_id, forwarded_message_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_blocked = 0")
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

# ========== КОМАНДЫ ==========

# КОМАНДА /start - показывает все команды
@dp.message(Command("start"))
async def start_command(message: Message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    if is_admin(user.id):
        await message.reply(
            "👋 Привет админ!\n\n"
            "📋 Доступные команды:\n"
            "/start - показать это сообщение\n"
            "/admin - панель администратора\n"
            "/addadmin (id) - добавить админа\n"
            "/removeadmin (id) - удалить админа\n"
            "/admins - список админов\n"
            "/block (id) - заблокировать пользователя\n"
            "/unblock (id) - разблокировать\n"
            "/send (id) (текст) - ответить пользователю"
        )
    else:
        await message.reply(
            "👋 Привет! Я анонимный бот.\n"
            "Твои сообщения будут переданы администраторам анонимно.\n"
            "Ты можешь отправлять текст, фото, видео и любые другие файлы!"
        )

# КОМАНДА /addadmin - добавить админа
@dp.message(Command("addadmin"))
async def add_admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У вас нет прав.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Использование: /addadmin (id)")
        return
    
    try:
        user_id = int(args[1])
        if is_admin(user_id):
            await message.reply("❌ Этот пользователь уже админ")
        else:
            add_admin(user_id, message.from_user.id)
            await message.reply(f"✅ Пользователь {user_id} добавлен в администраторы")
    except:
        await message.reply("❌ Неправильный ID")

# КОМАНДА /removeadmin - удалить админа
@dp.message(Command("removeadmin"))
async def remove_admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У вас нет прав.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Использование: /removeadmin (id)")
        return
    
    try:
        user_id = int(args[1])
        if user_id == INITIAL_ADMIN_ID:
            await message.reply("❌ Нельзя удалить первого админа")
        elif not is_admin(user_id):
            await message.reply("❌ Этот пользователь не админ")
        else:
            remove_admin(user_id)
            await message.reply(f"✅ Администратор {user_id} удален")
    except:
        await message.reply("❌ Неправильный ID")

# КОМАНДА /admins - список админов
@dp.message(Command("admins"))
async def admins_list_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У вас нет прав.")
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    admins = cursor.fetchall()
    conn.close()
    
    text = "📋 Список администраторов:\n"
    for admin_id in admins:
        text += f"• {admin_id[0]}\n"
    
    await message.reply(text)

# КОМАНДА /block - заблокировать
@dp.message(Command("block"))
async def block_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У вас нет прав.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Использование: /block (id)")
        return
    
    try:
        user_id = int(args[1])
        block_user(user_id, message.from_user.id)
        await message.reply(f"✅ Пользователь {user_id} заблокирован")
    except:
        await message.reply("❌ Неправильный ID")

# КОМАНДА /unblock - разблокировать
@dp.message(Command("unblock"))
async def unblock_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У вас нет прав.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Использование: /unblock (id)")
        return
    
    try:
        user_id = int(args[1])
        unblock_user(user_id, message.from_user.id)
        await message.reply(f"✅ Пользователь {user_id} разблокирован")
    except:
        await message.reply("❌ Неправильный ID")

# КОМАНДА /send - ответить пользователю
@dp.message(Command("send"))
async def send_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У вас нет прав.")
        return
    
    if message.chat.id != ADMIN_GROUP_ID:
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("❌ Использование: /send (id) (текст)")
        return
    
    try:
        user_id = int(parts[1])
        text = parts[2]
        
        if is_blocked(user_id):
            await message.reply("❌ Пользователь заблокирован")
            return
        
        await bot.send_message(user_id, f"📨 Сообщение от администрации:\n\n{text}")
        await message.reply(f"✅ Отправлено пользователю {user_id}")
    except:
        await message.reply("❌ Ошибка")

# КОМАНДА /admin - старая панель (оставил для совместимости)
@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У вас нет прав.")
        return
    
    await message.reply(
        "🔐 Используй команды:\n"
        "/addadmin (id)\n"
        "/removeadmin (id)\n"
        "/admins\n"
        "/block (id)\n"
        "/unblock (id)\n"
        "/send (id) (текст)"
    )

# ========== ФУНКЦИЯ ОТПРАВКИ В ГРУППУ ==========
async def forward_to_admins(message: Message, user, content_type, content, caption=None):
    user_info = (
        f"📨 Новое сообщение от пользователя:\n"
        f"👤 Имя: {user.first_name} {user.last_name or ''}\n"
        f"🆔 ID: {user.id}\n"
        f"📱 Юзернейм: @{user.username if user.username else 'отсутствует'}"
    )
    
    info_message = await bot.send_message(
        ADMIN_GROUP_ID,
        user_info,
        reply_markup=get_user_info_keyboard(user.id)
    )
    
    try:
        if content_type == "text":
            sent_message = await bot.send_message(
                ADMIN_GROUP_ID,
                f"<code>{content}</code>",
                parse_mode="HTML"
            )
            
        elif content_type == "photo":
            await bot.send_photo(ADMIN_GROUP_ID, content)
            if caption:
                sent_message = await bot.send_message(
                    ADMIN_GROUP_ID,
                    f"<code>{caption}</code>",
                    parse_mode="HTML"
                )
            else:
                sent_message = info_message
                
        elif content_type == "video":
            await bot.send_video(ADMIN_GROUP_ID, content)
            if caption:
                sent_message = await bot.send_message(
                    ADMIN_GROUP_ID,
                    f"<code>{caption}</code>",
                    parse_mode="HTML"
                )
            else:
                sent_message = info_message
                
        elif content_type == "document":
            await bot.send_document(ADMIN_GROUP_ID, content)
            if caption:
                sent_message = await bot.send_message(
                    ADMIN_GROUP_ID,
                    f"<code>{caption}</code>",
                    parse_mode="HTML"
                )
            else:
                sent_message = info_message
                
        elif content_type == "audio":
            await bot.send_audio(ADMIN_GROUP_ID, content)
            if caption:
                sent_message = await bot.send_message(
                    ADMIN_GROUP_ID,
                    f"<code>{caption}</code>",
                    parse_mode="HTML"
                )
            else:
                sent_message = info_message
                
        elif content_type == "voice":
            await bot.send_voice(ADMIN_GROUP_ID, content)
            if caption:
                sent_message = await bot.send_message(
                    ADMIN_GROUP_ID,
                    f"<code>{caption}</code>",
                    parse_mode="HTML"
                )
            else:
                sent_message = info_message
                
        elif content_type == "sticker":
            sent_message = await bot.send_sticker(ADMIN_GROUP_ID, content)
            
        else:
            sent_message = await bot.copy_message(
                chat_id=ADMIN_GROUP_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
        
        save_message(user.id, content_type, caption or "", content or "", 
                    sent_message.message_id if 'sent_message' in locals() else info_message.message_id)
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        raise e

# ========== КЛАВИАТУРЫ ==========
def get_user_info_keyboard(user_id):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🔒 Заблокировать", callback_data=f"block_{user_id}"),
        InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"unblock_{user_id}")
    )
    return keyboard.as_markup()

# ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========

# Текстовые сообщения от пользователей
@dp.message(F.text)
async def handle_text_message(message: Message):
    user = message.from_user
    
    if message.chat.id == ADMIN_GROUP_ID or message.text.startswith('/'):
        return
    
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    if is_blocked(user.id):
        await message.reply("❌ Вы заблокированы")
        return
    
    if is_admin(user.id):
        return
    
    try:
        await forward_to_admins(message, user, "text", message.text)
        await message.reply("✅ Сообщение доставлено админам!")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.reply("❌ Ошибка")

# Фото
@dp.message(F.photo)
async def handle_photo_message(message: Message):
    user = message.from_user
    
    if message.chat.id == ADMIN_GROUP_ID:
        return
    
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    if is_blocked(user.id):
        await message.reply("❌ Вы заблокированы")
        return
    
    if is_admin(user.id):
        return
    
    try:
        await forward_to_admins(message, user, "photo", message.photo[-1].file_id, message.caption)
        await message.reply("✅ Фото доставлено админам!")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.reply("❌ Ошибка")

# Видео
@dp.message(F.video)
async def handle_video_message(message: Message):
    user = message.from_user
    
    if message.chat.id == ADMIN_GROUP_ID:
        return
    
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    if is_blocked(user.id):
        await message.reply("❌ Вы заблокированы")
        return
    
    if is_admin(user.id):
        return
    
    try:
        await forward_to_admins(message, user, "video", message.video.file_id, message.caption)
        await message.reply("✅ Видео доставлено админам!")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.reply("❌ Ошибка")

# Документы
@dp.message(F.document)
async def handle_document_message(message: Message):
    user = message.from_user
    
    if message.chat.id == ADMIN_GROUP_ID:
        return
    
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    if is_blocked(user.id):
        await message.reply("❌ Вы заблокированы")
        return
    
    if is_admin(user.id):
        return
    
    try:
        await forward_to_admins(message, user, "document", message.document.file_id, message.caption)
        await message.reply("✅ Документ доставлен админам!")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.reply("❌ Ошибка")

# Аудио
@dp.message(F.audio)
async def handle_audio_message(message: Message):
    user = message.from_user
    
    if message.chat.id == ADMIN_GROUP_ID:
        return
    
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    if is_blocked(user.id):
        await message.reply("❌ Вы заблокированы")
        return
    
    if is_admin(user.id):
        return
    
    try:
        await forward_to_admins(message, user, "audio", message.audio.file_id, message.caption)
        await message.reply("✅ Аудио доставлено админам!")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.reply("❌ Ошибка")

# Голосовые
@dp.message(F.voice)
async def handle_voice_message(message: Message):
    user = message.from_user
    
    if message.chat.id == ADMIN_GROUP_ID:
        return
    
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    if is_blocked(user.id):
        await message.reply("❌ Вы заблокированы")
        return
    
    if is_admin(user.id):
        return
    
    try:
        await forward_to_admins(message, user, "voice", message.voice.file_id, message.caption)
        await message.reply("✅ Голосовое доставлено админам!")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.reply("❌ Ошибка")

# Стикеры
@dp.message(F.sticker)
async def handle_sticker_message(message: Message):
    user = message.from_user
    
    if message.chat.id == ADMIN_GROUP_ID:
        return
    
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    if is_blocked(user.id):
        await message.reply("❌ Вы заблокированы")
        return
    
    if is_admin(user.id):
        return
    
    try:
        await forward_to_admins(message, user, "sticker", message.sticker.file_id)
        await message.reply("✅ Стикер доставлен админам!")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.reply("❌ Ошибка")

# ========== КОЛЛБЭКИ ==========
@dp.callback_query(F.data.startswith("block_"))
async def block_user_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return
    
    user_id = int(callback.data.replace("block_", ""))
    block_user(user_id, callback.from_user.id)
    await callback.answer("✅ Заблокирован")
    await callback.message.edit_reply_markup(reply_markup=get_user_info_keyboard(user_id))

@dp.callback_query(F.data.startswith("unblock_"))
async def unblock_user_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return
    
    user_id = int(callback.data.replace("unblock_", ""))
    unblock_user(user_id, callback.from_user.id)
    await callback.answer("✅ Разблокирован")
    await callback.message.edit_reply_markup(reply_markup=get_user_info_keyboard(user_id))

# ========== ЗАПУСК ==========
async def main():
    print("🚀 Запуск бота...")
    init_db()
    add_initial_admin()
    
    try:
        chat = await bot.get_chat(ADMIN_GROUP_ID)
        print(f"✅ Группа: {chat.title}")
    except:
        print("❌ Бот не в группе!")
    
    print("✅ Бот работает!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())