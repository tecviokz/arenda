from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio

TOKEN = "8510821400:AAH18mLbKAEMTavsa_VpE3-QUDU-p7lKCGI"
ADMINS = [1925179708]  # твой ID

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ======= ПРОСТАЯ БАЗА =======
users = set()
active_numbers = {}  # {user_id: phone}
pending_codes = {}   # {user_id: last_code}

# ======= FSM =======
class SubmitNumber(StatesGroup):
    waiting_for_number = State()

class AdminSendCode(StatesGroup):
    waiting_for_code = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

# ======= КНОПКИ =======
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Сдать номер", callback_data="submit_number")],
        [InlineKeyboardButton(text="🛟 Поддержка", callback_data="support")]
    ])

def code_buttons():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Встал", callback_data="done"),
         InlineKeyboardButton(text="🔁 Повтор", callback_data="repeat")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton(text="🧹 Очистить активные", callback_data="clear")]
    ])

# ======= СТАРТ =======
@dp.message(Command("start"))
async def start(message: Message):
    users.add(message.from_user.id)
    await message.answer("👋 Добро пожаловать!\nВыберите действие:", reply_markup=main_menu())

# ======= СДАТЬ НОМЕР =======
@dp.callback_query(F.data=="submit_number")
async def submit_number(call: CallbackQuery, state: FSMContext):
    if call.from_user.id in active_numbers:
        await call.message.answer("❗ У вас уже есть активный номер.")
        return
    await call.message.answer("📲 Отправьте номер в формате +7700...")
    await state.set_state(SubmitNumber.waiting_for_number)

@dp.message(SubmitNumber.waiting_for_number)
async def process_number(message: Message, state: FSMContext):
    phone = message.text.strip()
    active_numbers[message.from_user.id] = phone
    users.add(message.from_user.id)

    text = f"📥 Новый номер\n\n📱 {phone}\n👤 @{message.from_user.username}\n🆔 {message.from_user.id}"
    for admin in ADMINS:
        await bot.send_message(admin, text)

    await message.answer("✅ Номер отправлен админу.")
    await state.clear()

# ======= ОТПРАВКА КОДА АДМИНОМ =======
@dp.message(Command("code"))
async def send_code_command(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    try:
        user_id = int(message.text.split()[1])
    except:
        await message.answer("❗ Используй: /code USER_ID")
        return
    if user_id not in active_numbers:
        await message.answer("❗ У пользователя нет активного номера.")
        return
    await state.update_data(target_user=user_id)
    await message.answer("🔑 Введите код:")
    await state.set_state(AdminSendCode.waiting_for_code)

@dp.message(AdminSendCode.waiting_for_code)
async def process_code(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    data = await state.get_data()
    user_id = data.get("target_user")
    code = message.text.strip()
    pending_codes[user_id] = code
    await bot.send_message(user_id, f"🔑 Ваш код:\n{code}", reply_markup=code_buttons())
    await message.answer("✅ Код отправлен пользователю.")
    await state.clear()

# ======= КНОПКИ ПОЛЬЗОВАТЕЛЯ =======
@dp.callback_query(F.data=="repeat")
async def repeat_code(call: CallbackQuery):
    user_id = call.from_user.id
    if user_id not in active_numbers:
        return
    phone = active_numbers[user_id]
    text = f"🔁 Пользователь просит повтор\n📱 {phone}\n👤 @{call.from_user.username}\n🆔 {user_id}"
    for admin in ADMINS:
        await bot.send_message(admin, text)
    await call.answer("Запрос отправлен админу.")

@dp.callback_query(F.data=="done")
async def done(call: CallbackQuery):
    user_id = call.from_user.id
    if user_id in active_numbers:
        del active_numbers[user_id]
    await call.message.edit_text("✅ Отлично!\nПожалуйста, не забудьте:\n— Добавить номер в отчёт\n— Указать свой username")

# ======= АДМИН ПАНЕЛЬ =======
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("👑 Админ панель:", reply_markup=admin_menu())

@dp.callback_query(F.data=="stats")
async def stats(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return
    await call.message.answer(f"📊 Статистика\n👥 Пользователей: {len(users)}\n📲 Активных номеров: {len(active_numbers)}")

@dp.callback_query(F.data=="clear")
async def clear_active(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return
    active_numbers.clear()
    await call.message.answer("🧹 Активные номера очищены.")

# ======= РАССЫЛКА =======
@dp.callback_query(F.data=="broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        return
    await call.message.answer("📨 Отправьте сообщение для рассылки:")
    await state.set_state(BroadcastState.waiting_for_message)

@dp.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    text = message.text
    for user in users:
        try:
            await bot.send_message(user, text)
        except:
            pass
    await message.answer("✅ Рассылка завершена.")
    await state.clear()

# ======= ПОДДЕРЖКА =======
@dp.callback_query(F.data=="support")
async def support(call: CallbackQuery):
    await call.message.answer("✍️ Напишите сообщение для поддержки. Оно придёт админам.")
    # Пользователь просто пишет, админу отправляется через reply вручную

# ======= ЗАПУСК =======
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())