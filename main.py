import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import aiohttp
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# 🔐 Chargement des variables .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")

# 📁 Initialisation des fichiers
for f in ["users.json", "credits.json", "licenses.json"]:
    if not Path(f).exists():
        with open(f, "w") as file:
            json.dump({}, file)

# 📦 Utilitaires JSON
def load(file): return json.load(open(file, "r"))
def save(file, data): json.dump(data, open(file, "w"), indent=2)

# 📋 Menu principal
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Accès SIP", callback_data="sip"),
         InlineKeyboardButton("💬 SMS Sender", callback_data="sms")],
        [InlineKeyboardButton("🆔 Caller ID", callback_data="caller"),
         InlineKeyboardButton("🎵 Musique", callback_data="musique")],
        [InlineKeyboardButton("💳 Recharger", callback_data="recharger"),
         InlineKeyboardButton("📊 Admin", callback_data="admin")]
    ])

# 🟢 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load("users.json")
    credits = load("credits.json")
    licenses = load("licenses.json")

    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "username": user.username,
            "first_name": user.first_name,
            "date": datetime.now().isoformat()
        }
        save("users.json", users)
    if uid not in credits:
        credits[uid] = 0
        save("credits.json", credits)

    heure = datetime.now().strftime("%H:%M:%S")
    msg = (
        f"🔷 Bienvenue sur LemonSpoofer 🍋

"
        f"🟢 Statut : En ligne
"
        f"🆔 ID : <code>{user.id}</code>
"
        f"💰 Crédits : {credits[uid]}
"
        f"🔑 Licence : {'✅ Active' if uid in licenses else '❌ Inactive'}
"
        f"🕒 Heure : {heure}

"
        f"Utilise /acheter pour la licence. 🚀"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=main_menu())

# 🧾 Callback boutons
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    licenses = load("licenses.json")
    if query.data == "admin":
        if uid != str(ADMIN_ID):
            await query.edit_message_text("⛔ Accès refusé.")
            return
        users = load("users.json")
        credits = load("credits.json")
        stats = (
            f"📊 Statistiques :
"
            f"👥 Utilisateurs : {len(users)}
"
            f"🔐 Licences : {len(load('licenses.json'))}
"
            f"💰 Crédits totaux : {sum(credits.values())}"
        )
        await query.edit_message_text(stats)
    elif uid not in licenses:
        await query.edit_message_text("❌ Tu n’as pas de licence active. Utilise /acheter.")
    else:
        await query.edit_message_text(f"✅ Accès accordé à : {query.data}")

# 💳 /acheter licence 120€
async def acheter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    headers = {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}
    body = {
        "price_amount": 120,
        "price_currency": "eur",
        "pay_currency": "usdttrc20",
        "ipn_callback_url": "https://nowpayments.io",
        "order_id": uid,
        "order_description": "Licence 2 mois LemonSpoofer"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.nowpayments.io/v1/invoice", headers=headers, json=body) as resp:
            res = await resp.json()
            if "invoice_url" in res:
                await update.message.reply_text(f"🔗 Paiement licence : {res['invoice_url']}")
            else:
                await update.message.reply_text("❌ Erreur lors du paiement.")

# 💰 /recharger crédits 5€
async def recharger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    headers = {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}
    body = {
        "price_amount": 5,
        "price_currency": "eur",
        "pay_currency": "usdttrc20",
        "ipn_callback_url": "https://nowpayments.io",
        "order_id": uid,
        "order_description": "Recharge crédits LemonSpoofer"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.nowpayments.io/v1/invoice", headers=headers, json=body) as resp:
            res = await resp.json()
            if "invoice_url" in res:
                await update.message.reply_text(f"🔗 Paiement recharge : {res['invoice_url']}")
            else:
                await update.message.reply_text("❌ Erreur NOWPayments.")

# 📡 Vérification automatique paiements (simulation basique)
async def check_payments(app):
    while True:
        await asyncio.sleep(30)
        async with aiohttp.ClientSession() as session:
            headers = {"x-api-key": NOWPAYMENTS_API_KEY}
            async with session.get("https://api.nowpayments.io/v1/payment") as resp:
                res = await resp.json()
                for tx in res.get("data", []):
                    if tx["payment_status"] == "finished":
                        uid = tx["order_id"]
                        if "licence" in tx["order_description"].lower():
                            licenses = load("licenses.json")
                            licenses[uid] = {
                                "activated": datetime.now().isoformat(),
                                "expires": "2 mois"
                            }
                            save("licenses.json", licenses)
                        elif "recharge" in tx["order_description"].lower():
                            credits = load("credits.json")
                            credits[uid] = credits.get(uid, 0) + 500
                            save("credits.json", credits)

# ▶️ Lancement principal
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("acheter", acheter))
    app.add_handler(CommandHandler("recharger", recharger))
    app.add_handler(CallbackQueryHandler(callback_handler))
    asyncio.create_task(check_payments(app))
    await app.run_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
