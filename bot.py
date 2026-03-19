import os
import requests
import threading
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from groq import Groq
from googlesearch import search

# =========================
# 🔐 ENV
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# =========================
# 🧠 DATA
# =========================
user_data = {}
user_study = {}

# =========================
# 🎓 STUDY DATA
# =========================
study_data = {
    "💻 IT": {
        "Computer Science": {
            "Programming": {
                "pdf": ["https://example.com/programming.pdf"],
                "videos": ["https://youtube.com/..."]
            },
            "Database": {
                "pdf": ["https://example.com/db.pdf"],
                "videos": ["https://youtube.com/..."]
            }
        }
    },
    "🏗️ Engineering": {
        "Civil": {
            "Statics": {
                "pdf": ["https://example.com/statics.pdf"],
                "videos": ["https://youtube.com/..."]
            }
        }
    }
}

# =========================
# 🎛️ MENU
# =========================
def main_menu():
    keyboard = [
        ["🤖 AI Chat", "🎓 Study"],
        ["🔎 Search", "📊 Stats"],
        ["🔙 Reset"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    user_data[user_id] = {"history": [], "mode": "menu"}
    user_study[user_id] = {}

    await update.message.reply_text(
        "🤖 اختر ماذا تريد:",
        reply_markup=main_menu()
    )

# =========================
# 🤖 AI CHAT
# =========================
async def ai_chat(user_id, text):
    history = user_data[user_id]["history"]

    history.append({"role": "user", "content": text})

    loop = asyncio.get_running_loop()

    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            messages=history[-10:],
            model="llama-3.3-70b-versatile"
        )
    )

    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})

    return "🤖 " + reply

# =========================
# 📊 STATS
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_count = len(user_data)
    total_messages = sum(len(u["history"]) for u in user_data.values())

    await update.message.reply_text(
        f"📊 الإحصائيات:\n👤 المستخدمين: {users_count}\n💬 الرسائل: {total_messages}"
    )

# =========================
# 🎓 STUDY FLOW
# =========================
async def handle_study(update, user_id, text):
    data = user_study[user_id]

    # اختيار القسم
    if text in study_data:
        data["department"] = text
        specs = study_data[text].keys()

        keyboard = [[s] for s in specs] + [["🔙 رجوع"]]
        await update.message.reply_text(
            "🎓 اختر التخصص:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # اختيار التخصص
    if "department" in data and text in study_data[data["department"]]:
        data["specialization"] = text
        subjects = study_data[data["department"]][text].keys()

        keyboard = [[s] for s in subjects] + [["🔙 رجوع"]]
        await update.message.reply_text(
            "📘 اختر المادة:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # اختيار المادة
    if "specialization" in data:
        try:
            content = study_data[data["department"]][data["specialization"]][text]

            msg = "📚 المصادر:\n\n"

            for pdf in content["pdf"]:
                msg += f"📄 PDF: {pdf}\n"

            for vid in content["videos"]:
                msg += f"🎥 فيديو: {vid}\n"

            await update.message.reply_text(msg, reply_markup=main_menu())

        except:
            await update.message.reply_text("❌ لا يوجد محتوى")

# =========================
# 🎯 MAIN HANDLER
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in user_data:
        user_data[user_id] = {"history": [], "mode": "menu"}
        user_study[user_id] = {}

    mode = user_data[user_id]["mode"]

    # الأزرار الرئيسية
    if text == "🤖 AI Chat":
        user_data[user_id]["mode"] = "ai"
        await update.message.reply_text("🤖 اكتب الآن")
        return

    elif text == "🎓 Study":
        user_data[user_id]["mode"] = "study"
        keyboard = [[d] for d in study_data.keys()]
        await update.message.reply_text(
            "🏫 اختر القسم:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    elif text == "🔎 Search":
        user_data[user_id]["mode"] = "search"
        await update.message.reply_text("🔎 اكتب كلمة البحث")
        return

    elif text == "📊 Stats":
        await stats(update, context)
        return

    elif text == "🔙 Reset" or text == "🔙 رجوع":
        user_data[user_id]["mode"] = "menu"
        user_data[user_id]["history"] = []
        user_study[user_id] = {}
        await update.message.reply_text("🔙 رجعنا للقائمة", reply_markup=main_menu())
        return

    # تنفيذ حسب الوضع
    if mode == "ai":
        reply = await ai_chat(user_id, text)
        await update.message.reply_text(reply)

    elif mode == "search":
        results = list(search(text, num_results=3))
        msg = "🔎 النتائج:\n" + "\n".join(results)
        await update.message.reply_text(msg)

    elif mode == "study":
        await handle_study(update, user_id, text)

    else:
        await update.message.reply_text("⬇️ اختر من القائمة", reply_markup=main_menu())

# =========================
# 🌐 WEB SERVER
# =========================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_web():
    PORT = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# =========================
# 🚀 APP
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🔥 BOT FINAL VERSION STARTED")

requests.get(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true",
    timeout=10
)

app.run_polling(drop_pending_updates=True)
