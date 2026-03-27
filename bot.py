#!/usr/bin/env python3
"""
TELEGRAM БОТ С KIMI K-2.5 (MOONSHOT AI)
АДМИН-ПАНЕЛЬ | ВАЙТ-ЛИСТ | РЕШЕНИЕ ЗАДАЧ ПО ФОТО
РАЗРАБОТЧИК: Тороп Никита
"""

import asyncio
import aiohttp
import json
import os
import io
import base64
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# ===== НАСТРОЙКИ =====
# Telegram
TOKEN = os.environ.get("BOT_TOKEN", "8360813002:AAFe0ONoF76RswDIIQIKpCyL2G0vS3kpnBg")

# Moonshot AI (Kimi K-2.5)
MOONSHOT_KEY = os.environ.get("MOONSHOT_KEY", "sk-3M12jfKGQrscfyq53fprthWUc8gJX4xmXe2pUY80bRQDWOn7")

# Админ
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "fuexu")  # без @
PASSWORD = os.environ.get("PASSWORD", "admin123")

# ===== ИНИЦИАЛИЗАЦИЯ =====
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# Хранилище
authorized_users = {}
user_history = {}

# ===== ВАЙТ-ЛИСТ =====
WHITELIST_FILE = "whitelist.json"

def load_whitelist():
    if os.path.exists(WHITELIST_FILE):
        try:
            with open(WHITELIST_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
                return []
        except:
            return []
    return []

def save_whitelist(whitelist):
    with open(WHITELIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(whitelist, f, indent=4, ensure_ascii=False)

whitelist = load_whitelist()

# ===== СОСТОЯНИЯ FSM =====
class PasswordState(StatesGroup):
    waiting_for_password = State()

class AdminState(StatesGroup):
    waiting_for_add_username = State()
    waiting_for_remove_username = State()

# ===== КЛАВИАТУРЫ =====
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💬 Задать вопрос"), KeyboardButton(text="ℹ️ Помощь")],
        [KeyboardButton(text="👨‍💻 О создателе"), KeyboardButton(text="🗑️ Очистить историю")]
    ],
    resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Список вайт-листа"), KeyboardButton(text="➕ Добавить в вайт-лист")],
        [KeyboardButton(text="❌ Удалить из вайт-листа"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🔙 В главное меню")]
    ],
    resize_keyboard=True
)

# ===== ФУНКЦИЯ KIMI K-2.5 API =====
async def ask_kimi(prompt, history=None):
    """Запрос к Kimi K-2.5 (Moonshot AI)"""
    try:
        # Формируем сообщения с историей
        messages = []
        
        # Системный промпт (задаёт поведение модели)
        messages.append({
            "role": "system",
            "content": "Ты — полезный ассистент. Ты помогаешь решать задачи по школьным предметам, отвечаешь на вопросы, помогаешь с программированием. Отвечай на русском языке, подробно и понятно."
        })
        
        # Добавляем историю диалога (последние 10 сообщений)
        if history:
            for msg in history[-10:]:
                messages.append(msg)
        
        # Добавляем текущий вопрос
        messages.append({"role": "user", "content": prompt})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.moonshot.ai/v1/chat/completions",
                json={
                    "model": "kimi-k2.5",
                    "messages": messages,
                    "max_tokens": 4096,
                    "temperature": 0.7
                },
                headers={
                    "Authorization": f"Bearer {MOONSHOT_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                elif resp.status == 401:
                    return "⚠️ *Ошибка авторизации API (401)*\n\nПроверьте API ключ Moonshot. Получить ключ можно на platform.moonshot.ai"
                elif resp.status == 429:
                    return "⚠️ *Превышен лимит запросов (429)*\n\nПодождите немного и попробуйте снова."
                else:
                    error_text = await resp.text()
                    return f"⚠️ *Ошибка API* (статус {resp.status})\n\nПопробуйте позже."
                    
    except asyncio.TimeoutError:
        return "⚠️ *Превышено время ожидания*\n\nСервер API не отвечает. Попробуйте позже."
    except Exception as e:
        return f"⚠️ *Ошибка подключения:* {str(e)}"

# ===== ФУНКЦИЯ ДЛЯ ФОТО (OCR) =====
async def extract_text_from_photo(file_bytes):
    """Извлечение текста из фото (простой OCR)"""
    try:
        import pytesseract
        from PIL import Image
        
        # Настройка пути для Windows (на Railway не нужно)
        if os.name == 'nt':
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        image = Image.open(io.BytesIO(file_bytes.getvalue()))
        text = pytesseract.image_to_string(image, lang='rus+eng')
        return text.strip()
    except Exception as e:
        return None

# ===== ПРОВЕРКА АДМИНА =====
def is_admin(username):
    return username == ADMIN_USERNAME

def is_authorized(user_id, username):
    if is_admin(username):
        return True
    if username in whitelist:
        return True
    return user_id in authorized_users

# ===== КОМАНДЫ =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if is_authorized(user_id, username):
        keyboard = admin_keyboard if is_admin(username) else main_keyboard
        await message.answer(
            "🤖 *Добро пожаловать!*\n\n✅ Вы уже авторизованы.\n\n🤖 Модель: Kimi K-2.5 (Moonshot AI)",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return
    
    await message.answer(
        "🤖 *Добро пожаловать!*\n\n🤖 Модель: Kimi K-2.5\n\n🔐 Введите /login для входа.",
        parse_mode="Markdown"
    )

@dp.message(Command("login"))
async def cmd_login(message: types.Message, state: FSMContext):
    username = message.from_user.username
    user_id = message.from_user.id
    
    if is_authorized(user_id, username):
        keyboard = admin_keyboard if is_admin(username) else main_keyboard
        await message.answer("✅ Вы уже авторизованы!", reply_markup=keyboard)
        return
    
    await state.set_state(PasswordState.waiting_for_password)
    await message.answer("🔐 *Введите пароль:*", parse_mode="Markdown")

@dp.message(PasswordState.waiting_for_password)
async def check_password(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if message.text == PASSWORD:
        authorized_users[user_id] = {
            "authorized_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "username": username or message.from_user.first_name
        }
        if user_id not in user_history:
            user_history[user_id] = []
        
        await state.clear()
        keyboard = admin_keyboard if is_admin(username) else main_keyboard
        
        await message.answer(
            "✅ *Доступ разрешен!*\n\n🤖 Модель: Kimi K-2.5 (256K контекста)\n\nТеперь вы можете использовать бота.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await message.answer("❌ *Неверный пароль!*", parse_mode="Markdown")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    username = message.from_user.username
    
    if not is_admin(username):
        await message.answer("⛔ *Нет доступа к админ-панели.*", parse_mode="Markdown")
        return
    
    await message.answer(
        "🛡️ *АДМИН-ПАНЕЛЬ*\n\n"
        "/admin add @username — добавить в вайт-лист\n"
        "/admin remove @username — удалить\n"
        "/admin list — показать список\n"
        "/admin stats — статистика\n"
        "/admin exit — выйти",
        parse_mode="Markdown",
        reply_markup=admin_keyboard
    )

@dp.message(Command("admin", commands=["admin"]))
async def admin_commands(message: types.Message):
    username = message.from_user.username
    if not is_admin(username):
        return
    
    args = message.text.split()
    if len(args) == 1:
        await cmd_admin(message)
        return
    
    command = args[1].lower()
    
    if command == "add" and len(args) >= 3:
        target = args[2].replace("@", "")
        if target in whitelist:
            await message.answer(f"⚠️ @{target} уже в вайт-листе.")
            return
        whitelist.append(target)
        save_whitelist(whitelist)
        await message.answer(f"✅ @{target} добавлен в вайт-лист!")
    
    elif command == "remove" and len(args) >= 3:
        target = args[2].replace("@", "")
        if target not in whitelist:
            await message.answer(f"⚠️ @{target} не найден.")
            return
        whitelist.remove(target)
        save_whitelist(whitelist)
        await message.answer(f"✅ @{target} удален из вайт-листа!")
    
    elif command == "list":
        if not whitelist:
            await message.answer("📋 Вайт-лист пуст.")
        else:
            text = "📋 *Вайт-лист:*\n\n" + "\n".join([f"• @{u}" for u in whitelist])
            await message.answer(text, parse_mode="Markdown")
    
    elif command == "stats":
        await message.answer(
            f"📊 *Статистика*\n\n"
            f"👥 Вайт-лист: {len(whitelist)}\n"
            f"🔐 По паролю: {len(authorized_users)}\n"
            f"💬 Диалогов: {len([h for h in user_history.values() if h])}\n\n"
            f"🤖 Модель: Kimi K-2.5\n"
            f"📚 Контекст: 256K токенов",
            parse_mode="Markdown"
        )
    
    elif command == "exit":
        await message.answer("🔙 Выход из админ-панели", reply_markup=main_keyboard)

# ===== АДМИН-КНОПКИ =====
@dp.message(lambda msg: msg.text == "📋 Список вайт-листа")
async def admin_list_btn(message: types.Message):
    if not is_admin(message.from_user.username):
        return
    if not whitelist:
        await message.answer("📋 Вайт-лист пуст.")
    else:
        text = "📋 *Вайт-лист:*\n\n" + "\n".join([f"• @{u}" for u in whitelist])
        await message.answer(text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "➕ Добавить в вайт-лист")
async def admin_add_btn(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.username):
        return
    await state.set_state(AdminState.waiting_for_add_username)
    await message.answer("✍️ Введите username пользователя для добавления:")

@dp.message(AdminState.waiting_for_add_username)
async def admin_add_user(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.username):
        await state.clear()
        return
    target = message.text.strip().replace("@", "")
    if target in whitelist:
        await message.answer(f"⚠️ @{target} уже в списке.")
    else:
        whitelist.append(target)
        save_whitelist(whitelist)
        await message.answer(f"✅ @{target} добавлен в вайт-лист!")
    await state.clear()

@dp.message(lambda msg: msg.text == "❌ Удалить из вайт-листа")
async def admin_remove_btn(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.username):
        return
    await state.set_state(AdminState.waiting_for_remove_username)
    await message.answer("✍️ Введите username пользователя для удаления:")

@dp.message(AdminState.waiting_for_remove_username)
async def admin_remove_user(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.username):
        await state.clear()
        return
    target = message.text.strip().replace("@", "")
    if target not in whitelist:
        await message.answer(f"⚠️ @{target} не найден.")
    else:
        whitelist.remove(target)
        save_whitelist(whitelist)
        await message.answer(f"✅ @{target} удален из вайт-листа!")
    await state.clear()

@dp.message(lambda msg: msg.text == "📊 Статистика")
async def admin_stats_btn(message: types.Message):
    if not is_admin(message.from_user.username):
        return
    await message.answer(
        f"📊 *Статистика*\n\n"
        f"👥 Вайт-лист: {len(whitelist)}\n"
        f"🔐 По паролю: {len(authorized_users)}\n\n"
        f"🤖 Модель: Kimi K-2.5\n"
        f"📚 Контекст: 256K токенов",
        parse_mode="Markdown"
    )

@dp.message(lambda msg: msg.text == "🔙 В главное меню")
async def admin_back_btn(message: types.Message):
    if not is_admin(message.from_user.username):
        return
    await message.answer("🔙 Возврат в главное меню", reply_markup=main_keyboard)

# ===== ОСНОВНЫЕ КОМАНДЫ =====
@dp.message(Command("ask"))
async def cmd_ask(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if not is_authorized(user_id, username):
        await message.answer("🔐 Введите /login для авторизации.")
        return
    
    question = message.text.replace("/ask", "").strip()
    if not question:
        await message.answer("❓ *Как использовать:*\n/ask [ваш вопрос]\n\nПример: /ask Какое население Москвы?", parse_mode="Markdown")
        return
    
    await bot.send_chat_action(message.chat.id, "typing")
    history = user_history.get(user_id, [])
    response = await ask_kimi(question, history)
    
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].append({"role": "user", "content": question})
    user_history[user_id].append({"role": "assistant", "content": response})
    if len(user_history[user_id]) > 20:
        user_history[user_id] = user_history[user_id][-20:]
    
    await message.answer(f"🤖 *Kimi K-2.5:*\n\n{response}", parse_mode="Markdown")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_history:
        user_history[user_id] = []
    await message.answer("🗑️ История диалога очищена!")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📚 *Команды*\n\n"
        "/login — вход по паролю\n"
        "/ask [вопрос] — вопрос Kimi K-2.5\n"
        "/clear — очистить историю\n"
        "/info — о боте\n"
        "/help — справка\n\n"
        "📸 *Фото:* отправьте фото задачи — бот распознает текст и решит её!\n\n"
        "🤖 *Модель:* Kimi K-2.5 (256K контекста)",
        parse_mode="Markdown"
    )

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    await message.answer(
        "🤖 *Kimi K-2.5 Telegram Bot*\n\n"
        "👨‍💻 *Создатель:* Тороп Никита\n"
        "🤖 *Модель:* Kimi K-2.5 (Moonshot AI)\n"
        "📚 *Контекст:* 256K токенов\n"
        "🌐 *API:* platform.moonshot.ai\n"
        "🔧 *Версия:* 4.0\n\n"
        "📌 *Особенности:*\n"
        "• Решение задач по фото\n"
        "• Админ-панель с вайт-листом\n"
        "• История диалога\n"
        "• Бесплатный доступ",
        parse_mode="Markdown"
    )

# ===== КНОПКИ =====
@dp.message(lambda msg: msg.text == "💬 Задать вопрос")
async def btn_ask(message: types.Message):
    await message.answer("✍️ Напишите вопрос или используйте /ask")

@dp.message(lambda msg: msg.text == "ℹ️ Помощь")
async def btn_help(message: types.Message):
    await cmd_help(message)

@dp.message(lambda msg: msg.text == "👨‍💻 О создателе")
async def btn_creator(message: types.Message):
    await message.answer(
        "👨‍💻 *Тороп Никита*\n\n"
        "Разработчик Telegram ботов\n"
        "Специализация: Python, aiogram, API нейросетей\n\n"
        "🤖 Бот использует модель Kimi K-2.5\n"
        "📱 Версия: 4.0",
        parse_mode="Markdown"
    )

@dp.message(lambda msg: msg.text == "🗑️ Очистить историю")
async def btn_clear(message: types.Message):
    await cmd_clear(message)

# ===== ОБРАБОТЧИК ФОТО =====

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if not is_authorized(user_id, username):
        await message.answer("🔐 Сначала авторизуйтесь: /login")
        return
    
    # ... остальной код обработки фото ...
    await bot.send_chat_action(message.chat.id, "typing")
    
    processing_msg = await message.answer("📸 Обрабатываю фото... Распознаю текст...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        
        text = await extract_text_from_photo(file_bytes)
        
        if not text or len(text) < 5:
            await processing_msg.edit_text(
                "❌ *Не удалось распознать текст на фото.*\n\n"
                "💡 *Советы:*\n"
                "• Сфотографируйте задачу чётче\n"
                "• Обеспечьте хорошее освещение\n"
                "• Текст должен быть разборчивым",
                parse_mode="Markdown"
            )
            return
        
        preview = text[:300] + "..." if len(text) > 300 else text
        await processing_msg.edit_text(
            f"📝 *Распознанный текст:*\n\n{preview}\n\n🤔 Решаю задачу с помощью Kimi K-2.5...",
            parse_mode="Markdown"
        )
        
        prompt = f"""Реши следующую задачу. Это задача по школьному предмету (математика, физика, химия, русский язык и т.д.).
Определи предмет и напиши:
1. Краткое условие задачи
2. Пошаговое решение с объяснением
3. Ответ

Задача:
{text}"""
        
        history = user_history.get(user_id, [])
        response = await ask_kimi(prompt, history)
        
        if user_id not in user_history:
            user_history[user_id] = []
        user_history[user_id].append({"role": "user", "content": f"[ФОТО ЗАДАЧИ] {text[:200]}..."})
        user_history[user_id].append({"role": "assistant", "content": response})
        
        await processing_msg.edit_text(
            f"📚 *Решение задачи (Kimi K-2.5):*\n\n{response}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await processing_msg.edit_text(f"⚠️ *Ошибка:* {str(e)}", parse_mode="Markdown")

# ===== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ =====
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if message.text.startswith("/"):
        return
    
    if message.text in ["💬 Задать вопрос", "ℹ️ Помощь", "👨‍💻 О создателе", "🗑️ Очистить историю",
                       "📋 Список вайт-листа", "➕ Добавить в вайт-лист", "❌ Удалить из вайт-листа",
                       "📊 Статистика", "🔙 В главное меню"]:
        return
    
    if not is_authorized(user_id, username):
        await message.answer("🔐 Введите /login для авторизации.")
        return
    
    await bot.send_chat_action(message.chat.id, "typing")
    history = user_history.get(user_id, [])
    response = await ask_kimi(message.text, history)
    
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].append({"role": "user", "content": message.text})
    user_history[user_id].append({"role": "assistant", "content": response})
    if len(user_history[user_id]) > 20:
        user_history[user_id] = user_history[user_id][-20:]
    
    await message.answer(f"🤖 *Kimi K-2.5:*\n\n{response}", parse_mode="Markdown")

# ===== ЗАПУСК =====
async def main():
    print("=" * 50)
    print("🤖 TELEGRAM БОТ ЗАПУЩЕН")
    print("=" * 50)
    print(f"👨‍💻 Админ: @{ADMIN_USERNAME}")
    print(f"🔐 Пароль: {PASSWORD}")
    print(f"📋 Вайт-лист: {len(whitelist)} пользователей")
    print(f"🤖 Модель: Kimi K-2.5 (Moonshot AI)")
    print(f"📚 Контекст: 256K токенов")
    print("=" * 50)
    print("✅ Бот готов к работе!")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
