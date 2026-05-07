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
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")  # Yangi!

# ========== API MIJOZLARI ==========
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
TEXT_MODEL = "gemini-2.0-flash"

# ========== 1. GEMINI: SLAYD MATNINI YARATISH ==========
def generate_slide_content(topic, slide_num, total_slides):
    """Gemini orqali slayd matnini yaratish"""
    prompt = f"""
    {topic} mavzusida {total_slides} slaydlik professional taqdimot.
    {slide_num}-slayd uchun:
    
    1. TITLE: Qisqa, aniq sarlavha (10 so'zgacha)
    2. POINTS: 4 ta qisqa, mazmunli nuqta
    3. IMAGE_PROMPT: Shu slayd mavzusiga mos rasm yaratish uchun qisqa prompt (20 so'zgacha)
    
    Qat'iy format:
    TITLE: sarlavha matni
    POINTS: nuqta1 | nuqta2 | nuqta3 | nuqta4
    IMAGE_PROMPT: rasm yaratish uchun prompt
    """
    
    try:
        response = gemini_client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.85,
                max_output_tokens=600
            )
        )
        return response.text
    except Exception as e:
        print(f"Matn xatosi: {e}")
        return f"TITLE: {topic}\nPOINTS: Kirish | Asosiy qism | Muhim jihatlar | Xulosa\nIMAGE_PROMPT: {topic} professional background"

def extract_title(content):
    for line in content.split('\n'):
        if line.startswith('TITLE:'):
            return line.replace('TITLE:', '').strip()
    return topic

def extract_points(content):
    for line in content.split('\n'):
        if line.startswith('POINTS:'):
            points = line.replace('POINTS:', '').strip()
            points_list = [p.strip() for p in points.split('|')]
            return '\n\n'.join([f"▸ {p}" for p in points_list])
    return "▸ Kirish\n\n▸ Asosiy qism\n\n▸ Xulosa"

def extract_image_prompt(content):
    for line in content.split('\n'):
        if line.startswith('IMAGE_PROMPT:'):
            return line.replace('IMAGE_PROMPT:', '').strip()
    return f"{topic} professional presentation background"

# ========== 2. REPLICATE: RASM YARATISH ==========
def generate_image_replicate(prompt):
    """Replicate API orqali rasm yaratish"""
    if not REPLICATE_API_KEY:
        return None
    
    # FLUX modeli - eng yaxshi sifatli bepul variant
    model = "black-forest-labs/flux-schnell"
    
    headers = {
        "Authorization": f"Token {REPLICATE_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "version": model,
        "input": {
            "prompt": prompt,
            "width": 1024,
            "height": 768,
            "num_outputs": 1,
            "num_inference_steps": 4,
            "guidance_scale": 0,
        }
    }
    
    try:
        # 1. Prediksiyani boshlash
        response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 201:
            print(f"Replicate start error: {response.status_code}")
            return None
        
        prediction = response.json()
        get_url = prediction["urls"]["get"]
        
        # 2. Natijani kutish
        for _ in range(30):  # maksimal 30 soniya kutish
            status_response = requests.get(get_url, headers=headers)
            status_data = status_response.json()
            
            if status_data["status"] == "succeeded":
                return status_data["output"][0]
            elif status_data["status"] == "failed":
                print(f"Replicate failed: {status_data.get('error')}")
                return None
            
            asyncio.sleep(1)
        
        return None
    except Exception as e:
        print(f"Rasm yaratish xatosi: {e}")
        return None

def download_image(url, filename):
    """Rasmni yuklab olish"""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Yuklash xatosi: {e}")
    return False

# ========== 3. POWERPOINT YARATISH ==========
def create_presentation(topic, num_slides=5):
    """Gemini matni + Replicate rasmlari bilan taqdimot yaratish"""
    print(f"📝 '{topic}' - {num_slides} slayd...")
    
    prs = Presentation()
    
    # Sarlavha slaydi
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = topic.upper()
    if slide.placeholders[1]:
        slide.placeholders[1].text = ""
    
    # Sarlavha uchun rasm
    img_url = generate_image_replicate(f"{topic} professional cover background")
    if img_url and download_image(img_url, "temp_cover.jpg"):
        try:
            slide.shapes.add_picture("temp_cover.jpg", Inches(0), Inches(2.5), 
                                    width=prs.slide_width, height=Inches(3.5))
            os.remove("temp_cover.jpg")
        except:
            pass
    
    # Asosiy slaydlar
    for i in range(1, num_slides + 1):
        print(f"  Slayd {i}...")
        
        content = generate_slide_content(topic, i, num_slides)
        title = extract_title(content)
        points = extract_points(content)
        image_prompt = extract_image_prompt(content)
        
        slide_layout = prs.slide_layouts[5]
        slide = prs.slides.add_slide(slide_layout)
        
        if slide.shapes.title:
            slide.shapes.title.text = title
            slide.shapes.title.text_frame.paragraphs[0].font.size = Pt(28)
            slide.shapes.title.text_frame.paragraphs[0].font.bold = True
        
        for shape in slide.shapes:
            if shape.has_text_frame:
                shape.text = points
                break
        
        # Rasm yaratish va qo'shish
        print(f"    Rasm yaratilmoqda: '{image_prompt[:50]}...'")
        img_url = generate_image_replicate(image_prompt)
        
        if img_url and download_image(img_url, f"temp_slide_{i}.jpg"):
            try:
                slide.shapes.add_picture(f"temp_slide_{i}.jpg", 
                                        Inches(6.5), Inches(1.2), 
                                        width=Inches(4.5), height=Inches(3.2))
                os.remove(f"temp_slide_{i}.jpg")
                print(f"    ✅ Rasm qo'shildi")
            except Exception as e:
                print(f"    Rasm qo'shish xatosi: {e}")
        else:
            print(f"    ⚠️ Rasm yaratilmadi")
        
        await asyncio.sleep(0.2)
    
    # Xulosa slaydi
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "XULOSA"
    slide.placeholders[1].text = f"▸ {topic} bo'yicha asosiy xulosalar\n\n▸ Kelajak istiqbollari\n\n▸ Amaliy tavsiyalar"
    
    filename = f"{topic.replace(' ', '_')}.pptx"
    prs.save(filename)
    print(f"✅ Tayyor: {filename}")
    return filename

# ========== TELEGRAM BOT ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 **Professional Slayd Bot**\n\n"
        "Gemini → Matn yozadi\n"
        "Replicate → Rasm yaratadi\n\n"
        "📌 Mavzuni yozing:",
        parse_mode="Markdown"
    )

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text
    context.user_data['topic'] = topic
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("3 slayd", callback_data="3"),
         InlineKeyboardButton("5 slayd", callback_data="5")],
        [InlineKeyboardButton("7 slayd", callback_data="7"),
         InlineKeyboardButton("10 slayd", callback_data="10")],
        [InlineKeyboardButton("15 slayd", callback_data="15"),
         InlineKeyboardButton("20 slayd", callback_data="20")]
    ])
    
    await update.message.reply_text(
        f"✅ Mavzu: {topic}\n\nNecha slayd kerak?",
        reply_markup=keyboard
    )

async def handle_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    num_slides = int(query.data)
    topic = context.user_data.get('topic', 'Taqdimot')
    
    await query.edit_message_text(
        f"⏳ {topic} - {num_slides} slayd tayyorlanmoqda...\n\n"
        f"📝 Matn yozilmoqda (Gemini)...\n"
        f"🎨 Rasmlar yaratilmoqda (Replicate FLUX)...\n"
        f"⏱ Bu 2-3 daqiqa vaqt oladi."
    )
    
    try:
        filename = create_presentation(topic, num_slides)
        
        with open(filename, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ **Tayyor!**\n\n📌 {topic}\n📊 {num_slides} slayd\n🎨 Har bir slaydda original AI rasm"
            )
        
        os.remove(filename)
    except Exception as e:
        print(f"Xatolik: {e}")
        await query.edit_message_text(f"❌ Xatolik: {str(e)[:200]}\n\nQaytadan uruning.")

def main():
    print("🤖 Bot ishga tushmoqda...")
    print(f"📝 Matn modeli: {TEXT_MODEL}")
    print(f"🎨 Image API: Replicate (FLUX Schnell)")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    app.add_handler(CallbackQueryHandler(handle_slide_count))
    
    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
