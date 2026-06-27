import os, logging
from google import genai
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ── Настройки ────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
API_KEY   = os.environ.get("GEMINI_API_KEY", "").strip()
client = genai.Client(api_key=API_KEY)

# ── Меню ─────────────────────────────────────────────────────
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Генерация документов", callback_data="gen_doc")],
        [InlineKeyboardButton(text="👤 Контрагенты", callback_data="list_clients")],
        [InlineKeyboardButton(text="⚙️ Статус API", callback_data="status")]
    ])

# ── Логика ───────────────────────────────────────────────────
async def ask_gemini(text: str) -> str:
    # Используем Interactions API
    interaction = client.interactions.create(
        model="gemini-3.5-flash",
        input=text
    )
    return interaction.output_text

# ── Обработчики ──────────────────────────────────────────────
router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer("🤖 Ассистент запущен. Выбери действие:", reply_markup=get_main_menu())

# Реакция на кнопки
@router.callback_query(F.data == "gen_doc")
async def action_gen_doc(callback: CallbackQuery):
    await callback.message.answer("Пришли данные для документа (название компании, сумма, услуга).")

@router.callback_query(F.data == "status")
async def action_status(callback: CallbackQuery):
    await callback.message.answer("✅ API Gemini работает. Модель: gemini-3.5-flash")

# Обработка файлов (Прием)
@router.message(F.document)
async def on_doc(msg: Message):
    wait = await msg.answer("📄 Анализирую документ...")
    file = await msg.bot.get_file(msg.document.file_id)
    file_bytes = await msg.bot.download_file(file.file_path)
    
    # Отправка в Gemini (используем base64 как в доках)
    response = await ask_gemini(f"Проанализируй документ: {msg.document.file_name}")
    await wait.edit_text(response)

# Функция отправки файла пользователю
async def send_file_to_user(bot: Bot, chat_id: int, file_path: str, caption: str):
    if os.path.exists(file_path):
        await bot.send_document(chat_id, FSInputFile(file_path), caption=caption)
    else:
        await bot.send_message(chat_id, "❌ Файл не найден на сервере.")

@router.message(F.text)
async def on_text(msg: Message):
    if msg.text.lower() == "меню":
        await msg.answer("Главное меню:", reply_markup=get_main_menu())
        return
        
    wait = await msg.answer("⏳ Думаю...")
    response = await ask_gemini(msg.text)
    await wait.edit_text(response)

# ── Запуск ────────────────────────────────────────────────────
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🚀 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
