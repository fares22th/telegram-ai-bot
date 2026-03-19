import os
import requests
import threading
import asyncio
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY missing")

client = Groq(api_key=GROQ_API_KEY)

# =========================
# 💾 DATABASE
# =========================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    messages_count INTEGER DEFAULT 0
)
""")
conn.commit()

def save_user(user):
    cursor.execute("""
    INSERT OR IGNORE INTO users (user_id, username, messages_count)
    VALUES (?, ?, 0)
    """, (user.id, user.username))

    cursor.execute("""
    UPDATE users SET messages_count = messages_count + 1
    WHERE user_id = ?
    """, (user.id,))

    conn.commit()

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.message.from_user)
    await update.message.reply_text("🤖 أهلاً! اكتب أي شيء وسأرد عليك 🔥")

# =========================
# 🤖 AI CHAT (بدون أوامر)
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    save_user(user)

    try:
        loop = asyncio.get_running_loop()

        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                messages=[{"role": "user", "content": text}],
                model="llama-3.3-70b-versatile"
            )
        )

        await update.message.reply_text("🤖 " + response.choices[0].message.content)

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

# =========================
# 🔎 SEARCH
# =========================
async def smart_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🔎 /search python")
        return

    try:
        results = list(search(" ".join(context.args), num_results=5))
        buttons = [[InlineKeyboardButton("🔗 فتح الرابط", url=url)] for url in results]

        await update.message.reply_text(
            "🔎 النتائج:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

# =========================
# 📊 STATS
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(messages_count) FROM users")
    total_messages = cursor.fetchone()[0] or 0

    await update.message.reply_text(
        f"📊 الإحصائيات:\n👤 المستخدمين: {users_count}\n💬 الرسائل: {total_messages}"
    )

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
app.add_handler(CommandHandler("search", smart_search))
app.add_handler(CommandHandler("stats", stats))

# 🔥 أهم سطر (AI بدون أوامر)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🔥 BOT STARTED")

# 🔥 تنظيف التعارض
requests.get(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true",
    timeout=10
)
print("NEW VERSION 999")

app.run_polling(drop_pending_updates=True)
