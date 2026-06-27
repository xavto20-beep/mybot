"""
Бухгалтерский ассистент — облачная версия
Один файл, минимум зависимостей
"""
import asyncio, logging, os, aiosqlite
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(level=logging.INFO)

# ── Настройки из переменных окружения ────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID  = int(os.environ["OWNER_USER_ID"])
DS_KEY    = os.getenv("DEEPSEEK_API_KEY", "")
OR_KEY    = os.getenv("OPENROUTER_API_KEY", "")
DB_PATH   = "agent.db"

OWNER_NAME    = os.getenv("OWNER_NAME", "")
OWNER_INN     = os.getenv("OWNER_INN", "")
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS", "")
OWNER_BANK    = os.getenv("OWNER_BANK", "")
OWNER_BIK     = os.getenv("OWNER_BIK", "")
OWNER_ACCOUNT = os.getenv("OWNER_ACCOUNT", "")
OWNER_CORR    = os.getenv("OWNER_CORR_ACCOUNT", "")
OWNER_PHONE   = os.getenv("OWNER_PHONE", "")

# ── LLM: DeepSeek → OpenRouter free ──────────────────────────
async def ask_llm(messages: list) -> str:
    if DS_KEY:
        try:
            client = AsyncOpenAI(api_key=DS_KEY, base_url="https://api.deepseek.com/v1")
            r = await client.chat.completions.create(
                model="deepseek-chat", messages=messages,
                temperature=0.1, max_tokens=1500
            )
            return r.choices[0].message.content
        except Exception as e:
            logging.warning(f"DeepSeek: {e}")

    if OR_KEY:
        try:
            client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1")
            r = await client.chat.completions.create(
                model="deepseek/deepseek-chat-v3-0324:free",
                messages=messages, max_tokens=1500
            )
            return r.choices[0].message.content
        except Exception as e:
            logging.warning(f"OpenRouter: {e}")

    return "❌ Нет доступных моделей. Проверь API ключи в настройках."

# ── База данных ───────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER, role TEXT, content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS counterparties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, inn TEXT, kpp TEXT,
                address TEXT, bank_name TEXT,
                bik TEXT, account TEXT
            );
            CREATE TABLE IF NOT EXISTS doc_counters (
                doc_type TEXT PRIMARY KEY,
                counter INTEGER DEFAULT 0
            );
        """)
        await db.commit()

async def save_msg(chat_id, role, content):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (chat_id,role,content) VALUES (?,?,?)",
            (chat_id, role, content)
        )
        await db.commit()

async def get_history(chat_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT role, content FROM messages
               WHERE chat_id=? ORDER BY created_at DESC LIMIT ?""",
            (chat_id, limit)
        ) as cur:
            rows = await cur.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

async def next_num(doc_type):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO doc_counters VALUES (?,0)", (doc_type,)
        )
        await db.execute(
            "UPDATE doc_counters SET counter=counter+1 WHERE doc_type=?", (doc_type,)
        )
        await db.commit()
        async with db.execute(
            "SELECT counter FROM doc_counters WHERE doc_type=?", (doc_type,)
        ) as c:
            return (await c.fetchone())[0]

# ── Системный промпт ──────────────────────────────────────────
def system_prompt():
    return f"""Ты — личный бухгалтерский ассистент предпринимателя. Только для владельца.
Отвечай кратко, по делу, на русском. Используй эмодзи для структуры.

РЕКВИЗИТЫ ВЛАДЕЛЬЦА:
{OWNER_NAME}, ИНН {OWNER_INN}
Адрес: {OWNER_ADDRESS}
Банк: {OWNER_BANK}, БИК {OWNER_BIK}
Р/с: {OWNER_ACCOUNT}  К/с: {OWNER_CORR}
Тел: {OWNER_PHONE}

ЧТО УМЕЕШЬ:
• Создавать документы: счёт, акт, платёжное поручение — выводишь готовый заполненный текст
• Консультировать по УСН, бухгалтерии, налогам
• Запоминать контрагентов по просьбе

ДОКУМЕНТЫ:
Когда просят создать документ — сразу выводи полный текст документа со всеми реквизитами.
Не спрашивай лишнего — используй то что есть, недостающее замени на [УТОЧНИТЬ].
Нумерацию начинай с 1 если не указана.
Для счёта и акта: шапка с реквизитами обеих сторон, таблица услуг, итог, подписи.
"""

# ── Агент ─────────────────────────────────────────────────────
async def process(chat_id: int, text: str) -> str:
    history = await get_history(chat_id)
    messages = [
        {"role": "system", "content": system_prompt()},
        *history,
        {"role": "user", "content": text}
    ]
    response = await ask_llm(messages)
    await save_msg(chat_id, "user", text)
    await save_msg(chat_id, "assistant", response)
    return response

# ── Telegram бот ──────────────────────────────────────────────
router = Router()

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        if event.from_user and event.from_user.id != OWNER_ID:
            await event.answer("⛔ Нет доступа")
            return
        return await handler(event, data)

@router.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer(
        "👋 Привет! Я твой бухгалтерский ассистент.\n\n"
        "<b>Что умею:</b>\n"
        "📄 Создать счёт, акт, платёжное поручение\n"
        "👤 Запомнить контрагента\n"
        "💬 Ответить по бухгалтерии и УСН\n\n"
        "<b>Примеры:</b>\n"
        "• Создай счёт для ООО Ромашка на 50000 за консультацию\n"
        "• Сделай акт за июнь для ИП Петров\n"
        "• Что лучше — патент или УСН?\n\n"
        "Просто пиши!"
    )

@router.message(F.text)
async def on_text(msg: Message):
    wait = await msg.answer("⏳")
    try:
        response = await process(msg.chat.id, msg.text)
        await wait.edit_text(response)
    except Exception as e:
        logging.error(e)
        await wait.edit_text(f"❌ Ошибка: {e}")

# ── Запуск ────────────────────────────────────────────────────
async def main():
    await init_db()
    
    # Расширенный таймаут для Telegram API, чтобы избежать обрыва связи
    session = Aiohttp
