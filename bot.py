import os
import requests
import yt_dlp
import threading
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(" البوت يعمل 100%")

# =========================
# AI (FIXED 100%)
# =========================
async def ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/ai سؤالك")
        return

    question = " ".join(context.args)

    try:
        loop = asyncio.get_running_loop()

        chat = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                messages=[{"role": "user", "content": question}],
                model="llama-3.3-70b-versatile"
            )
        )

        await update.message.reply_text(chat.choices[0].message.content)

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

# =========================
# SEARCH
# =========================
async def smart_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/search python")
        return

    try:
        results = list(search(" ".join(context.args), num_results=5))

        buttons = [[InlineKeyboardButton("فتح 🔗", url=url)] for url in results]

        await update.message.reply_text(
            "🔎 النتائج:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

# =========================
# WEB SERVER
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
# APP
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ai", ai))
app.add_handler(CommandHandler("search", smart_search))

print("🔥 BOT STARTED")

# 🔥 مهم جدًا (تنظيف نهائي)
requests.get(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true",
    timeout=10
)

app.run_polling(drop_pending_updates=True)
