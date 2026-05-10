import asyncio
import google.generativeai as genai
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger
import os
import sys

# ===================== SOZLAMALAR =====================
load_dotenv()  # .env faylni yuklaydi

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Tekshirish
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN topilmadi! .env faylni tekshiring.")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY topilmadi! .env faylni tekshiring.")
    sys.exit(1)

# Gemini sozlamalari
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.1-flash')   # gemini-3.1-pro ham qo'yishingiz mumkin

# ===================== BOT =====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(F.text)
async def gemini_handler(message: Message):
    user_text = message.text.strip()
    
    # /start komandasi
    if user_text.startswith("/start"):
        await message.answer(
            "👋 Salom! Men Gemini AI botiman.\n"
            "Savollaringizni yozing, men javob beraman."
        )
        return

    await message.chat.do("typing")   # "yozayapti..." effekti

    try:
        response = model.generate_content(user_text)
        await message.answer(response.text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Xatolik: {e}")
        await message.answer("⚠️ Xatolik yuz berdi. Qayta urinib ko‘ring.")


async def main():
    logger.success("🚀 Gemini Telegram Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
