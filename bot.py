import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pptx import Presentation
from pptx.util import Inches, Pt
from google import genai
from google.genai import types
import asyncio

# ========== KONFIGURATSIYA ==========
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("❌ Kalitlarni tekshiring! .env faylini sozlang.")

client = genai.Client(api_key=GEMINI_API_KEY)

# ========== TO'G'RI MODELLAR ==========
TEXT_MODEL = "gemini-2.0-flash"                       # Matn yozish
IMAGE_MODEL = "gemini-2.5-flash-image"                # Rasm yaratish (yangilangan!)

# Agar gemini-2.5-flash-image ishlamasa, buni sinab ko'ring:
# IMAGE_MODEL = "imagen-4.0-generate-001"            # Imagen 4 (muqobil)

# ========== SLAYDLAR YARATISH (20 slaydgacha) ==========
def generate_slide_content(topic, slide_num, total_slides):
    """Gemini orqali slayd matnini yaratish"""
    prompt = f"""
    {topic} mavzusida {total_slides} slaydlik taqdimot.
    {slide_num}-slayd uchun:
    
    1. TITLE: Qisqa, aniq sarlavha
    2. POINTS: 3-4 ta asosiy nuqta
    
    Format (aynan shu formatda javob ber):
    TITLE: [sarlavha]
    POINTS: [nuqta1] | [nuqta2] | [nuqta3] | [nuqta4]
    """
    
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=500
            )
        )
        return response.text
    except Exception as e:
        print(f"Matn xatosi: {e}")
        return f"TITLE: {topic} - {slide_num}-slayd\nPOINTS: Kirish | Asosiy qism | Tahlil | Xulosa"

def generate_slide_image(topic, slide_title):
    """Gemini orqali slaydga mos rasm yaratish"""
    image_prompt = f"Professional presentation background image about {topic} - {slide_title}. Modern, clean, minimalistic. No text on image."
    
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
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
        print(f"Rasm xatosi: {e}")
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
            points_list = [p.strip() for p in points.split('|')]
            formatted = '\n• '.join(points_list)
            return f"• {formatted}"
    return f"• {content[:200]}"

def create_full_presentation(topic, num_slides=10):
    """20 slaydgacha to'liq taqdimot yaratish"""
    print(f"📝 '{topic}' - {num_slides} slaydli taqdimot yaratilmoqda...")
    
    prs = Presentation()
    
    # 1. Sarlavha slaydi
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = topic.upper()
    slide.placeholders[1].text = f"Gemini AI tomonidan tayyorlandi\n{num_slides} slayd"
    
    # 2. Mundarija slaydi (agar slaydlar soni 5 dan ko'p bo'lsa)
    if num_slides > 5:
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = "MUNDARIJA"
        slide.placeholders[1].text = "• Taqdimot mazmuni\n• Asosiy bo'limlar\n• Xulosa va tavsiyalar"
    
    # 3. Asosiy slaydlar
    for i in range(1, min(num_slides, 21)):
        print(f"📄 Slayd {i}/{num_slides} tayyorlanmoqda...")
        
        content = generate_slide_content(topic, i, num_slides)
        title = extract_title(content)
        points = extract_points(content)
        
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title
        slide.placeholders[1].text = points
        
        # Rasm qo'shish (faqat 1-10 slaydlarga, tezlik uchun)
        if i <= 10:  # 10 tagacha rasm qo'shamiz (API limiti uchun)
            img_data = generate_slide_image(topic, title)
            if img_data:
                with open(f"temp_slide_{i}.png", "wb") as f:
                    f.write(img_data)
                slide.shapes.add_picture(f"temp_slide_{i}.png", 
                                        Inches(6.5), Inches(1.2), 
                                        width=Inches(4.2), height=Inches(3.1))
                os.remove(f"temp_slide_{i}.png")
        
        # API limitiga duch kelmaslik uchun kichik kutish
        if i % 3 == 0:
            asyncio.sleep(0.5)
    
    # 4. Xulosa slaydi
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "XULOSA"
    slide.placeholders[1].text = f"• {topic} bo'yicha asosiy xulosalar\n• Kelajak istiqbollari\n• Savol-javoblar"
    
    filename = f"{topic.replace(' ', '_')}_{num_slides}slayd.pptx"
    prs.save(filename)
    print(f"✅ Taqdimot saqlandi: {filename}")
    return filename

# ========== TELEGRAM BOT ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 **Gemini Slayd Botiga Xush Kelibsiz!**\n\n"
        "📝 **Qanday ishlaydi:**\n"
        "1. Mavzuni yozing (masalan: 'Sun'iy intellekt')\n"
        "2. Slaydlar sonini tanlang (3 dan 20 gacha)\n"
        "3. Kuting va taqdimotni yuklab oling\n\n"
        "✨ Har bir slaydda:\n"
        "✅ Professional matn\n"
        "✅ Mos rasm (birinchi 10 slayd)\n"
        "✅ Chiroyli dizayn\n\n"
        "**Mavzuni yozing:**",
        parse_mode="Markdown"
    )

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text
    context.user_data['topic'] = topic
    
    # Slayd sonini tanlash tugmalari
    buttons = []
    row = []
    for i in range(3, 21, 2):
        row.append([InlineKeyboardButton(f"📊 {i} slayd", callback_data=str(i))])
        if len(row) == 3:
            buttons.extend(row)
            row = []
    if row:
        buttons.extend(row)
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await update.message.reply_text(
        f"✅ Mavzu: **{topic}**\n\nNecha slayd kerak?",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    num_slides = int(query.data)
    topic = context.user_data.get('topic', 'Taqdimot')
    
    await query.edit_message_text(
        f"⏳ **{topic}** - {num_slides} slayd tayyorlanmoqda...\n\n"
        f"📝 Matn yozilmoqda...\n"
        f"🎨 Rasm yaratilmoqda (1-10 slaydlar)...\n"
        f"⏱ Taxminan {num_slides * 3 // 2} daqiqa vaqt ketadi.\n\n"
        f"⚠️ Iltimos, kuting!",
        parse_mode="Markdown"
    )
    
    try:
        filename = create_full_presentation(topic, num_slides)
        
        # Fayl hajmini tekshirish
        file_size = os.path.getsize(filename) / (1024 * 1024)
        
        with open(filename, 'rb') as f:
            caption = f"✅ **Taqdimot tayyor!**\n\n"
            caption += f"📌 Mavzu: {topic}\n"
            caption += f"📊 Slaydlar: {num_slides}\n"
            caption += f"🎨 Rasmlar: 1-10 slaydlarda\n"
            caption += f"📦 Hajmi: {file_size:.1f} MB\n\n"
            caption += f"Gemini AI tomonidan yaratildi"
            
            await query.message.reply_document(
                document=f,
                filename=filename,
                caption=caption,
                parse_mode="Markdown"
            )
        
        os.remove(filename)
        
    except Exception as e:
        await query.message.reply_text(f"❌ Xatolik: {str(e)}\n\nQaytadan urunib ko'ring.")

def main():
    print("🤖 Slayd Bot ishga tushmoqda...")
    print(f"📝 Matn modeli: {TEXT_MODEL}")
    print(f"🎨 Rasm modeli: {IMAGE_MODEL}")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    app.add_handler(CallbackQueryHandler(handle_slide_count))
    
    print("✅ Bot ishga tushdi!")
    print("💡 Foydalanuvchi 3-20 slayd tanlashi mumkin")
    print("🎨 1-10 slaydlarga avtomatik rasm qo'shiladi")
    
    app.run_polling()

if __name__ == "__main__":
    main()
