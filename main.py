import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# Chargement des variables d'environnement
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")

# Chargement ou création du fichier utilisateurs
user_file = Path("users.json")
if not user_file.exists():
    user_file.write_text(json.dumps({}))

with open(user_file, "r") as f:
    users = json.load(f)

# Commande /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    if user_id not in users:
        users[user_id] = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "credits": 0,
            "license": False,
            "joined": datetime.now().isoformat()
        }
        with open("users.json", "w") as f:
            json.dump(users, f, indent=4)

    heure = datetime.now().strftime('%H:%M:%S')
    keyboard = [
        [InlineKeyboardButton("📞 SIP", callback_data="sip"),
         InlineKeyboardButton("📨 SMS", callback_data="sms")],
        [InlineKeyboardButton("💳 Recharger", callback_data="recharger"),
         InlineKeyboardButton("📊 Admin", callback_data="admin")]
    ]
    msg = (
        f"👋 Bienvenue <b>{user.first_name}</b> !\n\n"
        f"🆔 <code>{user.id}</code>\n"
        f"💰 Crédits : {users[user_id]['credits']}\n"
        f"🔐 Licence : {'✅ Active' if users[user_id]['license'] else '❌ Inactive'}\n"
        f"🕒 Heure : {heure}\n"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# Commande /acheter (NOWPayments)
async def acheter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    body = {
        "price_amount": 120,
        "price_currency": "eur",
        "pay_currency": "usdttrc20",
        "ipn_callback_url": "https://nowpayments.io",
        "order_id": f"{user_id}_{datetime.now().timestamp()}",
        "order_description": "Licence 2 mois LemonSpoofer"
    }
    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.nowpayments.io/v1/invoice", json=body, headers=headers) as resp:
            data = await resp.json()
            if "invoice_url" in data:
                await update.message.reply_text(f"🔐 Paiement : {data['invoice_url']}")
            else:
                await update.message.reply_text(f"⚠️ Erreur NOWPayments :\n{data}")

# Admin : /admin
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Accès refusé.")
        return
    total_credits = sum(u.get("credits", 0) for u in users.values())
    total_licenses = sum(1 for u in users.values() if u.get("license"))
    total_sales = total_licenses * 120
    msg = (
        "📊 <b>Statistiques LemonSpoofer</b>\n\n"
        f"👥 Utilisateurs : {len(users)}\n"
        f"🔐 Licences actives : {total_licenses}\n"
        f"💳 Crédits totaux : {total_credits}\n"
        f"💰 Ventes totales : {total_sales} €"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

# Broadcast admin
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Tu n’es pas autorisé à envoyer un message groupé.")
        return
    if not context.args:
        await update.message.reply_text("❗ Utilise : /broadcast <message>")
        return
    msg = "📢 " + " ".join(context.args)
    for u in users.values():
        try:
            await context.bot.send_message(chat_id=u["id"], text=msg)
        except:
            continue
    await update.message.reply_text("✅ Message envoyé.")

# Callback bouton admin
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "admin":
        update.message = query.message
        await admin_command(update, context)
    else:
        await query.edit_message_text("❌ Fonction non disponible.")

# Lancement
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("acheter", acheter))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(callback))
    app.run_polling()

