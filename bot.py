import asyncio
import google.generativeai as genai
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from dotenv import load_dotenv
import os
import sys

# ===================== SOZLAMALAR =====================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    print("❌ BOT_TOKEN yoki GEMINI_API_KEY topilmadi!")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===================== UZUN XABARNI BO‘LISH =====================
def split_message(text: str, max_length: int = 4000):
    """Uzun matnni bo'lib yuborish"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        # Oxirgi bo'sh joydan kesish (so'z buzilmasligi uchun)
        split_pos = text[:max_length].rfind(' ')
        if split_pos == -1:
            split_pos = max_length
        parts.append(text[:split_pos])
        text = text[split_pos:].strip()
    return parts

@dp.message(F.text)
async def gemini_handler(message: Message):
    user_text = message.text.strip()
    
    if user_text.startswith("/start"):
        await message.answer("👋 Salom! Men Gemini AI botiman.\nSavollaringizni yozing ✨")
        return

    await message.chat.do("typing")

    try:
        response = model.generate_content(user_text)
        reply_text = response.text.strip()

        # Agar javob uzun bo'lsa, bo'lib yuboramiz
        messages = split_message(reply_text)
        
        for part in messages:
            await message.answer(part, parse_mode="Markdown")
            
    except Exception as e:
        print(f"Xatolik: {e}")
        await message.answer("⚠️ Xatolik yuz berdi. Qayta urinib ko‘ring.")


async def main():
    print("🚀 Gemini Telegram Bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
