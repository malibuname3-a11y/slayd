import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pptx import Presentation
from pptx.util import Inches, Pt
from google import genai
from google.genai import types

# ========== MUHIM: Kalitlarni .env fayldan avtomatik o'qish ==========
load_dotenv()  # .env faylidagi barcha kalitlarni o'qiydi

# Kalitlarni olish (endi qo'lda yozish shart emas!)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Kalitlarni tekshirish
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN .env faylida topilmadi!")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY .env faylida topilmadi!")

print("✅ Kalitlar .env fayldan muvaffaqiyatli yuklandi!")

# Gemini mijozini yaratish (API key avtomatik olinadi)
client = genai.Client(api_key=GEMINI_API_KEY)

# ========== SLAYDLAR YARATISH FUNKSIYALARI ==========
def generate_slide_content(topic, slide_num, total_slides):
    """Gemini orqali slayd matnini yaratish"""
    prompt = f"""
    {topic} mavzusida {total_slides} slaydlik taqdimot.
    {slide_num}-slayd uchun:
    
    1. TITLE: Qisqa, aniq sarlavha
    2. POINTS: 3-4 ta asosiy nuqta
    
    Format:
    TITLE: [sarlavha]
    POINTS: [nuqta1] | [nuqta2] | [nuqta3] | [nuqta4]
    """
    
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=500)
    )
    return response.text

def generate_slide_image(topic, slide_title):
    """Gemini orqali slaydga mos rasm yaratish"""
    image_prompt = f"Professional presentation background about {topic} - {slide_title}, modern, clean, 1920x1080"
    
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=image_prompt,
        config=types.GenerateContentConfig(response_modalities=["Image"], temperature=0.8)
    )
    
    if response.candidates[0].content.parts[0].inline_data:
        return response.candidates[0].content.parts[0].inline_data.data
    return None

def extract_title(content):
    for line in content.split('\n'):
        if line.startswith('TITLE:'):
            return line.replace('TITLE:', '').strip()
    return "Asosiy mavzu"

def extract_points(content):
    for line in content.split('\n'):
        if line.startswith('POINTS:'):
            points = line.replace('POINTS:', '').strip()
            formatted = points.replace('|', '\n• ')
            return f"• {formatted}"
    return f"• {content[:200]}"

def create_ai_presentation(topic, num_slides=3):
    """To'liq taqdimot yaratish"""
    prs = Presentation()
    
    # Sarlavha slaydi
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = topic.upper()
    slide.placeholders[1].text = "Gemini AI tomonidan tayyorlandi"
    
    # Mavzu slaydlari
    for i in range(1, num_slides + 1):
        content = generate_slide_content(topic, i, num_slides)
        title = extract_title(content)
        points = extract_points(content)
        
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title
        slide.placeholders[1].text = points
        
        # Rasm qo'shish
        img_data = generate_slide_image(topic, title)
        if img_data:
            with open(f"temp_{i}.png", "wb") as f:
                f.write(img_data)
            slide.shapes.add_picture(f"temp_{i}.png", Inches(7), Inches(1.5), 
                                    width=Inches(4), height=Inches(3))
            os.remove(f"temp_{i}.png")
    
    filename = f"{topic.replace(' ', '_')}_presentation.pptx"
    prs.save(filename)
    return filename

# ========== TELEGRAM BOT ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 **Gemini Slayd Botiga Xush Kelibsiz!**\n\n"
        "Menga mavzu yozing, men:\n"
        "✅ Matn yozaman\n"
        "✅ Rasm yarataman\n"
        "✅ To'liq PowerPoint jo'nataman\n\n"
        "Masalan: 'Sun'iy intellekt', 'Marketing'",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text
    await update.message.reply_text(f"⏳ '{topic}' mavzusida taqdimot tayyorlanmoqda...\n⏱ 1-2 daqiqa kuting.")
    
    try:
        filename = create_ai_presentation(topic, num_slides=3)
        
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ **Taqdimot tayyor!**\n📌 Mavzu: {topic}\n🤖 Gemini AI tomonidan yaratildi"
            )
        os.remove(filename)
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
