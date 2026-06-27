import os, logging
from google import genai
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ── Настройки ────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
API_KEY   = os.environ.get("GEMINI_API_KEY", "").strip()

# Инициализация официального клиента Google GenAI
client = genai.Client(api_key=API_KEY)

# ── Логика ───────────────────────────────────────────────────
async def ask_gemini(text: str) -> str:
    try:
        # Используем современную модель 3.5 Flash
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=text,
        )
        return response.text
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return f"❌ Ошибка API: {str(e)[:50]}"

# ── Бот ──────────────────────────────────────────────────────
router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer("🤖 Агент запущен на официальном Gemini API (Interactions). Пиши!")

@router.message(F.text)
async def on_text(msg: Message):
    wait = await msg.answer("⏳ Думаю...")
    response = await ask_gemini(msg.text)
    await wait.edit_text(response)

async def main():
    if not BOT_TOKEN or not API_KEY:
        logging.error("❌ BOT_TOKEN или GEMINI_API_KEY не найдены в переменных!")
        return

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🚀 Бот запущен через Google GenAI SDK")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
