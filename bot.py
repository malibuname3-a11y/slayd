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
from PIL import Image
from io import BytesIO

load_dotenv()

# ================== SOZLAMALAR ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Gemini modellari
TEXT_MODEL = "gemini-2.0-flash"
IMAGE_MODEL = "imagen-4.0-generate-001"   # Eng yaxshi sifat

# ================== GEMINI - MATN + RASM ==================
def generate_slide_content(topic, slide_num, total_slides):
    prompt = f"""
    {topic} mavzusida {total_slides} slaydlik professional PowerPoint taqdimoti.
    {slide_num}-slayd uchun:

    TITLE: Qisqa va kuchli sarlavha (8-12 so'z)
    POINTS: nuqta1 | nuqta2 | nuqta3 | nuqta4
    IMAGE_PROMPT: Ushbu slayd uchun ingliz tilida batafsil, chiroyli rasm prompti

    Faqat shu formatda javob ber.
    """

    try:
        response = gemini_client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=800)
        )
        return response.text.strip()
    except Exception as e:
        print(f"Matn xatosi: {e}")
        return f"TITLE: {topic} - Slayd {slide_num}\nPOINTS: Asosiy ma'lumot | Muhim fakt | Afzallik | Natija\nIMAGE_PROMPT: professional modern presentation slide about {topic}"


def extract_title(content): 
    for line in content.splitlines():
        if "TITLE:" in line: return line.split("TITLE:", 1)[1].strip()
    return "Sarlavha"

def extract_points(content):
    for line in content.splitlines():
        if "POINTS:" in line:
            pts = [p.strip() for p in line.split("POINTS:", 1)[1].strip().split("|")]
            return "\n\n".join([f"▸ {p}" for p in pts if p])
    return "▸ Ma'lumotlar"

def extract_image_prompt(content):
    for line in content.splitlines():
        if "IMAGE_PROMPT:" in line:
            return line.split("IMAGE_PROMPT:", 1)[1].strip()
    return f"professional business presentation about {topic}"


# ================== GEMINI IMAGE GENERATION ==================
async def generate_image_gemini(prompt: str):
    try:
        print(f"   🎨 Gemini Image yaratilmoqda...")

        response = gemini_client.models.generate_images(
            model=IMAGE_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
            )
        )

        if response.generated_images:
            img = response.generated_images[0].image
            img_bytes = BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            print("   ✅ Gemini rasmi tayyor!")
            return img_bytes
    except Exception as e:
        print(f"Gemini Image xatosi: {e}")
    return None


# ================== PPTX YARATISH ==================
async def create_presentation(topic, num_slides=10):
    print(f"🚀 {topic} — {num_slides} slayd boshlandi...")
    prs = Presentation()

    # Bosh sahifa
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = topic.upper()

    for i in range(1, num_slides + 1):
        print(f"   Slayd {i}/{num_slides}")

        content = generate_slide_content(topic, i, num_slides)
        title = extract_title(content)
        points = extract_points(content)
        image_prompt = extract_image_prompt(content)

        slide = prs.slides.add_slide(prs.slide_layouts[5])

        # Sarlavha
        if slide.shapes.title:
            slide.shapes.title.text = title
            slide.shapes.title.text_frame.paragraphs[0].font.size = Pt(34)
            slide.shapes.title.text_frame.paragraphs[0].font.bold = True

        # Matn
        for shape in slide.shapes:
            if shape.has_text_frame and shape != slide.shapes.title:
                shape.text = points
                break

        # Rasm (Gemini)
        img_bytes = await generate_image_gemini(image_prompt + ", high quality, clean, professional, modern style")
        if img_bytes:
            try:
                slide.shapes.add_picture(img_bytes, Inches(6.0), Inches(1.5), 
                                       width=Inches(5.0), height=Inches(4.2))
                print("   ✅ Rasm qo'shildi")
            except Exception as e:
                print(f"   Rasm qo'shish xatosi: {e}")

        await asyncio.sleep(6)  # Rate limit himoyasi

    # Xulosa slaydi
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "XULOSA VA TAVSIYALAR"

    filename = f"{topic.replace(' ', '_')[:50]}.pptx"
    prs.save(filename)
    return filename


# ================== BOT HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎨 **Gemini AI Slayd Bot**\n\nMavzuni yozing:", parse_mode="Markdown")

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    context.user_data['topic'] = topic
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("5 slayd", callback_data="5"), InlineKeyboardButton("10 slayd", callback_data="10")],
        [InlineKeyboardButton("15 slayd", callback_data="15"), InlineKeyboardButton("20 slayd", callback_data="20")]
    ])
    
    await update.message.reply_text(f"✅ Mavzu: **{topic}**\n\nQancha slayd kerak?", reply_markup=keyboard)

async def handle_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    num_slides = int(query.data)
    topic = context.user_data.get('topic', 'Taqdimot')

    await query.edit_message_text(f"⏳ {topic} — {num_slides} slayd tayyorlanmoqda...\nBu biroz vaqt oladi.")

    try:
        filename = await create_presentation(topic, num_slides)
        
        with open(filename, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ **Tayyor!**\n📌 {topic}\n📊 {num_slides} slayd\n🎨 Gemini Image bilan"
            )
        os.remove(filename)
    except Exception as e:
        await query.edit_message_text(f"❌ Xatolik: {str(e)[:200]}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    app.add_handler(CallbackQueryHandler(handle_slide_count))
    
    print("✅ Bot ishga tushdi! (Gemini Image bilan)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
