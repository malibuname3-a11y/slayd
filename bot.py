import os
import asyncio
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

# ================== API SOZLAMALARI ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

TEXT_MODEL = "gemini-2.0-flash"
IMAGE_MODEL = "imagen-4.0-generate-001"

# ================== SLAYD MATNI YARATISH ==================
def generate_slide_content(topic, slide_num, total_slides):
    prompt = f"""
    {topic} mavzusida {total_slides} slaydlik professional PowerPoint taqdimoti tayyorla.
    {slide_num}-slayd uchun quyidagi formatda javob ber:

    TITLE: Qisqa va kuchli sarlavha
    POINTS: nuqta1 | nuqta2 | nuqta3 | nuqta4
    IMAGE_PROMPT: Ushbu slayd uchun ingliz tilida chiroyli va professional rasm prompti

    Faqat shu 3 qatorda javob ber.
    """

    try:
        response = gemini_client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.75, max_output_tokens=700)
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini matn xatosi: {e}")
        return f"TITLE: {topic} - Slayd {slide_num}\nPOINTS: Asosiy ma'lumot | Muhim jihatlar | Afzalliklar | Natijalar\nIMAGE_PROMPT: modern professional presentation about {topic}"


def extract_title(content):
    for line in content.splitlines():
        if "TITLE:" in line:
            return line.split("TITLE:", 1)[1].strip()
    return "Sarlavha"

def extract_points(content):
    for line in content.splitlines():
        if "POINTS:" in line:
            points = line.split("POINTS:", 1)[1].strip()
            pts = [p.strip() for p in points.split("|") if p.strip()]
            return "\n\n".join([f"▸ {p}" for p in pts])
    return "▸ Ma'lumotlar"

def extract_image_prompt(content):
    for line in content.splitlines():
        if "IMAGE_PROMPT:" in line:
            return line.split("IMAGE_PROMPT:", 1)[1].strip()
    return f"professional modern business presentation slide about {topic}"


# ================== RASM YARATISH ==================
async def generate_image_gemini(prompt: str):
    try:
        print(f"   🎨 Rasm yaratilmoqda...")

        response = gemini_client.models.generate_images(
            model=IMAGE_MODEL,
            prompt=prompt + ", high quality, clean, professional, modern style, presentation slide",
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/png"
            )
        )

        if response.generated_images:
            img = response.generated_images[0].image
            img_bytes = BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            print("   ✅ Rasm tayyor!")
            return img_bytes
    except Exception as e:
        print(f"   ❌ Rasm yaratish xatosi: {e}")
    return None


# ================== POWERPOINT YARATISH ==================
async def create_presentation(topic, num_slides=10):
    print(f"🚀 {topic} — {num_slides} slayd boshlandi...")
    prs = Presentation()

    # 1. Bosh sahifa
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = topic.upper()

    for i in range(1, num_slides + 1):
        print(f"   Slayd {i}/{num_slides} ...")

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

        # Rasm qo'shish
        img_bytes = await generate_image_gemini(image_prompt)
        if img_bytes:
            try:
                slide.shapes.add_picture(img_bytes, Inches(6.0), Inches(1.5), 
                                       width=Inches(5.0), height=Inches(4.0))
                print("   ✅ Rasm qo'shildi")
            except Exception as e:
                print(f"   Rasm qo'shishda xato: {e}")

        await asyncio.sleep(7)  # Rate limit

    # Xulosa slaydi
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "XULOSA VA TAVSIYALAR"

    filename = f"{topic.replace(' ', '_')[:50]}.pptx"
    prs.save(filename)
    print(f"✅ Taqdimot saqlandi: {filename}")
    return filename


# ================== TELEGRAM BOT ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎨 **Gemini AI Slayd Bot**\n\n"
        "Mavzuni yozing, men har bir slaydga rasm bilan taqdimot tayyorlayman.",
        parse_mode="Markdown"
    )

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    context.user_data['topic'] = topic

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("5 slayd", callback_data="5"), InlineKeyboardButton("10 slayd", callback_data="10")],
        [InlineKeyboardButton("15 slayd", callback_data="15"), InlineKeyboardButton("20 slayd", callback_data="20")]
    ])

    await update.message.reply_text(f"✅ **Mavzu:** {topic}\n\nQancha slayd kerak?", reply_markup=keyboard)

async def handle_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    num_slides = int(query.data)
    topic = context.user_data.get('topic', 'Taqdimot')

    await query.edit_message_text(f"⏳ **{topic}**\n{num_slides} slayd tayyorlanmoqda...\nRasm yaratish biroz vaqt oladi.")

    try:
        filename = await create_presentation(topic, num_slides)
        
        with open(filename, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ **Tayyor!**\n\n📌 {topic}\n📊 {num_slides} slayd\n🎨 Gemini rasmlari bilan"
            )
        os.remove(filename)
    except Exception as e:
        print(f"Xatolik: {e}")
        await query.edit_message_text(f"❌ Xatolik yuz berdi: {str(e)[:200]}")


def main():
    print("🚀 Slayd Bot ishga tushmoqda...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    app.add_handler(CallbackQueryHandler(handle_slide_count))

    print("✅ Bot muvaffaqiyatli ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
