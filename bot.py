import os
import logging
import base64
import asyncio
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

# ── Логика работы с API ──────────────────────────────────────
async def ask_gemini_multimodal(text: str, file_bytes: bytes = None, mime_type: str = None) -> str:
    try:
        # Формируем input согласно документации Interactions API
        input_content = []
        
        # Если есть файл, добавляем его
        if file_bytes:
            encoded_file = base64.b64encode(file_bytes).decode("utf-8")
            input_content.append({
                "type": "image" if "image" in mime_type else "document", # Gemini API принимает файлы через base64
                "data": encoded_file,
                "mime_type": mime_type
            })
            
        # Добавляем текстовый промпт
        input_content.append({"type": "text", "text": text or "Проанализируй этот документ для целей бухгалтерии."})

        interaction = client.interactions.create(
            model="gemini-3.5-flash",
            input=input_content
        )
        return interaction.output_text
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return f"❌ Ошибка обработки: {str(e)[:100]}"

# ── Бот ──────────────────────────────────────────────────────
router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer("🤖 Ассистент готов. Присылай фото чеков или PDF-файлы для анализа.")

@router.message(F.photo)
async def on_photo(msg: Message):
    wait = await msg.answer("⏳ Анализирую фото...")
    # Берем фото самого высокого качества
    file_id = msg.photo[-1].file_id
    file = await msg.bot.get_file(file_id)
    file_bytes = await msg.bot.download_file(file.file_path)
    
    response = await ask_gemini_multimodal("Что на этом фото? Извлеки данные для бухгалтерии.", file_bytes.read(), "image/jpeg")
    await wait.edit_text(response)

@router.message(F.document)
async def on_doc(msg: Message):
    wait = await msg.answer("⏳ Анализирую документ...")
    file_id = msg.document.file_id
    file = await msg.bot.get_file(file_id)
    file_bytes = await msg.bot.download_file(file.file_path)
    
    mime_type = msg.document.mime_type
    response = await ask_gemini_multimodal("Извлеки данные из этого документа для бухгалтерии.", file_bytes.read(), mime_type)
    await wait.edit_text(response)

@router.message(F.text)
async def on_text(msg: Message):
    wait = await msg.answer("⏳ Думаю...")
    response = await ask_gemini_multimodal(msg.text)
    await wait.edit_text(response)

async def main():
    if not BOT_TOKEN or not API_KEY:
        logging.error("❌ BOT_TOKEN или GEMINI_API_KEY не заданы!")
        return

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🚀 Бот запущен и готов к работе с файлами")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
