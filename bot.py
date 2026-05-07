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

# ========== API KONFIGURATSIYASI ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
TEXT_MODEL = "gemini-2.0-flash-exp"  # yoki "gemini-2.0-flash"

# ========== 1. GEMINI ==========
def generate_slide_content(topic, slide_num, total_slides):
    prompt = f"""
    {topic} mavzusida {total_slides} slaydlik professional taqdimot tayyorla.
    {slide_num}-slayd uchun quyidagi formatda javob ber:

    TITLE: Qisqa va kuchli sarlavha (max 8-10 so'z)
    POINTS: nuqta1 | nuqta2 | nuqta3 | nuqta4
    IMAGE_PROMPT: Ushbu slayd uchun ingliz tilida yaxshi rasm prompti (FLUX uchun)

    Javobni faqat shu formatda ber, boshqa matn qo'shma.
    """

    try:
        response = gemini_client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=700
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini xatosi: {e}")
        return f"TITLE: {topic}\nPOINTS: Asosiy ma'lumot | Muhim faktlar | Misollar | Natija\nIMAGE_PROMPT: professional {topic} presentation slide"


def extract_title(content):
    for line in content.split('\n'):
        if line.startswith('TITLE:'):
            return line.replace('TITLE:', '').strip()
    return "Slayd"


def extract_points(content):
    for line in content.split('\n'):
        if line.startswith('POINTS:'):
            points = line.replace('POINTS:', '').strip()
            points_list = [p.strip() for p in points.split('|') if p.strip()]
            return '\n\n'.join([f"▸ {p}" for p in points_list])
    return "▸ Ma'lumotlar yuklanmoqda..."


def extract_image_prompt(content):
    for line in content.split('\n'):
        if line.startswith('IMAGE_PROMPT:'):
            return line.replace('IMAGE_PROMPT:', '').strip()
    return f"professional presentation slide about {topic}"


# ========== 2. REPLICATE (FLUX) ==========
def generate_image_replicate(prompt: str):
    if not REPLICATE_API_KEY:
        print("REPLICATE_API_KEY topilmadi!")
        return None

    headers = {
        "Authorization": f"Token {REPLICATE_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "input": {
            "prompt": prompt,
            "width": 1024,
            "height": 768,
            "num_outputs": 1,
            "num_inference_steps": 4,
        }
    }

    try:
        response = requests.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
            headers=headers,
            json=payload,
            timeout=40
        )

        if response.status_code != 201:
            print(f"Replicate error: {response.status_code} - {response.text}")
            return None

        prediction = response.json()
        get_url = prediction["urls"]["get"]

        for _ in range(25):
            status_resp = requests.get(get_url, headers=headers)
            data = status_resp.json()

            if data["status"] == "succeeded":
                return data["output"][0]
            elif data["status"] == "failed":
                print(f"FLUX failed: {data.get('error')}")
                return None

            asyncio.sleep(1.2)  # biroz kutamiz

        return None
    except Exception as e:
        print(f"Replicate umumiy xato: {e}")
        return None


def download_image(url, filename):
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(r.content)
            return True
    except Exception as e:
        print(f"Download xatosi: {e}")
    return False


# ========== 3. PPTX YARATISH ==========
async def create_presentation(topic, num_slides=5):
    print(f"🎯 '{topic}' uchun {num_slides} slayd tayyorlanmoqda...")

    prs = Presentation()

    # 1. Title Slide
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = topic.upper()

    img_url = generate_image_replicate(f"professional cover background for {topic} presentation")
    if img_url and download_image(img_url, "temp_cover.jpg"):
        try:
            slide.shapes.add_picture("temp_cover.jpg", Inches(0), Inches(1.5), 
                                   width=prs.slide_width, height=Inches(5))
            os.remove("temp_cover.jpg")
        except:
            pass

    # Asosiy slaydlar
    for i in range(1, num_slides + 1):
        print(f"   Slayd {i}/{num_slides}...")

        content = generate_slide_content(topic, i, num_slides)
        title = extract_title(content)
        points = extract_points(content)
        image_prompt = extract_image_prompt(content)

        slide = prs.slides.add_slide(prs.slide_layouts[5])  # Title + Content

        # Title
        if slide.shapes.title:
            slide.shapes.title.text = title
            slide.shapes.title.text_frame.paragraphs[0].font.size = Pt(32)
            slide.shapes.title.text_frame.paragraphs[0].font.bold = True

        # Content
        for shape in slide.shapes:
            if shape.has_text_frame and not shape == slide.shapes.title:
                shape.text = points
                break

        # Rasm
        img_url = generate_image_replicate(image_prompt)
        if img_url and download_image(img_url, f"temp_{i}.jpg"):
            try:
                left = Inches(6.8)
                top = Inches(1.5)
                slide.shapes.add_picture(f"temp_{i}.jpg", left, top, 
                                       width=Inches(4.2), height=Inches(3.8))
                os.remove(f"temp_{i}.jpg")
            except Exception as e:
                print(f"Rasm qo'shishda xato: {e}")

        await asyncio.sleep(0.5)  # API limitlarni chetlab o'tish uchun

    # Xulosa slaydi
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "XULOSA VA TAVSIYALAR"
    if len(slide.placeholders) > 1:
        slide.placeholders[1].text = f"{topic} bo‘yicha asosiy xulosalar va amaliy tavsiyalar."

    filename = f"{topic.replace(' ', '_')[:50]}.pptx"
    prs.save(filename)
    return filename


# ========== TELEGRAM HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎨 **AI Slayd Generatori**\n\n"
        "Mavzuni yozing, men Gemini + FLUX bilan chiroyli taqdimot tayyorlayman.",
        parse_mode="Markdown"
    )


async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    context.user_data['topic'] = topic

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("3 slayd", callback_data="3"),
         InlineKeyboardButton("5 slayd", callback_data="5")],
        [InlineKeyboardButton("7 slayd", callback_data="7"),
         InlineKeyboardButton("10 slayd", callback_data="10")]
    ])

    await update.message.reply_text(
        f"✅ **Mavzu qabul qilindi:** {topic}\n\nQancha slayd kerak?",
        reply_markup=keyboard
    )


async def handle_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    num_slides = int(query.data)
    topic = context.user_data.get('topic', 'Taqdimot')

    await query.edit_message_text(f"⏳ **{topic}** uchun {num_slides} slayd tayyorlanmoqda...\n\nAI ishlamoqda...")

    try:
        filename = await create_presentation(topic, num_slides)

        with open(filename, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ **Tayyor!**\n\n📌 {topic}\n📊 {num_slides} slayd\n🎨 FLUX rasmlari bilan"
            )
        os.remove(filename)
    except Exception as e:
        print(f"Umumiy xatolik: {e}")
        await query.edit_message_text(f"❌ Xatolik yuz berdi: {str(e)[:150]}")


def main():
    print("🤖 Slayd Bot ishga tushmoqda...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    app.add_handler(CallbackQueryHandler(handle_slide_count))

    print("✅ Bot muvaffaqiyatli ishga tushdi!")
    app.run_polling()


if __name__ == "__main__":
    main()
