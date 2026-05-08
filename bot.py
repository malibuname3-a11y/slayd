import logging
import os
import json
import tempfile
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Tokenni o'zingizning bot tokeningiz bilan almashtiring
BOT_TOKEN = "BOT_TOKEN"

# Conversation states
TITLE, SLIDE_COUNT, SLIDE_CONTENT, SLIDE_IMAGE, CONFIRM = range(5)

# Foydalanuvchi ma'lumotlarini saqlash
user_data: Dict[int, dict] = {}

# HTML5 Presentation template (reveal.js)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/reveal.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/theme/white.min.css">
    <style>
        .reveal {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        .reveal h1, .reveal h2, .reveal h3 {{
            color: #2c3e50;
            text-transform: none;
            font-weight: 600;
        }}
        .reveal p {{
            color: #34495e;
            line-height: 1.6;
        }}
        .reveal .slides section {{
            padding: 20px;
        }}
        .reveal img {{
            max-height: 400px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .reveal .progress {{
            background: #3498db;
        }}
        .reveal .controls {{
            color: #3498db;
        }}
        .slide-number {{
            background: #3498db;
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="reveal">
        <div class="slides">
            {slides}
        </div>
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/reveal.min.js"></script>
    <script>
        Reveal.initialize({{
            hash: true,
            slideNumber: 'c/t',
            transition: 'slide',
            width: 1200,
            height: 700,
            margin: 0.1
        }});
    </script>
</body>
</html>"""

SLIDE_TEMPLATE = """
<section>
    <h2>{title}</h2>
    <p>{content}</p>
    {image}
</section>
"""

TITLE_SLIDE_TEMPLATE = """
<section>
    <h1>{title}</h1>
    <p style="font-size: 1.2em; color: #7f8c8d;">Taqdimot</p>
    <p style="font-size: 0.9em; margin-top: 40px;">{date}</p>
</section>
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Botni ishga tushirish va taqdimot sarlavhasini so'rash"""
    user_id = update.effective_user.id
    user_data[user_id] = {
        'title': '',
        'slide_count': 0,
        'current_slide': 0,
        'slides': [],
        'images': {},
        'temp_dir': tempfile.mkdtemp()
    }

    await update.message.reply_text(
        "🎉 *Telegram Taqdimot Yaratuvchi Botiga Xush Kelibsiz!*\n\n"
        "Bu bot orqali professional HTML5 taqdimotlar yaratishingiz mumkin.\n\n"
        "Taqdimotingiz sarlavhasini kiriting:",
        parse_mode='Markdown'
    )
    return TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Taqdimot sarlavhasini qabul qilish"""
    user_id = update.effective_user.id
    title = update.message.text.strip()

    if not title or len(title) > 100:
        await update.message.reply_text(
            "❌ Noto'g'ri sarlavha. Iltimos, 1-100 ta belgi orasida sarlavha kiriting."
        )
        return TITLE

    user_data[user_id]['title'] = title

    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(6, 11)],
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(11, 16)],
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(16, 21)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ Sarlavha: *{title}*\n\n"
        f"📊 Nechta slayd kerak? (1-20)",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return SLIDE_COUNT

async def get_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Slaydlar sonini qabul qilish"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    count = int(query.data)
    user_data[user_id]['slide_count'] = count
    user_data[user_id]['current_slide'] = 1

    await query.edit_message_text(
        f"✅ Slaydlar soni: *{count}*\n\n"
        f"📝 *1-slayd* ma'lumotlarini kiriting.\n\n"
        f"Sarlavha va matnni quyidagi formatda yuboring:\n"
        f"`Sarlavha | Matn`\n\n"
        f"Masalan:\n"
        f"`Kirish | Bu slayd kirish qismi haqida`",
        parse_mode='Markdown'
    )
    return SLIDE_CONTENT

async def get_slide_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Slayd matnini qabul qilish va rasm so'rash"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if '|' not in text:
        await update.message.reply_text(
            "❌ Noto'g'ri format. Iltimos, `Sarlavha | Matn` formatida kiriting.",
            parse_mode='Markdown'
        )
        return SLIDE_CONTENT

    parts = text.split('|', 1)
    slide_title = parts[0].strip()
    slide_content = parts[1].strip()

    current = user_data[user_id]['current_slide']
    user_data[user_id]['slides'].append({
        'title': slide_title,
        'content': slide_content,
        'has_image': False
    })

    keyboard = [
        [InlineKeyboardButton("✅ Ha", callback_data="yes")],
        [InlineKeyboardButton("❌ Yo'q", callback_data="no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ *{current}-slayd* saqlandi.\n\n"
        f"Bu slaydga rasm qo'shmoqchimisiz?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return SLIDE_IMAGE

async def handle_slide_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Slayd rasmini qabul qilish yoki o'tkazib yuborish"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    current = user_data[user_id]['current_slide']
    total = user_data[user_id]['slide_count']

    if query.data == "yes":
        await query.edit_message_text(
            f"📤 *{current}-slayd* uchun rasm yuboring (foto yoki hujjat sifatida)."
        )
        return SLIDE_IMAGE
    else:
        user_data[user_id]['current_slide'] += 1

        if user_data[user_id]['current_slide'] > total:
            return await finish_presentation(update, context)

        next_slide = user_data[user_id]['current_slide']
        await query.edit_message_text(
            f"📝 *{next_slide}-slayd* ma'lumotlarini kiriting.\n\n"
            f"`Sarlavha | Matn` formatida yuboring:",
            parse_mode='Markdown'
        )
        return SLIDE_CONTENT

async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Rasmni qabul qilish va saqlash"""
    user_id = update.effective_user.id
    current = user_data[user_id]['current_slide']
    total = user_data[user_id]['slide_count']

    try:
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await photo.get_file()
        elif update.message.document:
            file = await update.message.document.get_file()
        else:
            await update.message.reply_text("❌ Iltimos, rasm yuboring.")
            return SLIDE_IMAGE

        # Rasmni saqlash
        temp_dir = user_data[user_id]['temp_dir']
        image_path = os.path.join(temp_dir, f"slide_{current}.jpg")
        await file.download_to_drive(image_path)

        user_data[user_id]['slides'][current - 1]['has_image'] = True
        user_data[user_id]['images'][current] = image_path

        user_data[user_id]['current_slide'] += 1

        if user_data[user_id]['current_slide'] > total:
            return await finish_presentation(update, context)

        next_slide = user_data[user_id]['current_slide']
        await update.message.reply_text(
            f"✅ Rasm saqlandi.\n\n"
            f"📝 *{next_slide}-slayd* ma'lumotlarini kiriting.\n\n"
            f"`Sarlavha | Matn` formatida yuboring:",
            parse_mode='Markdown'
        )
        return SLIDE_CONTENT

    except Exception as e:
        logger.error(f"Rasm yuklashda xatolik: {e}")
        await update.message.reply_text(
            "❌ Rasmni yuklashda xatolik. Iltimos, qayta urinib ko'ring."
        )
        return SLIDE_IMAGE

async def finish_presentation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Taqdimotni yaratish va yuborish"""
    user_id = update.effective_user.id
    data = user_data[user_id]

    try:
        # HTML fayl yaratish
        temp_dir = data['temp_dir']
        html_path = os.path.join(temp_dir, "presentation.html")

        slides_html = ""

        # Title slide
        slides_html += TITLE_SLIDE_TEMPLATE.format(
            title=data['title'],
            date=datetime.now().strftime("%d.%m.%Y")
        )

        # Content slides
        for i, slide in enumerate(data['slides'], 1):
            image_html = ""
            if slide.get('has_image') and i in data['images']:
                # Rasmni base64 kodlash yoki nisbiy yo'l
                image_name = f"slide_{i}.jpg"
                image_html = f'<img src="{image_name}" alt="Slide {i}" style="max-width:80%;">'

            slides_html += SLIDE_TEMPLATE.format(
                title=slide['title'],
                content=slide['content'],
                image=image_html
            )

        # To'liq HTML
        final_html = HTML_TEMPLATE.format(
            title=data['title'],
            slides=slides_html
        )

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(final_html)

        # ZIP arxiv yaratish (HTML + rasmlar)
        import zipfile
        zip_path = os.path.join(temp_dir, "presentation.zip")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(html_path, "presentation.html")
            for i, img_path in data['images'].items():
                if os.path.exists(img_path):
                    zipf.write(img_path, f"slide_{i}.jpg")

        # ZIP faylni yuborish
        with open(zip_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(f, filename=f"{data['title']}.zip"),
                caption=f"✅ *{data['title']}* taqdimoti tayyor!\n\n"
                        f"📊 Slaydlar soni: {data['slide_count']}\n"
                        f"📁 ZIP faylni yuklab oling va `presentation.html` ni brauzerda oching.\n\n"
                        f"_Taqdimot reveal.js yordamida yaratildi._",
                parse_mode='Markdown'
            )

        # Tozalash
        cleanup_user_data(user_id)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎉 Taqdimot muvaffaqiyatli yaratildi!\n"
                 "Yangi taqdimot yaratish uchun /start ni bosing."
        )

    except Exception as e:
        logger.error(f"Taqdimot yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Taqdimot yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
        )
        cleanup_user_data(user_id)

    return ConversationHandler.END

def cleanup_user_data(user_id: int):
    """Foydalanuvchi ma'lumotlarini tozalash"""
    if user_id in user_data:
        temp_dir = user_data[user_id].get('temp_dir', '')
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        del user_data[user_id]

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bekor qilish"""
    user_id = update.effective_user.id
    cleanup_user_data(user_id)

    await update.message.reply_text(
        "❌ Bekor qilindi. Yangi taqdimot uchun /start ni bosing."
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam buyrug'i"""
    await update.message.reply_text(
        "🤖 *Telegram Taqdimot Boti - Yordam*\n\n"
        "*Buyruqlar:*\n"
        "/start - Yangi taqdimot yaratish\n"
        "/cancel - Jarayonni bekor qilish\n"
        "/help - Bu yordam xabari\n\n"
        "*Qo'llanma:*\n"
        "1. Botga /start yuboring\n"
        "2. Taqdimot sarlavhasini kiriting\n"
        "3. Slaydlar sonini tanlang (1-20)\n"
        "4. Har bir slayd uchun `Sarlavha | Matn` formatida ma'lumot kiriting\n"
        "5. Ixtiyoriy ravishda rasm qo'shing\n"
        "6. Tayyor taqdimotni ZIP fayl sifatida yuklab oling\n\n"
        "*Eslatma:* Taqdimot HTML5 formatida (reveal.js) yaratiladi.",
        parse_mode='Markdown'
    )

def main():
    """Botni ishga tushirish"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            SLIDE_COUNT: [CallbackQueryHandler(get_slide_count, pattern='^\d+$')],
            SLIDE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_slide_content)],
            SLIDE_IMAGE: [
                CallbackQueryHandler(handle_slide_image, pattern='^(yes|no)$'),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_image)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))

    print("Bot ishga tushdi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
