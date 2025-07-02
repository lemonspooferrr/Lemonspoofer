import logging
import os
import json
from dotenv import load_dotenv
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import aiohttp

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TOKEN")
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")

user_licenses = {}
user_credits = {}

# ✅ Enregistre l’utilisateur dans users.json
def save_user(user_id):
    try:
        with open("users.json", "r") as f:
            users = json.load(f)
            if not isinstance(users, list):
                users = list(users.values()) if isinstance(users, dict) else []
    except (FileNotFoundError, json.JSONDecodeError):
        users = []

    if user_id not in users:
        users.append(user_id)
        with open("users.json", "w") as f:
            json.dump(users, f)

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Accès SIP", callback_data="sip"), InlineKeyboardButton("💳 Recharger", callback_data="recharger")],
        [InlineKeyboardButton("🆔 Caller ID", callback_data="caller_id"), InlineKeyboardButton("🎵 Musique d’attente", callback_data="musique")],
        [InlineKeyboardButton("💬 SMS Sender", callback_data="sms"), InlineKeyboardButton("📧 Mail Sender", callback_data="mail")],
        [InlineKeyboardButton("⚙️ Paramètres", callback_data="parametres")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id)
    heure = datetime.now().strftime('%H:%M:%S')
    message = (
        "🔷 Bienvenue sur LemonSpoofer🍋\n\n"
        f"🟢 Statut : En ligne\n"
        f"🆔 ID : {user.id}\n"
        f"💰 Crédits : {user_credits.get(user.id, 0)}\n"
        f"🕒 Heure : {heure}\n\n"
        "Utilise /acheter pour obtenir ta licence. 🚀"
    )
    await update.message.reply_text(message, reply_markup=menu())

async def acheter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    uid = f"{user_id}_{datetime.now().timestamp()}"
    body = {
        "price_amount": 120,
        "price_currency": "eur",
        "pay_currency": "usdttrc20",
        "ipn_callback_url": "https://nowpayments.io",
        "order_id": uid,
        "order_description": "Licence 2 mois LemonSpoofer"
    }
    headers = {"x-api-key": NOWPAYMENTS_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.nowpayments.io/v1/invoice", json=body, headers=headers) as resp:
            data = await resp.json()

    if "invoice_url" in data:
        url = data["invoice_url"]
        await update.message.reply_text(f"🔐 Paiement licence (120€ pour 2 mois) :\n{url}")
    else:
        await update.message.reply_text(f"⚠️ Erreur lors de la génération du lien :\n{data}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) != os.getenv("ADMIN_ID"):
        await update.message.reply_text("❌ Tu n’es pas autorisé à envoyer un broadcast.")
        return
    if not context.args:
        await update.message.reply_text("❗ Utilise /broadcast [ton message]")
        return
    message = "🔊 " + " ".join(context.args)
    try:
        with open("users.json", "r") as f:
            users = json.load(f)
            if isinstance(users, dict):
                users = list(users.values())
    except:
        users = []
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            count += 1
        except:
            continue
    await update.message.reply_text(f"✅ Message envoyé à {count} utilisateurs.")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if not user_licenses.get(user_id):
        await query.edit_message_text("❌ Tu dois acheter une licence pour accéder à cette option.\nUtilise /acheter 🚀")
        return
    await query.edit_message_text(f"✅ Accès accordé à l’option : {query.data}")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("acheter", acheter))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(handle_buttons))

if __name__ == "__main__":
    app.bot.delete_webhook(drop_pending_updates=True)
    app.run_polling()
