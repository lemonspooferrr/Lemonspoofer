import os
import json
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import threading
import http.server
import socketserver

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
CALLBACK_URL = os.getenv("NOWPAYMENTS_CALLBACK_URL")

# Init user DB
if not Path("users.json").exists():
    with open("users.json", "w") as f:
        json.dump({}, f)

def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=2)

def main_menu(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Accès SIP", callback_data="sip")],
        [InlineKeyboardButton("💬 Accès SMS", callback_data="sms")],
        [InlineKeyboardButton("📲 Caller ID", callback_data="caller_id")],
        [InlineKeyboardButton("🎵 Musique d’attente", callback_data="musique")],
        [InlineKeyboardButton("🛒 Acheter licence (120€)", callback_data="buy")],
        [InlineKeyboardButton("📩 Support", url="https://t.me/LemonCloudSL")]
    ])

# ==== ACHAT LICENCE ==== #
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    cryptos = ["btc", "eth", "ltc", "sol"]

    buttons = [
        [InlineKeyboardButton(f"💰 Payer en {crypto.upper()}", callback_data=f"buy_{crypto}")]
        for crypto in cryptos
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await update.callback_query.message.reply_text(
        f"💳 Choisis ta crypto pour payer la licence (120€) :", reply_markup=keyboard
    )

async def generate_invoice(user_id, amount, crypto, order_prefix=""):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "price_amount": amount,
        "price_currency": "eur",
        "pay_currency": crypto,
        "order_id": f"{order_prefix}{user_id}",
        "ipn_callback_url": CALLBACK_URL,
    }
    r = requests.post(url, json=payload, headers=headers)
    return r.json().get("invoice_url")

# ==== RECHARGE CREDITS ==== #
async def recharge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text(
        "💶 Combien veux-tu recharger ? (min 5€)\nEnvoie un montant en euros.",
        parse_mode="HTML"
    )
    context.user_data["awaiting_recharge"] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_recharge"):
        try:
            amount = float(update.message.text.strip())
            if amount < 5:
                return await update.message.reply_text("❌ Minimum 5€.")
            context.user_data.pop("awaiting_recharge")

            buttons = [
                [InlineKeyboardButton(f"Payer {amount}€ en {c.upper()}", callback_data=f"recharge_{c}_{amount}")]
                for c in ["btc", "eth", "ltc", "sol"]
            ]
            return await update.message.reply_text("💳 Choisis ta crypto :", reply_markup=InlineKeyboardMarkup(buttons))

        except:
            return await update.message.reply_text("❌ Montant invalide.")
    return

# ==== CALLBACK HANDLER ==== #
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "buy":
        return await buy(update, context)
    if data == "recharge":
        return await recharge(update, context)

    if data.startswith("buy_"):
        crypto = data.split("_")[1]
        invoice = await generate_invoice(update.effective_user.id, 120, crypto)
        return await query.edit_message_text(
            f"🧾 Paiement en {crypto.upper()} :\n{invoice}\n\n✅ Une fois payé, la licence s’activera automatiquement."
        )

    if data.startswith("recharge_"):
        _, crypto, amount = data.split("_")
        invoice = await generate_invoice(update.effective_user.id, float(amount), crypto, order_prefix="RECHARGE_")
        return await query.edit_message_text(
            f"🧾 Paiement {amount}€ en {crypto.upper()} :\n{invoice}\n\n✅ Une fois payé, les crédits seront ajoutés."
        )

    users = load_users()
    uid = str(query.from_user.id)
    if data in ["sip", "sms", "caller_id", "musique"]:
        if not users.get(uid, {}).get("license_expiry"):
            return await query.edit_message_text("🚫 Licence requise pour utiliser cette option.")
        log_action(update.effective_user, f'Utilisation fonction : {data}')
        await query.edit_message_text(f"✅ Fonctionnalité {data} activée (simulation)")

# ==== /start ==== #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print("✅ /start déclenché par", user.id)
    log_action(user, '/start command')
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

    user_data = users[uid]
    license_status = "✅ Active" if user_data.get("license_expiry") else "❌ Inactive"

    msg = (
        f"🛰️ <b>Bienvenue sur <u>LemonSpoofer</u>, {user.first_name} !</b>\n\n"
        f"🆔 <b>ID utilisateur :</b> <code>{uid}</code>\n"
        f"💼 <b>Statut licence :</b> {license_status}\n"
        f"💳 <b>Crédits :</b> <code>{user_data['credits']}</code>\n\n"
        f"🔒 <b>Accès restreint :</b> Une licence active est requise pour débloquer les fonctionnalités du service.\n"
        f"💰 <b>Prix de la licence :</b> 120€ pour 2 mois (paiement en crypto).\n\n"
        f"📍 Utilise le menu ci-dessous pour acheter une licence ou contacter le support."
    )
    await update.message.reply_text(msg, reply_markup=main_menu(uid), parse_mode="HTML")

# ==== /admin ==== #
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    users = load_users()
    total_users = len(users)
    total_credits = sum(u.get("credits", 0) for u in users.values())
    total_licenses = sum(1 for u in users.values() if u.get("license_expiry"))
    msg = (
        f"📊 Statistiques :\n"
        f"👥 Utilisateurs : {total_users}\n"
        f"💰 Crédits totaux : {total_credits}\n"
        f"✅ Licences actives : {total_licenses}"
    )
    await update.message.reply_text(msg)

# ==== /help ==== #
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 <b>Aide LemonSpoofer</b>\n\n"
        "🛠️ <b>Fonctionnalités :</b>\n"
        "📞 Accès SIP | 💬 Accès SMS | 📲 Caller ID | 🎵 Musique d’attente\n\n"
        "🪪 <b>Licence :</b> 120€ pour 2 mois (paiement en crypto)\n"
        "💳 <b>Crédits :</b> recharge libre (min 5€)\n\n"
        "🔗 Paiements auto en : BTC, ETH, LTC, SOL\n"
        "📩 Support : @LemonCloudSL"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

# ==== /broadcast ==== #
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    if len(context.args) == 0:
        return await update.message.reply_text("❗ Utilisation : /broadcast <message>")
    
    message = "🔊 <b>Annonce :</b>\n" + " ".join(context.args)
    users = load_users()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=message, parse_mode="HTML")
            count += 1
        except:
            continue
    await update.message.reply_text(f"✅ Message envoyé à {count} utilisateur(s).")

# ==== Logging ==== #
def log_action(user, action):
    logging.info(f"{datetime.now()} - {user.username} ({user.id}) - {action}")
    try:
        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} - {user.username} ({user.id}) - {action}\n")
    except Exception as e:
        print(f"Logging error: {e}")

# ==== BOT INIT ==== #
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("help", help))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Keep alive on Render
def keep_alive():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", 8080), handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=keep_alive).start()
app.run_polling()
