import asyncio, logging, os
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(level=logging.INFO)

# ── Настройки ────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OR_KEY    = os.environ.get("OPENROUTER_API_KEY", "").strip()

# Используем самую стабильную бесплатную модель
MODEL = "google/gemini-2.0-flash-lite-preview-02-05:free"

# ── Логика ───────────────────────────────────────────────────
async def ask_llm(text: str) -> str:
    try:
        client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1")
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": text}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Ошибка (проверь ключ): {str(e)[:50]}"

# ── Бот ──────────────────────────────────────────────────────
router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer("🤖 Бот готов. Пиши вопрос.")

@router.message(F.text)
async def on_text(msg: Message):
    wait = await msg.answer("⏳...")
    response = await ask_llm(msg.text)
    await wait.edit_text(response)

async def main():
    bot = Bot(token=BOT_TOKEN, session=AiohttpSession(timeout=60), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🚀 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
