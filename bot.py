import telebot
from instagrapi import Client
from collections import defaultdict, Counter
import os
from dotenv import load_dotenv

load_dotenv()

# ================== .env dan olish ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
INSTA_USERNAME = os.getenv("INSTA_USERNAME")
INSTA_PASSWORD = os.getenv("INSTA_PASSWORD")
CURRENT_POST_URL = os.getenv("POST_URL")

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN topilmadi! .env faylini tekshiring.")
    exit()

bot = telebot.TeleBot(TELEGRAM_TOKEN)
cl = Client()

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
        "✅ Reels Statistikasi Boti ishga tushdi!\n\n"
        "/stats — Like va Commentlarni ko'rish\n"
        "/setpost — Yangi Reels havolasini yuborish")

@bot.message_handler(commands=['setpost'])
def set_post(message):
    global CURRENT_POST_URL
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        # Reels linkini to'g'rilash
        if "instagram.com/reels/" in url or "instagram.com/reel/" in url:
            url = url.replace("/reels/", "/reel/")
        CURRENT_POST_URL = url
        bot.reply_to(message, f"✅ Reels saqlandi:\n{CURRENT_POST_URL}")
    except:
        bot.reply_to(message, "❌ Foydalanish: /setpost https://www.instagram.com/reel/....")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not CURRENT_POST_URL:
        bot.reply_to(message, "❌ Avval /setpost orqali Reels havolasini yuboring!")
        return

    status = bot.send_message(message.chat.id, "⏳ Reelsdan ma'lumot yuklanmoqda... (biroz vaqt oladi)")

    try:
        media_pk = cl.media_pk_from_url(CURRENT_POST_URL)
        media = cl.media_info(media_pk).dict()

        # Like bosganlar
        likers = cl.media_likers(media_pk)
        liker_list = [f"@{user.username}" for user in likers]

        # Commentlar
        comments = cl.media_comments(media_pk, amount=300)
        comment_counter = Counter(c.user.username for c in comments)

        text = f"📊 <b>REELS STATISTIKASI</b>\n\n"
        text += f"❤️ Jami Like: <b>{len(likers)} ta</b>\n"
        text += f"💬 Jami Comment: <b>{len(comments)} ta</b>\n"
        text += f"👥 Comment yozganlar: <b>{len(comment_counter)} ta</b>\n\n"

        # Like bosgan userlar
        text += f"<b>❤️ Like bosganlar ({len(liker_list)} ta):</b>\n"
        text += "\n".join(liker_list[:30])  # Birinchi 30 tasini chiqaradi
        if len(liker_list) > 30:
            text += f"\n... va yana {len(liker_list)-30} ta"

        # Top comment yozganlar
        text += f"\n\n<b>🔥 Eng faol comment yozganlar:</b>\n"
        for i, (user, count) in enumerate(comment_counter.most_common(15), 1):
            text += f"{i}. @{user} — {count} ta\n"

        bot.edit_message_text(text, message.chat.id, status.message_id, parse_mode='HTML')

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {str(e)}\n\nReels linkini qayta /setpost qiling.", 
                             message.chat.id, status.message_id)

print("🤖 Reels Statistikasi Boti ishga tushdi...")
bot.infinity_polling()
