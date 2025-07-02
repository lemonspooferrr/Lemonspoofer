import os
import json
import aiohttp
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")

# Load/save user database
USERS_FILE = "users.json"
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Main menu
def main_menu():
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
    license_status = users[uid]['license_expiry'] or '❌ Inactive'
    msg = (
        f"👋 Bienvenue {user.first_name} !

"
        f"🆔 ID : <code>{user.id}</code>
"
        f"💳 Crédits : {users[uid]['credits']}
"
        f"📅 Licence : {license_status}
"
        f"🕒 Heure : {time_str}"
    )
    await update.message.reply_text(msg, reply_markup=main_menu(), parse_mode="HTML")

# Admin Stats
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    users = load_users()
    total_users = len(users)
    total_credits = sum(u.get("credits", 0) for u in users.values())
    total_licenses = sum(1 for u in users.values() if u.get("license_expiry"))
    msg = (
        "📊 Statistiques :
"
        f"👥 Utilisateurs : {total_users}
"
        f"💰 Crédits totaux : {total_credits}
"
        f"✅ Licences actives : {total_licenses}"
    )
    await update.message.reply_text(msg)

# Broadcast
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    msg = ' '.join(context.args)
    if not msg:
        return await update.message.reply_text("❗ Utilise: /broadcast Votre message ici")
    users = load_users()
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=msg)
        except:
            pass
    await update.message.reply_text("✅ Message envoyé")

# Buy Licence
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    async with aiohttp.ClientSession() as session:
        body = {
            "price_amount": 120,
            "price_currency": "eur",
            "pay_currency": "usdttrc20",
            "order_id": user_id,
            "order_description": "Licence LemonSpoofer 2 mois"
        }
        headers = {
            "x-api-key": NOWPAYMENTS_API_KEY,
            "Content-Type": "application/json"
        }
        async with session.post("https://api.nowpayments.io/v1/invoice", json=body, headers=headers) as resp:
            data = await resp.json()
            invoice_url = data.get("invoice_url")
            if invoice_url:
                await update.callback_query.message.reply_text(f"🔐 Paiement ici : {invoice_url}")
            else:
                await update.callback_query.message.reply_text("❌ Erreur de paiement")

# Recharge crédits
async def recharge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    async with aiohttp.ClientSession() as session:
        body = {
            "price_amount": 5,
            "price_currency": "eur",
            "pay_currency": "usdttrc20",
            "order_id": user_id,
            "order_description": "Recharge crédits LemonSpoofer"
        }
        headers = {
            "x-api-key": NOWPAYMENTS_API_KEY,
            "Content-Type": "application/json"
        }
        async with session.post("https://api.nowpayments.io/v1/invoice", json=body, headers=headers) as resp:
            data = await resp.json()
            invoice_url = data.get("invoice_url")
            if invoice_url:
                await update.callback_query.message.reply_text(
                    "💸 Recharge tes crédits ici:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Payer maintenant", url=invoice_url)]])
                )
            else:
                await update.callback_query.message.reply_text("❌ Erreur de paiement")

# Callback
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    users = load_users()
    uid = str(query.from_user.id)
    user_data = users.get(uid, {})
    license_ok = user_data.get("license_expiry")

    if data == "buy":
        return await buy(update, context)
    elif data == "recharge":
        return await recharge(update, context)
    elif data in ["sip", "sms", "caller_id", "musique"]:
        if not license_ok:
            return await query.message.reply_text("🚫 Licence requise pour utiliser cette option.")
        await query.message.reply_text(f"✅ Fonctionnalité {data} activée (simulation)")

# Run app
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(handle_callback))
app.run_polling()
