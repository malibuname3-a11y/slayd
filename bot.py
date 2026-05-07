import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pptx import Presentation
from pptx.util import Inches, Pt
from google import genai
from google.genai import types
import io

# ========== KONFIGURATSIYA ==========
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("❌ Kalitlarni tekshiring! .env faylida token va API key bo'lishi kerak.")

# Gemini mijozini yaratish
client = genai.Client(api_key=GEMINI_API_KEY)

# ========== MODELLARNI TEKSHIRISH ==========
def get_available_models():
    """Mavjud modellarni ko'rsatish"""
    print("🔍 Mavjud modellarni tekshirish...")
    for model in client.models.list():
        print(f"  - {model.name}")
    print()

# ========== TO'G'RI MODELLAR BILAN SLAYDLAR YARATISH ==========

# Matn yaratish uchun model (Flash tez va samarali)
TEXT_MODEL = "gemini-2.0-flash"  # 2026 yil aprel holatida eng so'nggi stable model[citation:3]

# Rasm yaratish uchun model - alohida model kerak!
# Gemini 2.0 Flash rasm yarata olmaydi, buning uchun maxsus model kerak[citation:4]
IMAGE_MODEL = "gemini-2.5-flash-image-preview"  # Rasm yaratish uchun maxsus model[citation:4]

def generate_slide_content(topic, slide_num, total_slides):
    """Gemini orqali slayd matnini yaratish (MATN UChUN)"""
    
    prompt = f"""
    {topic} mavzusida {total_slides} slaydlik taqdimot.
    {slide_num}-slayd uchun:
    
    1. TITLE: Qisqa, aniq sarlavha (10 so'zgacha)
    2. POINTS: 3-4 ta asosiy nuqta
    
    Format (aynan shu formatda javob ber):
    TITLE: [sarlavha]
    POINTS: [nuqta1] | [nuqta2] | [nuqta3] | [nuqta4]
    """
    
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL,  # MUHIM: Matn uchun gemini-2.0-flash
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=500
            )
        )
        return response.text
    except Exception as e:
        print(f"Matn yaratishda xatolik: {e}")
        return f"TITLE: {topic} - {slide_num}-slayd\nPOINTS: Kirish | Asosiy qism | Xulosa"

def generate_slide_image(topic, slide_title):
    """Gemini orqali slaydga mos rasm yaratish (RASM UCHUN - alohida model!)"""
    
    image_prompt = f"Create a professional presentation slide background image about: {topic} - {slide_title}. Modern, clean, professional style. No text on the image, just visual elements."
    
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,  # MUHIM: Rasm uchun maxsus model!
            contents=image_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.8
            )
        )
        
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    return part.inline_data.data
        return None
    except Exception as e:
        print(f"Rasm yaratishda xatolik: {e}")
        return None

def extract_title(content):
    """Gemini javobidan sarlavhani olish"""
    lines = content.split('\n')
    for line in lines:
        if line.startswith('TITLE:'):
            return line.replace('TITLE:', '').strip()
    return "Asosiy mavzu"

def extract_points(content):
    """Gemini javobidan nuqtalarni olish"""
    for line in content.split('\n'):
        if line.startswith('POINTS:'):
            points = line.replace('POINTS:', '').strip()
            # '|' bilan ajratilgan nuqtalarni formatlash
            points_list = [p.strip() for p in points.split('|')]
            formatted = '\n• '.join(points_list)
            return f"• {formatted}"
    return f"• {content[:200]}"

def create_ai_presentation(topic, num_slides=3):
    """To'liq taqdimot yaratish"""
    print(f"📝 '{topic}' uchun taqdimot yaratilmoqda...")
    
    prs = Presentation()
    
    # 1. Sarlavha slaydi
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = topic.upper()
    slide.placeholders[1].text = "Gemini AI tomonidan tayyorlandi"
    
    # Sarlavha uchun rasm
    print("🎨 Sarlavha uchun rasm yaratilmoqda...")
    img_data = generate_slide_image(topic, "cover")
    if img_data:
        with open("temp_cover.png", "wb") as f:
            f.write(img_data)
        slide.shapes.add_picture("temp_cover.png", Inches(0), Inches(3), 
                                width=prs.slide_width, height=Inches(3))
        os.remove("temp_cover.png")
    
    # 2. Mavzu slaydlari
    for i in range(1, num_slides + 1):
        print(f"📄 {i}/{num_slides} - slayd tayyorlanmoqda...")
        
        # Matn yaratish
        content = generate_slide_content(topic, i, num_slides)
        title = extract_title(content)
        points = extract_points(content)
        
        # Slayd yaratish
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title
        slide.placeholders[1].text = points
        
        # Rasm qo'shish
        print(f"🎨 Slayd {i} uchun rasm yaratilmoqda...")
        img_data = generate_slide_image(topic, title)
        if img_data:
            with open(f"temp_slide_{i}.png", "wb") as f:
                f.write(img_data)
            slide.shapes.add_picture(f"temp_slide_{i}.png", 
                                    Inches(7), Inches(1.5), 
                                    width=Inches(4), height=Inches(3))
            os.remove(f"temp_slide_{i}.png")
    
    filename = f"{topic.replace(' ', '_')}_presentation.pptx"
    prs.save(filename)
    print(f"✅ Taqdimot saqlandi: {filename}")
    return filename

# ========== TELEGRAM BOT ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 **Gemini Slayd Botiga Xush Kelibsiz!**\n\n"
        "Menga mavzu yozing, men:\n"
        "✅ Professional matn yozaman (Gemini 2.0 Flash)\n"
        "✅ Har bir slaydga mos rasm yarataman (Gemini 2.5 Flash Image)\n"
        "✅ To'liq PowerPoint taqdimotini jo'nataman\n\n"
        "Masalan: 'Sun'iy intellekt', 'Marketing strategiyasi', 'Ekologiya'",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text
    await update.message.reply_text(
        f"⏳ '{topic}' mavzusida taqdimot tayyorlanmoqda...\n\n"
        f"📝 Matn yozilmoqda...\n"
        f"🎨 Rasmlar yaratilmoqda...\n"
        f"⏱ Bu 1-2 daqiqa vaqt olishi mumkin."
    )
    
    try:
        filename = create_ai_presentation(topic, num_slides=3)
        
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ **Taqdimot tayyor!**\n\n"
                       f"📌 Mavzu: {topic}\n"
                       f"🤖 AI tomonidan yaratildi: Gemini 2.0 Flash (matn) + Gemini 2.5 Flash Image (rasm)\n"
                       f"🎨 Har bir slaydda original rasm\n\n"
                       f"Qayta foydalanish uchun /start",
                parse_mode="Markdown"
            )
        
        os.remove(filename)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}\n\nQaytadan urunib ko'ring.")

def main():
    print("🤖 Gemini Slayd Bot ishga tushmoqda...")
    print(f"📝 Matn modeli: {TEXT_MODEL}")
    print(f"🎨 Rasm modeli: {IMAGE_MODEL}")
    
    # Mavjud modellarni ko'rsatish (diagnostika uchun)
    get_available_models()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
