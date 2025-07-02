import logging
import os
import json
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import aiohttp

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
        "🔷 Bienvenue sur LemonSpoofer🍋

"
        f"🟢 Statut : En ligne
"
        f"🆔 ID : {user.id}
"
        f"💰 Crédits : {user_credits.get(user.id, 0)}
"
        f"🕒 Heure : {heure}

"
        "Utilise /acheter pour obtenir ta licence. 🚀"
    )
    await update.message.reply_text(message, reply_markup=menu())

# 💳 Commande /acheter (paiement crypto 120 € via NOWPayments)
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
        await update.message.reply_text(f"🔐 Paiement licence (120€ pour 2 mois) :
{url}")
    else:
        await update.message.reply_text(f"⚠️ Erreur lors de la génération du lien :
{data}")

# 🔒 Boutons protégés
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if not user_licenses.get(user_id):
        await query.edit_message_text("❌ Tu dois acheter une licence pour accéder à cette option.
Utilise /acheter 🚀")
        return
    await query.edit_message_text(f"✅ Accès accordé à l’option : {query.data}")

# 📣 Commande /broadcast (admin uniquement)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 7478470461  # Ton ID Telegram
    sender_id = update.effective_user.id

    if sender_id != admin_id:
        await update.message.reply_text("⛔ Tu n'es pas autorisé à utiliser cette commande.")
        return

    if context.args:
        message_to_send = " ".join(context.args)
    else:
        await update.message.reply_text("⚠️ Utilisation : /broadcast Votre message ici")
        return

    try:
        with open("users.json", "r") as f:
            users = json.load(f)
    except:
        users = []

    count = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_send)
            count += 1
        except Exception as e:
            logging.warning(f"Impossible d’envoyer à {user_id}: {e}")

    await update.message.reply_text(f"✅ Message envoyé à {count} utilisateur(s).")

# ▶️ Lancer le bot
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("acheter", acheter))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(handle_buttons))

if __name__ == "__main__":
    app.bot.delete_webhook(drop_pending_updates=True)
    app.run_polling()
