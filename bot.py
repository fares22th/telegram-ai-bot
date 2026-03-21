import os
import json
import threading
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from groq import Groq

# 🔥 Firebase
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import FieldValue


# =========================
# 🔐 ENV
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
FIREBASE_KEY = os.getenv("FIREBASE_KEY")

if not TELEGRAM_TOKEN:
    raise SystemExit("❌ TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise SystemExit("❌ GROQ_API_KEY missing")

if not FIREBASE_KEY:
    raise SystemExit("❌ FIREBASE_KEY missing")

client = Groq(api_key=GROQ_API_KEY)


# =========================
# 🔥 Firebase Init
# =========================
try:
    cred = credentials.Certificate(json.loads(FIREBASE_KEY))
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("🔥 Firebase CONNECTED")
except Exception as e:
    print("❌ Firebase ERROR:", e)
    db = None


# =========================
# ⚡ CACHE
# =========================
STUDY_CACHE = {}

def get_study_data():
    global STUDY_CACHE

    if not STUDY_CACHE:
        docs = db.collection("study").stream()
        for doc in docs:
            STUDY_CACHE[doc.id] = doc.to_dict()

    return STUDY_CACHE


# =========================
# 🔥 FIREBASE HELPERS
# =========================
def save_user(user_id):
    try:
        db.collection("users").document(str(user_id)).set({
            "id": str(user_id)
        }, merge=True)
        print("✅ user saved:", user_id)
    except Exception as e:
        print("❌ save user error:", e)


def increment_messages():
    try:
        db.collection("stats").document("messages").set(
            {"count": FieldValue.increment(1)},
            merge=True,
        )
    except Exception as e:
        print("❌ msg error:", e)


def increment_subject(subject):
    try:
        db.collection("usage").document(subject).set(
            {"count": FieldValue.increment(1)},
            merge=True,
        )
    except Exception as e:
        print("❌ usage error:", e)


# =========================
# 🧠 MEMORY
# =========================
user_data = {}
user_study = {}


# =========================
# 🎛️ MENU
# =========================
def main_menu():
    return ReplyKeyboardMarkup(
        [
            ["🤖 AI Chat", "🎓 Study"],
            ["🧠 AI Search", "📊 Stats"],
            ["🔙 Reset"],
        ],
        resize_keyboard=True,
    )


# =========================
# 🚀 START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    user_data[uid] = {"history": [], "mode": "menu"}
    user_study[uid] = {}

    save_user(uid)
    increment_messages()

    await update.message.reply_text(
        "🔥 أهلاً! اختر:",
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
            model="llama-3.3-70b-versatile",
        ),
    )

    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})

    return "🤖 " + reply


# =========================
# 🧠 AI SEARCH (🔥 الجديد)
# =========================
async def ai_search(query):
    loop = asyncio.get_running_loop()

    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": f"ابحث عن هذا الموضوع واعطني أفضل شرح وروابط مفيدة:\n{query}"
            }],
            model="llama-3.3-70b-versatile",
        ),
    )

    return "🧠 AI Search:\n\n" + response.choices[0].message.content


# =========================
# 📊 STATS
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = list(db.collection("users").stream())
    users_count = len(users)

    msg_doc = db.collection("stats").document("messages").get()
    msg_count = msg_doc.to_dict().get("count", 0) if msg_doc.exists else 0

    await update.message.reply_text(
        f"📊 الإحصائيات:\n👤 المستخدمين: {users_count}\n💬 الرسائل: {msg_count}"
    )


# =========================
# 🎓 STUDY
# =========================
async def handle_study(update, uid, text):
    data = user_study[uid]
    study_data = get_study_data()

    if text in study_data:
        data["department"] = text

        keyboard = [[s] for s in study_data[text].keys()]
        keyboard.append(["🔙 رجوع"])

        await update.message.reply_text(
            "🎓 اختر التخصص:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return

    if "department" in data and text in study_data[data["department"]]:
        data["specialization"] = text

        subjects = study_data[data["department"]][text].keys()

        keyboard = [[s] for s in subjects]
        keyboard.append(["🔙 رجوع"])

        await update.message.reply_text(
            "📘 اختر المادة:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return

    if "specialization" in data:
        try:
            content = study_data[data["department"]][data["specialization"]][text]

            increment_subject(text)

            msg = "📚 المصادر:\n\n"

            for pdf in content.get("pdf", []):
                msg += f"📄 {pdf}\n"

            for vid in content.get("videos", []):
                msg += f"🎥 {vid}\n"

            await update.message.reply_text(msg, reply_markup=main_menu())

        except:
            await update.message.reply_text("❌ لا يوجد محتوى")


# =========================
# 🎯 MAIN
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    save_user(uid)
    increment_messages()

    if uid not in user_data:
        user_data[uid] = {"history": [], "mode": "menu"}
        user_study[uid] = {}

    mode = user_data[uid]["mode"]

    if text == "🤖 AI Chat":
        user_data[uid]["mode"] = "ai"
        await update.message.reply_text("🤖 اكتب سؤالك")
        return

    elif text == "🎓 Study":
        user_data[uid]["mode"] = "study"

        study_data = get_study_data()
        keyboard = [[d] for d in study_data.keys()]

        await update.message.reply_text(
            "🏫 اختر القسم:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return

    elif text == "🧠 AI Search":
        user_data[uid]["mode"] = "search"
        await update.message.reply_text("🧠 اكتب ما تريد البحث عنه")
        return

    elif text == "📊 Stats":
        await stats(update, context)
        return

    elif text in ["🔙 Reset", "🔙 رجوع"]:
        user_data[uid] = {"history": [], "mode": "menu"}
        user_study[uid] = {}
        await update.message.reply_text("🔙 رجعنا", reply_markup=main_menu())
        return

    if mode == "ai":
        reply = await ai_chat(uid, text)
        await update.message.reply_text(reply)

    elif mode == "search":
        result = await ai_search(text)
        await update.message.reply_text(result)

    elif mode == "study":
        await handle_study(update, uid, text)

    else:
        await update.message.reply_text("⬇️ اختر من القائمة", reply_markup=main_menu())


# =========================
# 🌐 SERVER
# =========================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot running")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_web, daemon=True).start()


# =========================
# 🚀 RUN
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🔥 BOT STARTED")

requests.get(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true"
)

app.run_polling(drop_pending_updates=True)
