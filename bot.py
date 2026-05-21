import telebot
from instagrapi import Client
from collections import defaultdict
import json
import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# ================== SOZLAMALAR ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
INSTA_USERNAME = os.getenv("INSTA_USERNAME")
INSTA_PASSWORD = os.getenv("INSTA_PASSWORD")
CURRENT_POST_URL = os.getenv("POST_URL")

if not all([TELEGRAM_TOKEN, INSTA_USERNAME, INSTA_PASSWORD]):
    print("❌ .env faylida ma'lumotlar yetarli emas!")
    exit()

bot = telebot.TeleBot(TELEGRAM_TOKEN)
cl = Client()

DATA_FILE = "tracking.json"
tracking_data = {"likers": set(), "comments": defaultdict(list)}

# Eski ma'lumotlarni yuklash
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            tracking_data["likers"] = set(data.get("likers", []))
            tracking_data["comments"] = defaultdict(list, data.get("comments", {}))
    except:
        pass

def save_tracking():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "likers": list(tracking_data["likers"]),
                "comments": dict(tracking_data["comments"])
            }, f, ensure_ascii=False, indent=2)
    except:
        pass

# Instagramga kirish
def instagram_login():
    try:
        cl.login(INSTA_USERNAME, INSTA_PASSWORD)
        print("✅ Instagramga muvaffaqiyatli kirdik!")
        return True
    except Exception as e:
        print(f"❌ Instagram login xatosi: {e}")
        return False

instagram_login()

# ================== KOMANDALAR ==================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
        "✅ Bot muvaffaqiyatli ishga tushdi!\n\n"
        "/stats — Yangi like va commentlarni ko‘rish\n"
        "/setpost — Yangi post linkini o‘zgartirish")

@bot.message_handler(commands=['setpost'])
def set_post(message):
    global CURRENT_POST_URL
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        CURRENT_POST_URL = url
        bot.reply_to(message, f"✅ Post yangilandi:\n{CURRENT_POST_URL}")
    except:
        bot.reply_to(message, "❌ Foydalanish: /setpost https://www.instagram.com/p/....")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    chat_id = message.chat.id
    status_msg = bot.send_message(chat_id, "⏳ Instagramdan ma'lumot yuklanmoqda... Iltimos biroz kutib turing.")

    try:
        # Post linkdan media_pk olish
        media_pk = cl.media_pk_from_url(CURRENT_POST_URL)
        media = cl.media_info(media_pk).dict()

        # Like bosganlar
        current_likers = {user.username for user in cl.media_likers(media_pk)}
        new_likers = current_likers - tracking_data["likers"]

        # Commentlar
        comments = cl.media_comments(media_pk, amount=250)
        current_comments = defaultdict(list)
        for c in comments:
            current_comments[c.user.username].append(c.text)

        # Yangi commentlar
        new_comments = []
        for user, texts in current_comments.items():
            old_texts = tracking_data["comments"].get(user, [])
            for text in texts:
                if text not in old_texts:
                    new_comments.append((user, text))

        # Natija matni
        text = f"📊 <b>Post Statistikasi</b>\n\n"
        text += f"❤️ Like: <b>{media['like_count']}</b>\n"
        text += f"💬 Comment: <b>{media['comment_count']}</b>\n\n"

        if new_likers:
            text += f"<b>🆕 Yangi Like bosganlar ({len(new_likers)} ta):</b>\n"
            for user in list(new_likers)[:20]:
                text += f"❤️ @{user}\n"
        else:
            text += "🟢 Yangi like yo‘q\n"

        if new_comments:
            text += f"\n<b>🆕 Yangi Commentlar:</b>\n"
            for user, comm in new_comments[:12]:
                text += f"💬 <b>@{user}</b>: {comm[:65]}{'...' if len(comm) > 65 else ''}\n"
        else:
            text += "\n🟢 Yangi comment yo‘q\n"

        bot.edit_message_text(text, chat_id, status_msg.message_id, parse_mode='HTML')

        # Ma'lumotni yangilash
        tracking_data["likers"] = current_likers
        tracking_data["comments"] = current_comments
        save_tracking()

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {str(e)}\n\n/setpost orqali post linkini qayta qo‘ying.", 
                             chat_id, status_msg.message_id)

print("🤖 Telegram bot muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()
