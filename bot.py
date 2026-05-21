import telebot
from instagrapi import Client
from collections import defaultdict
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

# Agar biror narsa yo'q bo'lsa
if not TELEGRAM_TOKEN or not INSTA_USERNAME or not INSTA_PASSWORD:
    print("❌ .env faylida ma'lumotlar to'liq emas!")
    print("TELEGRAM_TOKEN, INSTA_USERNAME va INSTA_PASSWORD ni to'ldiring.")
    exit()

# =====================================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)
cl = Client()

DATA_FILE = "tracking.json"

tracking_data = {"likers": set(), "comments": defaultdict(list)}

if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            tracking_data["likers"] = set(data.get("likers", []))
            tracking_data["comments"] = defaultdict(list, data.get("comments", {}))
    except:
        pass

def save_tracking():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            "likers": list(tracking_data["likers"]),
            "comments": dict(tracking_data["comments"])
        }, f, ensure_ascii=False, indent=2)

def instagram_login():
    try:
        cl.login(INSTA_USERNAME, INSTA_PASSWORD)
        print("✅ Instagramga muvaffaqiyatli kirdik!")
    except Exception as e:
        print("❌ Instagram login xatosi:", e)

instagram_login()

# ===================== KOMANDALAR =====================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Bot ishga tushdi!\n/stats — statistikani ko'rish")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    chat_id = message.chat.id
    status = bot.send_message(chat_id, "⏳ Ma'lumot yuklanmoqda...")

    try:
        media_pk = cl.media_pk_from_url(CURRENT_POST_URL)
        media = cl.media_info(media_pk).dict()

        current_likers = {user.username for user in cl.media_likers(media_pk)}
        new_likers = current_likers - tracking_data["likers"]

        comments = cl.media_comments(media_pk, amount=200)
        current_comments = defaultdict(list)
        for c in comments:
            current_comments[c.user.username].append(c.text)

        new_comments = []
        for user, texts in current_comments.items():
            old_texts = tracking_data["comments"].get(user, [])
            for text in texts:
                if text not in old_texts:
                    new_comments.append((user, text))

        # Natija
        text = f"📊 <b>Post Statistikasi</b>\n\n"
        text += f"❤️ Like: <b>{media['like_count']}</b>\n"
        text += f"💬 Comment: <b>{media['comment_count']}</b>\n\n"

        if new_likers:
            text += f"<b>🆕 Yangi Like bosganlar ({len(new_likers)}):</b>\n"
            for u in list(new_likers)[:15]:
                text += f"❤️ @{u}\n"
        else:
            text += "🟢 Yangi like yo'q\n"

        if new_comments:
            text += f"\n<b>🆕 Yangi Commentlar:</b>\n"
            for user, comm in new_comments[:10]:
                text += f"💬 <b>@{user}</b>: {comm[:60]}{'...' if len(comm)>60 else ''}\n"

        bot.edit_message_text(text, chat_id, status.message_id, parse_mode='HTML')

        # Yangilash
        tracking_data["likers"] = current_likers
        tracking_data["comments"] = current_comments
        save_tracking()

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {str(e)}", chat_id, status.message_id)

print("🤖 Bot muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()
