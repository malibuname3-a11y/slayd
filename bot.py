import os
import asyncio
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pptx import Presentation
from pptx.util import Inches, Pt
from google import genai
from google.genai import types

load_dotenv()

# ================== API SOZLAMALARI ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")

# Gemini sozlamalari
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
TEXT_MODEL = "gemini-2.0-flash"   # Ishlaydigan model

# ================== 1. GEMINI - MATN YARATISH ==================
def generate_slide_content(topic, slide_num, total_slides):
    prompt = f"""
    {topic} mavzusida {total_slides} slaydlik professional PowerPoint taqdimoti tayyorla.
    {slide_num}-slayd uchun quyidagi formatda javob ber:

    TITLE: Qisqa, kuchli va jozibali sarlavha
    POINTS: nuqta1 | nuqta2 | nuqta3 | nuqta4
    IMAGE_PROMPT: Ingliz tilida professional, chiroyli rasm prompti (FLUX uchun)

    Javobni faqat shu 3 qatorda ber, boshqa matn qo'shma.
    """

    try:
        response = gemini_client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.75,
                max_output_tokens=700
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini xatosi: {e}")
        return f"""TITLE: {topic} - Slayd {slide_num}
POINTS: Muhim ma'lumotlar | Asosiy faktlar | Afzalliklar | Natijalar
IMAGE_PROMPT: professional presentation slide about {topic}"""


def extract_title(content):
    for line in content.splitlines():
        if line.startswith('TITLE:'):
            return line.replace('TITLE:', '').strip()
    return f"Slayd {slide_num}"


def extract_points(content):
    for line in content.splitlines():
        if line.startswith('POINTS:'):
            points = line.replace('POINTS:', '').strip()
            points_list = [p.strip() for p in points.split('|') if p.strip()]
            return '\n\n'.join([f"▸ {p}" for p in points_list])
    return "▸ Ma'lumotlar\n▸ Muhim jihatlar"


def extract_image_prompt(content):
    for line in content.splitlines():
        if line.startswith('IMAGE_PROMPT:'):
            return line.replace('IMAGE_PROMPT:', '').strip()
    return f"professional business presentation about {topic}"


# ================== 2. REPLICATE - RASM YARATISH ==================
async def generate_image_replicate(prompt: str):   # ← async qo'shildi
    if not REPLICATE_API_KEY:
        print("⚠️ REPLICATE_API_KEY yo'q")
        return None

    headers = {
        "Authorization": f"Token {REPLICATE_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "input": {
            "prompt": prompt + ", high quality, clean, professional, presentation style",
            "width": 1024,
            "height": 768,
            "num_outputs": 1,
            "go_fast": True
        }
    }

    try:
        print(f"   🖼 Rasm yaratilmoqda: {prompt[:70]}...")

        response = requests.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code != 201:
            print(f"   ❌ Replicate error: {response.status_code}")
            return None

        prediction = response.json()
        get_url = prediction["urls"]["get"]

        for _ in range(35):
            status_resp = requests.get(get_url, headers=headers, timeout=30)
            data = status_resp.json()
            status = data.get("status")

            if status == "succeeded":
                print("   ✅ Rasm tayyor!")
                return data["output"][0]
            elif status == "failed":
                print(f"   ❌ FLUX failed: {data.get('error')}")
                return None

            await asyncio.sleep(1.8)   # Endi xato bermaydi

        return None
    except Exception as e:
        print(f"   ❌ Replicate xatosi: {e}")
        return None
# ================== 3. POWERPOINT YARATISH ==================
async def create_presentation(topic, num_slides=5):
    print(f"🎯 '{topic}' uchun {num_slides} slayd tayyorlanmoqda...")

    prs = Presentation()

    # 1. Bosh sahifa
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = topic.upper()

    # Asosiy slaydlar
    for i in range(1, num_slides + 1):
        print(f"   Slayd {i}/{num_slides} ...")

        content = generate_slide_content(topic, i, num_slides)
        title = extract_title(content)
        points = extract_points(content)
        image_prompt = extract_image_prompt(content)

        slide = prs.slides.add_slide(prs.slide_layouts[5])  # Title and Content layout

        # Sarlavha
        if slide.shapes.title:
            slide.shapes.title.text = title
            slide.shapes.title.text_frame.paragraphs[0].font.size = Pt(32)
            slide.shapes.title.text_frame.paragraphs[0].font.bold = True

        # Matn
        for shape in slide.shapes:
            if shape.has_text_frame and shape != slide.shapes.title:
                shape.text = points
                break

        # Rasm qo'shish
        img_url = generate_image_replicate(image_prompt)
        if img_url and download_image(img_url, f"temp_slide_{i}.jpg"):
            try:
                slide.shapes.add_picture(f"temp_slide_{i}.jpg", 
                                       Inches(6.2), Inches(1.5), 
                                       width=Inches(4.8), height=Inches(4.0))
                print(f"   ✅ Rasm qo'shildi")
            except Exception as e:
                print(f"   Rasm qo'shishda xato: {e}")
            finally:
                if os.path.exists(f"temp_slide_{i}.jpg"):
                    os.remove(f"temp_slide_{i}.jpg")

        await asyncio.sleep(7)  # Replicate rate limit uchun (muhim!)

    # Xulosa slaydi
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "XULOSA"
    if len(slide.placeholders) > 1:
        slide.placeholders[1].text = f"{topic} bo'yicha asosiy xulosalar va tavsiyalar."

    filename = f"{topic.replace(' ', '_')[:40]}.pptx"
    prs.save(filename)
    print(f"✅ Taqdimot saqlandi: {filename}")
    return filename


# ================== TELEGRAM BOT ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎨 **AI Slayd Generatori**\n\n"
        "Mavzuni yozing, men Gemini + FLUX bilan chiroyli taqdimot tayyorlayman!",
        parse_mode="Markdown"
    )


async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    context.user_data['topic'] = topic

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("5 slayd", callback_data="3"),
         InlineKeyboardButton("10 slayd", callback_data="5")],
        [InlineKeyboardButton("15 slayd", callback_data="7"),
         InlineKeyboardButton("20 slayd", callback_data="10")]
    ])

    await update.message.reply_text(
        f"✅ **Mavzu:** {topic}\n\nQancha slayd kerak?", 
        reply_markup=keyboard
    )


async def handle_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    num_slides = int(query.data)
    topic = context.user_data.get('topic', 'Taqdimot')

    await query.edit_message_text(f"⏳ **{topic}** — {num_slides} slayd tayyorlanmoqda...\nAI ishlamoqda...")

    try:
        filename = await create_presentation(topic, num_slides)

        with open(filename, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ **Tayyor!**\n\n📌 {topic}\n📊 {num_slides} slayd\n🎨 AI rasmlar bilan"
            )
        os.remove(filename)
    except Exception as e:
        print(f"Xatolik: {e}")
        await query.edit_message_text(f"❌ Xatolik yuz berdi: {str(e)[:200]}")


def main():
    print("🤖 Slayd Bot ishga tushmoqda...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    app.add_handler(CallbackQueryHandler(handle_slide_count))

    print("✅ Bot muvaffaqiyatli ishga tushdi!")
    app.run_polling(drop_pending_updates=True)   # Muhim!


if __name__ == "__main__":
    main()
