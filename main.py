import logging
import os
import json
from dotenv import load_dotenv
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import aiohttp

load_dotenv()

# 🔐 Logs
logging.basicConfig(level=logging.INFO)

# 🔧 Clé API et Token
BOT_TOKEN = os.getenv("TOKEN")
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")

# 📌 Utilisateurs
user_licenses = {}
user_credits = {}

# ✅ Enregistre l’utilisateur dans users.json
def save_user(user_id):
    try:
        with open("users.json", "r") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []

    if user_id not in users:
        users.append(user_id)
        with open("users.json", "w") as f:
            json.dump(users, f)

# ⌨️ Menu principal
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Accès SIP", callback_data="sip"), InlineKeyboardButton("💳 Recharger", callback_data="recharger")],
        [InlineKeyboardButton("🆔 Caller ID", callback_data="caller_id"), InlineKeyboardButton("🎵 Musique d’attente", callback_data="musique")],
        [InlineKeyboardButton("💬 SMS Sender", callback_data="sms"), InlineKeyboardButton("📧 Mail Sender", callback_data="mail")],
        [InlineKeyboardButton("⚙️ Paramètres", callback_data="parametres")]
    ])

# 🟢 Commande /start
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

# 💳 Commande /acheter
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
        await update.message.reply_text(f"🔐 Paiement licence (120€ pour 2 mois) :\n{data['invoice_url']}")
    else:
        await update.message.reply_text(f"⚠️ Erreur lors de la génération du lien :\n{data}")

# 🔒 Boutons protégés
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if not user_licenses.get(user_id):
        await query.edit_message_text("❌ Tu dois acheter une licence pour accéder à cette option. Utilise /acheter 🚀")
        return
    await query.edit_message_text(f"✅ Accès accordé à l’option : {query.data}")

# 📢 Commande /broadcast
ADMIN_IDS = [7478470461]  # Remplace par ton ID Telegram admin

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Tu n'es pas autorisé à utiliser cette commande.")
        return

    try:
        with open("users.json", "r") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []

    if not context.args:
        await update.message.reply_text("❌ Utilisation : /broadcast [message]")
        return

    message = "📢 " + " ".join(context.args)
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logging.warning(f"Impossible d’envoyer à {user_id}: {e}")

    await update.message.reply_text("✅ Message envoyé à tous les utilisateurs enregistrés.")

# ▶️ Lancer le bot
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("acheter", acheter))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(handle_buttons))

if __name__ == "__main__":
    app.bot.delete_webhook(drop_pending_updates=True)
    app.run_polling()

# 🧠 Admin Commande
from telegram.constants import ParseMode

ADMIN_ID = os.getenv("ADMIN_ID")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 Accès réservé à l'administrateur.")
        return

    try:
        with open("users.json", "r") as f:
            users = json.load(f)
        total_users = len(users) if isinstance(users, list) else len(users.values())
    except:
        total_users = 0

    total_credits = sum(user_credits.get(str(uid), 0) for uid in users) if isinstance(users, list) else 0
    total_licenses = sum(1 for uid in users if user_licenses.get(str(uid))) if isinstance(users, list) else 0
    last_user = users[-1] if isinstance(users, list) and users else "N/A"

    msg = (
        f"📊 <b>Statistiques LemonSpoofer</b>

"
        f"👥 Utilisateurs : <b>{total_users}</b>
"
        f"💳 Crédits totaux : <b>{total_credits}</b>
"
        f"🔑 Licences actives : <b>{total_licenses}</b>
"
        f"📌 Dernier inscrit : <b>{last_user}</b>
"
    )

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

application.add_handler(CommandHandler('admin', admin))

