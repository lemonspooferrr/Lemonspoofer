import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")

# Init user DB
if not Path("users.json").exists():
    with open("users.json", "w") as f:
        json.dump({}, f)

# Load/save functions
def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=2)

# Main menu
def main_menu(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Accès SIP", callback_data="sip")],
        [InlineKeyboardButton("💬 Accès SMS", callback_data="sms")],
        [InlineKeyboardButton("📲 Caller ID", callback_data="caller_id")],
        [InlineKeyboardButton("🎵 Musique d’attente", callback_data="musique")],
        [InlineKeyboardButton("🛒 Acheter licence (120€)", callback_data="buy")],
        [InlineKeyboardButton("➕ Recharger crédits", callback_data="recharge")]
    ])

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "username": user.username,
            "first_name": user.first_name,
            "credits": 0,
            "license_expiry": None
        }
        save_users(users)

    time_str = datetime.now().strftime('%H:%M:%S')
    user_data = users[uid]
    license_status = user_data['license_expiry'] or '❌ Non active'
    message = (
        f"🔷 Bienvenue sur LemonSpoofer 🍋
"
        f"🕒 Heure: {time_str}
"
        f"🆔 ID: <code>{user.id}</code>
"
        f"👤 Nom: {user.first_name}
"
        f"💳 Crédits: {user_data['credits']}
"
        f"📅 Licence: {license_status}
"
    )
    await update.message.reply_text(message, reply_markup=main_menu(uid), parse_mode="HTML")

# Admin
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    users = load_users()
    total_users = len(users)
    total_credits = sum(u.get("credits", 0) for u in users.values())
    total_licenses = sum(1 for u in users.values() if u.get("license_expiry"))
    message = (
        f"📊 Statistiques:
"
        f"👥 Utilisateurs: {total_users}
"
        f"💳 Crédits totaux: {total_credits}
"
        f"✅ Licences actives: {total_licenses}
"
    )
    await update.message.reply_text(message)

# Broadcast
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    msg = ' '.join(context.args)
    if not msg:
        return await update.message.reply_text("❗ Utilise: /broadcast Votre message")
    users = load_users()
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=msg)
        except:
            pass
    await update.message.reply_text("✅ Message envoyé")

# Callback
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    users = load_users()
    data = query.data
    await query.answer()

    if data == "buy":
        return await buy(update, context)

    if data == "recharge":
        payment_url = f"https://nowpayments.io/payment/?api_key={NOWPAYMENTS_API_KEY}&price_amount=5&price_currency=eur&order_id={user_id}"
        await query.edit_message_text("💸 Recharge tes crédits ici:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Payer maintenant", url=payment_url)]
        ]))
    elif data in ["sip", "sms", "caller_id", "musique"]:
        license_ok = users[user_id].get("license_expiry")
        if not license_ok:
            return await query.edit_message_text("🚫 Licence requise pour utiliser cette option.")
        await query.edit_message_text(f"✅ Fonctionnalité {data} activée (simulation)")

# Buy command
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()

    async with aiohttp.ClientSession() as session:
        body = {
            "price_amount": 120,
            "price_currency": "eur",
            "pay_currency": "usdttrc20",
            "order_id": user_id,
            "order_description": "Licence LemonSpoofer 2 mois",
            "ipn_callback_url": "https://yourdomain.com/ipn"
        }
        headers = {
            "x-api-key": NOWPAYMENTS_API_KEY,
            "Content-Type": "application/json"
        }
        async with session.post("https://api.nowpayments.io/v1/invoice", json=body, headers=headers) as resp:
            data = await resp.json()
            invoice_url = data.get("invoice_url")

    if invoice_url:
        await update.message.reply_text(
            f"🔐 Clique ici pour acheter ta licence 2 mois (120€):\n{invoice_url}"
        )
    else:
        await update.message.reply_text("❌ Erreur lors de la génération du lien de paiement.")

# Start the app
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("buy", buy))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(handle_callback))
app.run_polling()

