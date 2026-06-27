import asyncio, logging, os
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(level=logging.INFO)

# ── Настройки ────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OR_KEY    = os.environ.get("OPENROUTER_API_KEY", "").strip()

# Резервная бесплатная модель на случай, если автопоиск подведет
FALLBACK_MODEL = "google/gemini-2.0-flash-lite-preview-02-05:free"

# ── Логика работы с моделями ─────────────────────────────────
class AIModelManager:
    def __init__(self):
        self.best_model = FALLBACK_MODEL
        self.client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1")

    async def update_models(self):
        """Пытается найти бесплатные модели, если не вышло - ставит fallback"""
        try:
            models = await self.client.models.list()
            # Пробуем найти модель с нулевой ценой в разных форматах
            free_models = []
            for m in models.data:
                # Проверка: есть ли pricing и является ли цена 0
                pricing = getattr(m, 'pricing', None)
                if pricing and hasattr(pricing, 'prompt') and float(pricing.prompt) == 0:
                    free_models.append(m.id)
            
            if free_models:
                self.best_model = free_models[0]
                logging.info(f"Найдено бесплатных моделей: {len(free_models)}. Выбрана: {self.best_model}")
            else:
                logging.warning("Бесплатные модели по API не найдены, используем fallback.")
                self.best_model = FALLBACK_MODEL
        except Exception as e:
            logging.error(f"Ошибка при обновлении моделей: {e}. Используем fallback.")
            self.best_model = FALLBACK_MODEL

ai_manager = AIModelManager()

async def ask_llm(user_input: str) -> str:
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
    wait = await msg.answer("🔄 Обновляю список моделей...")
    await ai_manager.update_models()
    await wait.edit_text(f"✅ Готово! Выбрана модель: <b>{ai_manager.best_model}</b>")

@router.message(F.photo)
async def on_photo(msg: Message):
    await msg.answer("📸 Фото получил. Скоро научусь его читать!")

@router.message(F.document)
async def on_doc(msg: Message):
    await msg.answer("📄 Документ принят. Пока просто храню его.")

@router.message(F.text)
async def on_text(msg: Message):
    wait = await msg.answer("⏳")
    response = await ask_llm(msg.text)
    await wait.edit_text(response)

# ── Запуск ────────────────────────────────────────────────────
async def main():
    if not BOT_TOKEN or not OR_KEY:
        logging.error("❌ Ошибка: Не заданы BOT_TOKEN или OPENROUTER_API_KEY")
        return

    bot = Bot(token=BOT_TOKEN, session=AiohttpSession(timeout=60), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    
    logging.info("🚀 Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await ai_manager.update_models()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
