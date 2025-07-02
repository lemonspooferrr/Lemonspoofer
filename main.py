import os
import json
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters
)
from dotenv import load_dotenv
import aiohttp

# Charger les variables d'environnement
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")

# Créer un fichier users.json s'il n'existe pas
if not Path("users.json").exists():
    with open("users.json", "w") as f:
        json.dump({}, f)

# Fonctions de base
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "credits": 0,
        "is_licensed": False,
        "joined": datetime.now().isoformat()
    }

    with open("users.json", "r") as f:
        users = json.load(f)

    if str(user.id) not in users:
        users[str(user.id)] = user_data
        with open("users.json", "w") as f:
            json.dump(users, f)

    heure = datetime.now().strftime('%H:%M:%S')
    msg = (
        "🔷 Bienvenue sur LemonSpoofer🍋\n"
        f"🟢 Statut : En ligne\n"
        f"🆔 ID : {user.id}\n"
        f"💰 Crédits : {users[str(user.id)]['credits']}\n"
        f"🕒 Heure : {heure}\n\n"
        "Utilise /acheter pour obtenir ta licence. 🚀"
    )
    buttons = [
        [InlineKeyboardButton("📞 Accès SIP", callback_data="sip"),
         InlineKeyboardButton("💳 Recharger", callback_data="recharger")],
        [InlineKeyboardButton("🪪 Caller ID", callback_data="caller"),
         InlineKeyboardButton("🎵 Musique d’attente", callback_data="musique")],
        [InlineKeyboardButton("💬 SMS Sender", callback_data="sms"),
         InlineKeyboardButton("📧 Mail Sender", callback_data="mail")],
        [InlineKeyboardButton("⚙️ Paramètres", callback_data="params")]
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

async def acheter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    uid = f"{user_id}_{datetime.now().timestamp()}"
    body = {
        "price_amount": 120,
        "price_currency": "eur",
        "pay_currency": "usdtrc20",
        "ipn_callback_url": "https://nowpayments.io",
        "order_id": uid,
        "order_description": "Licence 2 mois LemonSpoofer"
    }
    headers = {"x-api-key": NOWPAYMENTS_API_KEY}

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.nowpayments.io/v1/invoice", json=body, headers=headers) as resp:
            data = await resp.json()
            if "invoice_url" in data:
                await update.message.reply_text(f"🔐 Paiement licence : {data['invoice_url']}")
            else:
                await update.message.reply_text("⚠️ Erreur lors de la création du paiement.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != os.getenv("ADMIN_ID"):
        await update.message.reply_text("❌ Tu n’es pas autorisé à envoyer un broadcast.")
        return
    if not context.args:
        await update.message.reply_text("❗ Utilise /broadcast <message>")
        return

    message = "📢 " + " ".join(context.args)
    with open("users.json", "r") as f:
        users = json.load(f)
        if isinstance(users, dict):
            users = list(users.values())
    for u in users:
        try:
            await context.bot.send_message(chat_id=u["id"], text=message)
        except:
            continue
    await update.message.reply_text("✅ Message envoyé à tous les utilisateurs.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != os.getenv("ADMIN_ID"):
        await update.message.reply_text("❌ Accès refusé.")
        return
    with open("users.json", "r") as f:
        users = json.load(f)
    total_users = len(users)
    total_licensed = sum(1 for u in users.values() if u.get("is_licensed"))
    total_credits = sum(u.get("credits", 0) for u in users.values())
    msg = (
        "<b>📊 Statistiques LemonSpoofer</b>\n"
        f"👤 Utilisateurs : {total_users}\n"
        f"✅ Licenciés : {total_licensed}\n"
        f"💳 Crédits cumulés : {total_credits}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("acheter", acheter))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.run_polling()
