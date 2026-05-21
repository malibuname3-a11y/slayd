import telebot
from instagrapi import Client
from collections import defaultdict, Counter
import json
import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# ================== AVTOMATIK O'QISH ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
INSTA_USERNAME = os.getenv("INSTA_USERNAME")
INSTA_PASSWORD = os.getenv("INSTA_PASSWORD")
CURRENT_POST_URL = os.getenv("POST_URL")

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN topilmadi! .env faylini tekshiring.")
    exit()

bot = telebot.TeleBot(TELEGRAM_TOKEN)
cl = Client()

# ================== LOGIN ==================
def instagram_login():
    try:
        cl.login(INSTA_USERNAME, INSTA_PASSWORD)
        print("✅ Instagramga muvaffaqiyatli kirdik!")
        return True
    except Exception as e:
        print(f"❌ Login xatosi: {e}")
        return False

instagram_login()

# ================== KOMANDALAR ==================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
        "👋 Ishxona Instagram Statistikasi Boti\n\n"
        "/stats — Like va Comment userlarini ko'rish\n"
        "/setpost — Yangi post havolasini yuborish")

@bot.message_handler(commands=['setpost'])
def set_post(message):
    global CURRENT_POST_URL
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        CURRENT_POST_URL = url
        bot.reply_to(message, f"✅ Post yangilandi:\n{CURRENT_POST_URL}")
    except:
        bot.reply_to(message, "❌ /setpost https://www.instagram.com/p/....")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not CURRENT_POST_URL:
        bot.reply_to(message, "❌ Avval /setpost orqali post/video havolasini yuboring!")
        return

    status = bot.send_message(message.chat.id, "⏳ Ma'lumot yuklanmoqda... Iltimos kuting.")

    try:
        media_pk = cl.media_pk_from_url(CURRENT_POST_URL)
        media = cl.media_info(media_pk).dict()

        # Like bosganlar
        likers = cl.media_likers(media_pk)
        liker_usernames = [user.username for user in likers]

        # Comment yozganlar
        comments = cl.media_comments(media_pk, amount=300)
        comment_counter = Counter()
        comment_details = []

        for c in comments:
            username = c.user.username
            comment_counter[username] += 1
            comment_details.append((username, c.text))

        # Natija
        text = f"📊 <b>VIDEO / POST STATISTIKASI</b>\n\n"
        text += f"❤️ Jami Like: <b>{len(likers)} ta</b>\n"
        text += f"💬 Jami Comment: <b>{len(comments)} ta</b>\n"
        text += f"👥 Comment yozgan odamlar: <b>{len(comment_counter)} ta</b>\n\n"

        # Like bosgan userlar
        text += f"<b>❤️ Like bosgan userlar ({len(likers)} ta):</b>\n"
        for i, user in enumerate(liker_usernames[:25], 1):   # Birinchi 25 tasini chiqaradi
            text += f"{i}. @{user}\n"
        if len(liker_usernames) > 25:
            text += f"... va yana {len(liker_usernames)-25} ta\n"

        # Eng faol comment userlar
        text += f"\n<b>🔥 Eng ko'p comment yozganlar:</b>\n"
        for i, (user, count) in enumerate(comment_counter.most_common(15), 1):
            text += f"{i}. @{user} — {count} ta\n"

        bot.edit_message_text(text, message.chat.id, status.message_id, parse_mode='HTML')

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {str(e)}\nPost linkini tekshirib /setpost qiling.", 
                             message.chat.id, status.message_id)

print("🤖 Bot muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()
