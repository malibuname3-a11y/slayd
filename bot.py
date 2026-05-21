import telebot
from instagrapi import Client
from collections import defaultdict
import time
import threading
import json
import os

# ================== SOZLAMALAR FAYL =================================
CONFIG_FILE = "config.json"

# Agar config fayl bo'lmasa — yaratadi va token so'raydi
if not os.path.exists(CONFIG_FILE):
    print("🔑 Birinchi marta ishga tushmoqda...")
    print("BotFatherdan olingan Telegram bot tokeningizni quyiga yozing:")
    token = input("Telegram Token: ").strip()
    
    config = {
        "telegram_token": token,
        "insta_username": input("Instagram Username: ").strip(),
        "insta_password": input("Instagram Password: ").strip(),
        "post_url": input("Instagram Post Link (bo'sh qoldirsa ham bo'ladi): ").strip()
    }
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    
    print("✅ Sozlamalar saqlandi! Endi bot ishga tushmoqda...\n")
else:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

# Sozlamalarni olish
TELEGRAM_TOKEN = config["telegram_token"]
INSTA_USERNAME = config.get("insta_username")
INSTA_PASSWORD = config.get("insta_password")
CURRENT_POST_URL = config.get("post_url", "https://www.instagram.com/p/DEFAULT_POST/")

# ================== BOTNI ISHGA TUSHIRISH ==================
bot = telebot.TeleBot(TELEGRAM_TOKEN)
cl = Client()

DATA_FILE = "instagram_tracking.json"
tracking_data = {"likers": set(), "comments": defaultdict(list)}

# Oldingi ma'lumotlarni yuklash
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            tracking_data["likers"] = set(data.get("likers", []))
            tracking_data["comments"] = defaultdict(list, data.get("comments", {}))
    except:
        pass

def save_tracking():
    data = {
        "likers": list(tracking_data["likers"]),
        "comments": dict(tracking_data["comments"])
    }
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def instagram_login():
    try:
        cl.login(INSTA_USERNAME, INSTA_PASSWORD)
        print("✅ Instagramga muvaffaqiyatli kirdik!")
    except Exception as e:
        print("❌ Instagram login xatosi:", e)

instagram_login()

# ================== KOMANDALAR ==================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
        "✅ Bot muvaffaqiyatli ishga tushdi!\n\n"
        "/stats — Yangi like va commentlarni ko‘rish\n"
        "/setpost — Yangi post linkini o‘zgartirish")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    chat_id = message.chat.id
    status_msg = bot.send_message(chat_id, "⏳ Instagramdan ma'lumot yuklanmoqda...")

    try:
        media_pk = cl.media_pk_from_url(CURRENT_POST_URL)
        media = cl.media_info(media_pk).dict()

        current_likers = {user.username for user in cl.media_likers(media_pk)}
        new_likers = current_likers - tracking_data["likers"]

        comments = cl.media_comments(media_pk, amount=250)
        current_comments = defaultdict(list)
        for c in comments:
            current_comments[c.user.username].append(c.text)

        new_comments = []
        for user, texts in current_comments.items():
            old = tracking_data["comments"].get(user, [])
            for text in texts:
                if text not in old:
                    new_comments.append((user, text))

        # Natija
        text = f"📊 <b>Post Statistikasi</b>\n\n"
        text += f"❤️ Like: <b>{media['like_count']}</b>\n"
        text += f"💬 Comment: <b>{media['comment_count']}</b>\n\n"

        if new_likers:
            text += f"<b>🆕 Yangi Like bosganlar:</b>\n"
            for user in list(new_likers)[:15]:
                text += f"❤️ @{user}\n"
        else:
            text += "🟢 Yangi like yo‘q\n"

        if new_comments:
            text += f"\n<b>🆕 Yangi Commentlar:</b>\n"
            for user, comm in new_comments[:12]:
                text += f"💬 <b>@{user}</b>: {comm[:70]}{'...' if len(comm)>70 else ''}\n"
        else:
            text += "\n🟢 Yangi comment yo‘q\n"

        bot.edit_message_text(text, chat_id, status_msg.message_id, parse_mode='HTML')

        # Yangilash
        tracking_data["likers"] = current_likers
        tracking_data["comments"] = current_comments
        save_tracking()

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {str(e)}\nPost linkini /setpost bilan yangilab ko‘ring.", 
                             chat_id, status_msg.message_id)

@bot.message_handler(commands=['setpost'])
def set_post(message):
    global CURRENT_POST_URL
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        CURRENT_POST_URL = url
        # config faylni ham yangilash
        config["post_url"] = url
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        bot.reply_to(message, f"✅ Post yangilandi!\n{CURRENT_POST_URL}")
    except:
        bot.reply_to(message, "❌ Foydalanish: /setpost https://www.instagram.com/p/....")

print("🤖 Telegram bot muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()
