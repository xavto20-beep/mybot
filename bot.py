import asyncio, logging, os, aiosqlite, json
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(level=logging.INFO)

# ── Настройки ────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OR_KEY    = os.environ.get("OPENROUTER_API_KEY", "").strip()
DB_PATH   = "agent.db"

# ── Логика работы с моделями ─────────────────────────────────
class AIModelManager:
    def __init__(self):
        self.best_model = None
        self.client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1")

    async def update_models(self):
        """Получает список бесплатных моделей с OpenRouter"""
        try:
            models = await self.client.models.list()
            # Фильтруем: только те, где prompt price = 0
            free_models = [
                m.id for m in models.data 
                if m.pricing and float(m.pricing.prompt) == 0
            ]
            # Выбираем одну из топов (обычно gemini-flash или llama-3-8b)
            self.best_model = free_models[0] if free_models else "google/gemini-2.0-flash-lite-preview-02-05:free"
            return free_models
        except Exception as e:
            logging.error(f"Ошибка при обновлении моделей: {e}")
            return []

ai_manager = AIModelManager()

async def ask_llm(user_input: str) -> str:
    if not ai_manager.best_model:
        await ai_manager.update_models()
    
    try:
        response = await ai_manager.client.chat.completions.create(
            model=ai_manager.best_model,
            messages=[{"role": "user", "content": user_input}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Ошибка LLM ({ai_manager.best_model}): {str(e)[:50]}"

# ── Бот ──────────────────────────────────────────────────────
router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer("👋 Бухгалтерский агент на связи! Присылай документы, фото или вопросы.")

@router.message(Command("ping"))
async def cmd_ping(msg: Message):
    wait = await msg.answer("🔄 Ищу лучшие бесплатные модели...")
    models = await ai_manager.update_models()
    await wait.edit_text(f"✅ Готово! Выбрана модель: <b>{ai_manager.best_model}</b>\n\nВсего бесплатных: {len(models)}")

@router.message(F.photo)
async def on_photo(msg: Message):
    await msg.answer("📸 Получил фото. Бухгалтерский анализ пока в разработке, но я его вижу!")

@router.message(F.document)
async def on_doc(msg: Message):
    await msg.answer("📄 Документ принят. Обрабатываю...")
    # Здесь можно добавить логику скачивания файла через bot.download()

@router.message(F.text)
async def on_text(msg: Message):
    wait = await msg.answer("⏳ Думаю...")
    response = await ask_llm(msg.text)
    await wait.edit_text(response)

# ── Запуск ────────────────────────────────────────────────────
async def main():
    bot = Bot(token=BOT_TOKEN, session=AiohttpSession(timeout=60), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    
    logging.info("🚀 Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    # Предварительная загрузка моделей при старте
    await ai_manager.update_models()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
