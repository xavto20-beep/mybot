"""
Бухгалтерский ассистент — облачная версия
"""
import asyncio, logging, os, aiosqlite
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(level=logging.INFO)

# ── Настройки ────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OWNER_ID  = int(os.environ.get("OWNER_USER_ID", 0))
DS_KEY    = os.getenv("DEEPSEEK_API_KEY", "").strip()
OR_KEY    = os.getenv("OPENROUTER_API_KEY", "").strip()
GEMINI_KEY= os.getenv("GEMINI_API_KEY", "").strip()
DB_PATH   = "agent.db"

# ── LLM: Исправленный роутер ──────────────────────────────────
async def ask_llm(messages: list) -> str:
    # Исправленный Gemini
    if GEMINI_KEY:
        try:
            # Для Google AI Studio используем именно этот URL
            client = AsyncOpenAI(api_key=GEMINI_KEY, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            r = await client.chat.completions.create(
                model="gemini-1.5-flash", messages=messages
            )
            return r.choices[0].message.content
        except Exception as e:
            logging.warning(f"Gemini Error: {e}")

    # OpenRouter
    if OR_KEY:
        try:
            client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1")
            r = await client.chat.completions.create(
                model="deepseek/deepseek-chat", messages=messages
            )
            return r.choices[0].message.content
        except Exception as e:
            logging.warning(f"OpenRouter Error: {e}")

    return "❌ Модели не отвечают. Проверь ключи /ping"

# ── База данных и Агент (оставляем как было) ──────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, role TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        await db.commit()

async def save_msg(chat_id, role, content):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO messages (chat_id,role,content) VALUES (?,?,?)", (chat_id, role, content))
        await db.commit()

async def get_history(chat_id, limit=6):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT role, content FROM messages WHERE chat_id=? ORDER BY created_at DESC LIMIT ?", (chat_id, limit)) as cur:
            rows = await cur.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

async def process(chat_id: int, text: str) -> str:
    history = await get_history(chat_id)
    messages = [{"role": "system", "content": "Ты бухгалтерский ассистент. Отвечай кратко."}] + history + [{"role": "user", "content": text}]
    response = await ask_llm(messages)
    await save_msg(chat_id, "user", text)
    await save_msg(chat_id, "assistant", response)
    return response

# ── Бот ──────────────────────────────────────────────────────
router = Router()

@router.message(Command("ping"))
async def cmd_ping(msg: Message):
    wait = await msg.answer("🔄 Проверка...")
    res = "📊 Статус:\n"
    if GEMINI_KEY:
        try:
            c = AsyncOpenAI(api_key=GEMINI_KEY, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            await c.chat.completions.create(model="gemini-1.5-flash", messages=[{"role":"user","content":"hi"}], max_tokens=5)
            res += "🟢 Gemini: OK\n"
        except Exception as e:
            res += f"🔴 Gemini: {str(e)[:30]}...\n"
    await wait.edit_text(res)

@router.message(F.text)
async def on_text(msg: Message):
    wait = await msg.answer("⏳")
    try:
        response = await process(msg.chat.id, msg.text)
        await wait.edit_text(response)
    except Exception as e:
        await wait.edit_text(f"❌ Ошибка: {e}")

async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN, session=AiohttpSession(timeout=60), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
