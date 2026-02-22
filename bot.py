import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [1925179708]  # <-- ВСТАВЬ СВОЙ TELEGRAM ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= DATABASE =================

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    number TEXT,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('price', '50₽')")
conn.commit()

# ================= FSM =================

class RentState(StatesGroup):
    waiting_number = State()

# ================= КНОПКИ =================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Арендовать", callback_data="rent")],
        [InlineKeyboardButton(text="💰 Прайс", callback_data="price")],
        [InlineKeyboardButton(text="📊 Очередь", callback_data="queue")],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")]
    ])

def status_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Встал", callback_data="done"),
            InlineKeyboardButton(text="🔁 Повтор", callback_data="repeat")
        ]
    ])

# ================= START =================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Добро пожаловать!\n\nВыберите действие:",
        reply_markup=main_menu()
    )

# ================= АРЕНДА =================

@dp.callback_query(F.data == "rent")
async def rent(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📩 Введите номер в формате +79999999999")
    await state.set_state(RentState.waiting_number)
    await callback.answer()

@dp.message(RentState.waiting_number)
async def get_number(message: Message, state: FSMContext):
    number = message.text.strip()

    if not number.startswith("+") or not number[1:].isdigit():
        await message.answer("❌ Неверный формат номера.")
        return

    cursor.execute(
        "INSERT INTO queue (user_id, username, number, status) VALUES (?, ?, ?, ?)",
        (message.from_user.id, message.from_user.username, number, "waiting")
    )
    conn.commit()

    for admin in ADMIN_IDS:
        await bot.send_message(
            admin,
            f"📥 Новый номер\n\n👤 @{message.from_user.username}\n🆔 {message.from_user.id}\n📱 {number}"
        )

    await message.answer("⏳ Номер добавлен в очередь.")
    await state.clear()

# ================= ПРАЙС =================

@dp.callback_query(F.data == "price")
async def price(callback: CallbackQuery):
    cursor.execute("SELECT value FROM settings WHERE key='price'")
    price = cursor.fetchone()[0]
    await callback.message.answer(f"💰 Текущий прайс: {price}")
    await callback.answer()

# ================= ОЧЕРЕДЬ =================

@dp.callback_query(F.data == "queue")
async def show_queue(callback: CallbackQuery):
    cursor.execute("SELECT COUNT(*) FROM queue WHERE status='waiting'")
    count = cursor.fetchone()[0]
    await callback.message.answer(f"📊 В очереди: {count} номеров")
    await callback.answer()

# ================= ПОДДЕРЖКА =================

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.message.answer("✍️ Напишите сообщение для поддержки.")
    await callback.answer()

@dp.message()
async def support_message(message: Message):
    if message.from_user.id in ADMIN_IDS:
        return

    for admin in ADMIN_IDS:
        await bot.send_message(
            admin,
            f"🛠 Поддержка от @{message.from_user.username}:\n\n{message.text}"
        )

# ================= ОТПРАВКА КОДА =================

@dp.message(Command("code"))
async def send_code(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        _, user_id, code = message.text.split(maxsplit=2)

        await bot.send_message(
            int(user_id),
            f"🔐 Ваш код:\n\n{code}",
            reply_markup=status_kb()
        )

        await message.answer("✅ Код отправлен.")
    except:
        await message.answer("Используй: /code user_id код")

# ================= ВСТАЛ / ПОВТОР =================

@dp.callback_query(F.data == "done")
async def done(callback: CallbackQuery):
    await callback.message.edit_text(
        "✅ Отлично!\n\nНе забудьте добавить номер в отчёт и указать username."
    )
    await callback.answer()

@dp.callback_query(F.data == "repeat")
async def repeat(callback: CallbackQuery):
    for admin in ADMIN_IDS:
        await bot.send_message(
            admin,
            f"🔁 Повтор кода\n\n👤 @{callback.from_user.username}\n🆔 {callback.from_user.id}"
        )
    await callback.answer("Администратор уведомлён")

# ================= АДМИН КОМАНДЫ =================

@dp.message(Command("setprice"))
async def set_price(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        _, new_price = message.text.split(maxsplit=1)
        cursor.execute("UPDATE settings SET value=? WHERE key='price'", (new_price,))
        conn.commit()
        await message.answer("💰 Прайс обновлён.")
    except:
        await message.answer("Используй: /setprice 60₽")

@dp.message(Command("clearqueue"))
async def clear_queue(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    cursor.execute("DELETE FROM queue")
    conn.commit()
    await message.answer("🗑 Очередь очищена.")

# ================= ЗАПУСК =================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
