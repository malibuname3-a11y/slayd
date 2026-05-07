import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from google import genai
from google.genai import types

# ========== KONFIGURATSIYA ==========
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("❌ Kalitlarni tekshiring! .env faylini sozlang.")
    print("TELEGRAM_BOT_TOKEN va GEMINI_API_KEY ni kiriting.")
    exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# ========== MODELLAR ==========
TEXT_MODEL = "gemini-2.0-flash"
IMAGE_MODEL = "gemini-2.5-flash-image"

# Foydalanuvchi ma'lumotlari
user_data = {}

# ========== MATN YARATISH ==========
def generate_slide_content(topic, slide_num, total_slides):
    """Gemini orqali slayd matnini yaratish"""
    prompt = f"""
    {topic} mavzusida {total_slides} slaydlik professional taqdimot.
    {slide_num}-slayd uchun:
    
    1. TITLE: Qisqa, aniq sarlavha (10 so'zgacha)
    2. POINTS: 4 ta asosiy nuqta
    
    Format (aynan shu formatda javob ber, boshqa so'z qo'shma):
    TITLE: sarlavha
    POINTS: nuqta1 | nuqta2 | nuqta3 | nuqta4
    """
    
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=300
            )
        )
        return response.text
    except Exception as e:
        print(f"Matn xatosi: {e}")
        return f"TITLE: {topic} - {slide_num}-slayd\nPOINTS: Kirish | Asosiy qism | Muhim jihatlar | Xulosa"

def extract_title(content):
    """Matndan sarlavhani olish"""
    for line in content.split('\n'):
        if line.startswith('TITLE:'):
            return line.replace('TITLE:', '').strip()
    return "Asosiy mavzu"

def extract_points(content):
    """Matndan nuqtalarni olish"""
    for line in content.split('\n'):
        if line.startswith('POINTS:'):
            points = line.replace('POINTS:', '').strip()
            points_list = [p.strip() for p in points.split('|')]
            formatted = '\n• '.join(points_list)
            return f"• {formatted}"
    return f"• {content[:200]}"

# ========== RASM YARATISH ==========
def generate_slide_image(topic, slide_title):
    """Gemini orqali slaydga mos rasm yaratish"""
    image_prompt = f"Professional presentation background image about {topic} - {slide_title}. Modern, clean, business style. No text, just visual."
    
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=image_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.8
            )
        )
        
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        return part.inline_data.data
        return None
    except Exception as e:
        print(f"Rasm xatosi: {e}")
        return None

# ========== POWERPOINT YARATISH ==========
def create_presentation(topic, num_slides=5):
    """To'liq PowerPoint taqdimotini yaratish"""
    print(f"📝 '{topic}' - {num_slides} slayd yaratilmoqda...")
    
    prs = Presentation()
    
    # 1. Sarlavha slaydi
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = topic.upper()
    if slide.placeholders[1]:
        slide.placeholders[1].text = f"AI tomonidan tayyorlangan taqdimot\n{num_slides} slayd"
    
    # Sarlavhaga rasm qo'shish
    img_data = generate_slide_image(topic, "cover")
    if img_data:
        try:
            with open("temp_cover.png", "wb") as f:
                f.write(img_data)
            slide.shapes.add_picture("temp_cover.png", Inches(0), Inches(3), 
                                    width=prs.slide_width, height=Inches(3))
            os.remove("temp_cover.png")
        except:
            pass
    
    # 2. Mundarija (agar 7+ slayd bo'lsa)
    if num_slides >= 7:
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = "MUNDARIJA"
        body = slide.placeholders[1]
        body.text = "• Taqdimot mazmuni\n• Asosiy bo'limlar\n• Qo'shimcha ma'lumotlar\n• Xulosa"
    
    # 3. Asosiy slaydlar
    for i in range(1, num_slides + 1):
        print(f"  Slayd {i}/{num_slides}...")
        
        # Matn yaratish
        content = generate_slide_content(topic, i, num_slides)
        title = extract_title(content)
        points = extract_points(content)
        
        # Slayd qo'shish
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title
        slide.placeholders[1].text = points
        
        # Rasm qo'shish (birinchi 8 slaydga)
        if i <= 8:
            img_data = generate_slide_image(topic, title)
            if img_data:
                try:
                    with open(f"temp_slide_{i}.png", "wb") as f:
                        f.write(img_data)
                    slide.shapes.add_picture(f"temp_slide_{i}.png", 
                                            Inches(6.5), Inches(1.2), 
                                            width=Inches(4), height=Inches(3))
                    os.remove(f"temp_slide_{i}.png")
                except:
                    pass
        
        # API limiti uchun kichik pauza
        asyncio.sleep(0.3)
    
    # 4. Xulosa slaydi
    if num_slides >= 3:
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = "XULOSA"
        slide.placeholders[1].text = f"• {topic} bo'yicha asosiy xulosalar\n• Muhim tavsiyalar\n• Kelajak rejalari\n• Savol-javoblar"
    
    filename = f"{topic.replace(' ', '_')}_{num_slides}slayd.pptx"
    prs.save(filename)
    print(f"✅ Taqdimot saqlandi: {filename}")
    return filename

# ========== TELEGRAM BOT ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start buyrug'i"""
    await update.message.reply_text(
        "🎉 **Gemini Slayd Botiga Xush Kelibsiz!**\n\n"
        "📝 Mavzu yozing, men sizga:\n"
        "✅ Professional matnli taqdimot\n"
        "✅ Har bir slaydga mos rasm\n"
        "✅ PowerPoint (.pptx) faylini tayyorlab beraman\n\n"
        "**Masalan:** Sun'iy intellekt, Marketing strategiyasi, Ekologiya\n\n"
        "✏️ Mavzuni yozing:",
        parse_mode="Markdown"
    )

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi mavzu yozganda"""
    topic = update.message.text
    user_id = update.effective_user.id
    user_data[user_id] = {"topic": topic}
    
    # Slayd sonini tanlash tugmalari
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 3 slayd", callback_data="3"),
         InlineKeyboardButton("📈 5 slayd", callback_data="5")],
        [InlineKeyboardButton("📚 7 slayd", callback_data="7"),
         InlineKeyboardButton("🎨 10 slayd", callback_data="10")],
        [InlineKeyboardButton("🏆 15 slayd", callback_data="15"),
         InlineKeyboardButton("🌟 20 slayd", callback_data="20")]
    ])
    
    await update.message.reply_text(
        f"✅ Mavzu: **{topic}**\n\nNecha slayd kerak?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def handle_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi slayd sonini tanlaganda"""
    query = update.callback_query
    
    try:
        await query.answer()
        
        num_slides = int(query.data)
        user_id = query.from_user.id
        topic = user_data.get(user_id, {}).get("topic", "Taqdimot")
        
        # "Yozilmoqda" xabarini tahrirlash
        await query.edit_message_text(
            f"⏳ **{topic}** - {num_slides} slayd tayyorlanmoqda...\n\n"
            f"📝 Matn yozilmoqda...\n"
            f"🎨 Rasmlar yaratilmoqda...\n"
            f"⏱ Taxminan 1-2 daqiqa vaqt ketadi.\n\n"
            f"⚠️ Iltimos, kuting...",
            parse_mode="Markdown"
        )
        
        # Taqdimot yaratish
        filename = create_presentation(topic, num_slides)
        
        # Faylni jo'natish
        with open(filename, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ **Taqdimot tayyor!**\n\n"
                       f"📌 Mavzu: {topic}\n"
                       f"📊 Slaydlar: {num_slides}\n"
                       f"🎨 Rasmlar: Birinchi 8 slaydda\n\n"
                       f"🤖 Gemini AI tomonidan yaratildi",
                parse_mode="Markdown"
            )
        
        # Faylni o'chirish
        os.remove(filename)
        
        # Keyingi taqdimot uchun
        await query.message.reply_text(
            "🔄 Yana taqdimot tayyorlash uchun /start bosing yoki mavzu yozing."
        )
        
    except Exception as e:
        print(f"Xatolik: {e}")
        try:
            await query.edit_message_text(
                f"❌ Xatolik yuz berdi: {str(e)[:200]}\n\n"
                f"Qaytadan urunib ko'ring yoki boshqa mavzu yozing."
            )
        except:
            await query.message.reply_text(
                f"❌ Xatolik yuz berdi. Qayta uruning."
            )

# ========== MAIN ==========
def main():
    print("🤖 Gemini Slayd Bot ishga tushmoqda...")
    print(f"📝 Matn modeli: {TEXT_MODEL}")
    print(f"🎨 Rasm modeli: {IMAGE_MODEL}")
    
    # Botni yaratish
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlerlarni qo'shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    app.add_handler(CallbackQueryHandler(handle_slide_count))
    
    print("✅ Bot ishga tushdi!")
    print("💡 Telegram'da @BotFather dan olgan bot username ni toping")
    print("💬 Botga xabar yuborib sinab ko'ring\n")
    
    # Botni ishga tushirish
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
