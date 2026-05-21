import telebot
from instagrapi import Client
from collections import Counter
import json
import os
from dotenv import load_dotenv

# ================== CONFIG ==================
CONFIG_FILE = "config.json"

# Agar config fayl bo'lmasa — birinchi marta so'raydi
if not os.path.exists(CONFIG_FILE):
    print("\n🔑 Birinchi marta sozlamalar kiritilmoqda...")
    print("BotFatherdan olingan Telegram bot tokeningizni quyiga yozing:")
    
    telegram_token = input("Telegram Token: ").strip()
    
    config = {
        "telegram_token": telegram_token,
        "post_url": ""
    }
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    
    print("✅ Token saqlandi! Bot ishga tushmoqda...\n")
else:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

# ================== BOT ==================
bot = telebot.TeleBot(config["telegram_token"])
cl = Client()

SESSION_FILE = "instagram_session.json"

# Sessiyani yuklash
if os.path.exists(SESSION_FILE):
    try:
        cl.load_settings(SESSION_FILE)
        print("✅ Instagram sessiyasi yuklandi")
    except:
        print("⚠️ Sessiya yuklanmadi, /login orqali qayta kirishingiz kerak")

def save_session():
    cl.dump_settings(SESSION_FILE)

# ================== KOMANDALAR ==================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
        "✅ **Reels Statistikasi Boti** ishga tushdi!\n\n"
        "/login — Instagramga kirish (birinchi marta)\n"
        "/setpost — Reels havolasini yuborish\n"
        "/stats — Like va commentlarni ko'rish")

@bot.message_handler(commands=['login'])
def login(message):
    msg = bot.reply_to(message, "Instagram **Username**ingizni yuboring:")
    bot.register_next_step_handler(msg, process_username)

def process_username(message):
    username = message.text.strip()
    msg = bot.reply_to(message, "Instagram **Parol**ingizni yuboring:")
    bot.register_next_step_handler(msg, lambda m: process_password(m, username))

def process_password(message, username):
    password = message.text.strip()
    status_msg = bot.reply_to(message, "⏳ Instagramga kirishga urinmoqda...")

    try:
        cl.login(username, password)
        save_session()
        bot.edit_message_text("✅ Instagramga muvaffaqiyatli kirdik!\nEndi parol saqlanadi.", 
                            message.chat.id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {e}", message.chat.id, status_msg.message_id)

@bot.message_handler(commands=['setpost'])
def set_post(message):
    global config
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        config["post_url"] = url
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        bot.reply_to(message, f"✅ Reels saqlandi:\n{url}")
    except:
        bot.reply_to(message, "❌ /setpost https://www.instagram.com/reel/......")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not config.get("post_url"):
        bot.reply_to(message, "❌ Avval /setpost orqali Reels havolasini yuboring!")
        return

    status = bot.send_message(message.chat.id, "⏳ Reelsdan ma'lumot yuklanmoqda...")

    try:
        media_pk = cl.media_pk_from_url(config["post_url"])
        media = cl.media_info(media_pk).dict()

        likers = cl.media_likers(media_pk)
        comments = cl.media_comments(media_pk, amount=250)
        comment_counter = Counter(c.user.username for c in comments)

        text = f"📊 <b>REELS STATISTIKASI</b>\n\n"
        text += f"❤️ Like bosgan: <b>{len(likers)} ta</b>\n"
        text += f"💬 Comment yozgan: <b>{len(comments)} ta</b>\n"
        text += f"👥 Comment yozgan odamlar: <b>{len(comment_counter)} ta</b>\n\n"

        # Like userlar
        text += "<b>❤️ Like bosgan userlar:</b>\n"
        for i, user in enumerate([u.username for u in likers][:30], 1):
            text += f"{i}. @{user}\n"
        if len(likers) > 30:
            text += f"... yana {len(likers)-30} ta\n"

        # Top commenters
        text += f"\n<b>🔥 Eng faol comment yozganlar:</b>\n"
        for i, (user, count) in enumerate(comment_counter.most_common(12), 1):
            text += f"{i}. @{user} — {count} ta comment\n"

        bot.edit_message_text(text, message.chat.id, status.message_id, parse_mode='HTML')

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {str(e)}\nPost linkini tekshiring.", 
                             message.chat.id, status.message_id)

print("🤖 Bot muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()
