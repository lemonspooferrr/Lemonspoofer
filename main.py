import os
import json
import logging
import requests
import asyncio
from datetime import datetime
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
        [InlineKeyboardButton("📡 État des routes", callback_data="routes")],
        [InlineKeyboardButton("🛒 Acheter licence (120€)", callback_data="buy")],
        [InlineKeyboardButton("📩 Support", url="https://t.me/LemonCloudSL")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_action(user, '/start')
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"👋 /start par @{user.username or 'inconnu'} ({user.id})")

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

    msg = f"""
🍋 <b>Bienvenue sur <u>LemonSpoofer</u>, {user.first_name} !</b>

🎭 <b>Contrôle ton identité numérique</b>
📞 Spoof vocal, SMS anonymes, numéro personnalisé, et plus.

🔓 <b>Licence requise</b> pour débloquer :
• Appels spoofés (SIP)
• Envois de SMS anonymes
• Numéro Caller ID
• Musique d’attente personnalisée

💰 <b>Tarif :</b> 120€ pour 2 mois (Crypto uniquement)
🧾 Paiement automatique & instantané (BTC, ETH, LTC, SOL)

🆔 <b>Ton ID :</b> <code>{uid}</code>
📊 <b>Statut licence :</b> {license_status}
💳 <b>Crédits :</b> <code>{user_data['credits']}</code>

👇 Utilise le menu ci-dessous pour commencer.
📩 Support : @LemonCloudSL
"""
    await update.message.reply_text(msg, reply_markup=main_menu(uid), parse_mode="HTML")

async def etat_routes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_action(user, '📡 État des routes')
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📡 Bouton État des routes cliqué par @{user.username or 'inconnu'} ({user.id})")

    message = await update.callback_query.message.edit_text("📡 Vérification en cours...\n[░░░░░░░░░░] 0%")
    for i in range(1, 11):
        await asyncio.sleep(0.3)
        bar = "█" * i + "░" * (10 - i)
        await message.edit_text(f"📡 Vérification en cours...\n[{bar}] {i*10}%")
    
    final_msg = (
        "📶 <b>État des routes internationales</b> :\n\n"
        "🇫🇷 France : ✅ Fonctionnelle\n"
        "🇧🇪 Belgique : ✅ Fonctionnelle\n"
        "🇬🇧 UK : ✅ Fonctionnelle\n"
        "🇺🇸 USA : ✅ Fonctionnelle\n"
        "🇩🇪 Allemagne : ✅ Fonctionnelle\n"
        "🇨🇭 Suisse : ✅ Fonctionnelle\n"
        "🇨🇦 Canada : ✅ Fonctionnelle\n"
        "🇪🇸 Espagne : ✅ Fonctionnelle\n"
        "🇮🇹 Italie : ✅ Fonctionnelle\n\n"
        "🔁 Optimisation automatique des passerelles en temps réel.\n"
        "🔒 Qualité HD & identification dynamique assurée."
    )
    await message.edit_text(final_msg, parse_mode="HTML")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🛒 Achat licence demandé par @{user.username or 'inconnu'} ({user.id})")

    cryptos = ["btc", "eth", "ltc", "sol"]
    buttons = [
        [InlineKeyboardButton(f"💰 Payer en {crypto.upper()}", callback_data=f"buy_{crypto}")]
        for crypto in cryptos
    ]

    msg = (
        "🪪 <b>Licence LemonSpoofer</b>\n\n"
        "🎯 <b>Contenu :</b> Accès SIP, SMS spoof, Caller ID, musique d’attente\n"
        "⏳ <b>Durée :</b> 2 mois\n"
        "💸 <b>Prix :</b> 120€ (paiement crypto)\n\n"
        "💳 <b>Choisis ta cryptomonnaie :</b>"
    )
    await update.callback_query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

async def generate_invoice(user_id, amount, crypto, order_prefix=""):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "price_amount": amount,
        "price_currency": "eur",
        "pay_currency": crypto,
        "order_id": f"{order_prefix}{user_id}",
        "ipn_callback_url": CALLBACK_URL,
    }
    # Exécution non bloquante dans un thread
    def _post():
        return requests.post(url, json=payload, headers=headers)
    r = await asyncio.to_thread(_post)
    return r.json().get("invoice_url")

async def recharge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("💶 Combien veux-tu recharger ? (min 5€)\nEnvoie un montant en euros.")
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

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "buy": return await buy(update, context)
    if data == "recharge": return await recharge(update, context)
    if data == "routes": return await etat_routes(update, context)

    if data.startswith("buy_"):
        crypto = data.split("_")[1]
        invoice = await generate_invoice(update.effective_user.id, 120, crypto)
        return await query.edit_message_text(f"🧾 Paiement en {crypto.upper()} :\n{invoice}\n\n✅ Une fois payé, la licence s’activera automatiquement.")

    if data.startswith("recharge_"):
        _, crypto, amount = data.split("_")
        invoice = await generate_invoice(update.effective_user.id, float(amount), crypto, order_prefix="RECHARGE_")
        return await query.edit_message_text(f"🧾 Paiement {amount}€ en {crypto.upper()} :\n{invoice}\n\n✅ Une fois payé, les crédits seront ajoutés.")

    users = load_users()
    uid = str(query.from_user.id)
    if data in ["sip", "sms", "caller_id", "musique"]:
        if not users.get(uid, {}).get("license_expiry"):
            return await query.edit_message_text("🚫 Licence requise pour utiliser cette option.")
        log_action(update.effective_user, f'Utilisation fonction : {data}')
        await query.edit_message_text(f"✅ Fonctionnalité {data} activée (simulation)")

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

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 <b>Aide LemonSpoofer</b>\n\n"
        "🛠️ <b>Fonctionnalités :</b>\n"
        "📞 SIP • 💬 SMS spoof • 📲 Caller ID • 🎵 Musique d’attente\n\n"
        "🪪 <b>Licence :</b> 120€ pour 2 mois\n"
        "💳 <b>Crédits :</b> recharge libre (min 5€)\n"
        "🔗 Paiement crypto : BTC, ETH, LTC, SOL\n\n"
        "📩 Support : @LemonCloudSL"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

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

def log_action(user, action):
    logging.info(f"{datetime.now()} - {user.username} ({user.id}) - {action}")
    try:
        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} - {user.username} ({user.id}) - {action}\n")
    except Exception as e:
        print(f"Erreur log : {e}")

# Start
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("help", help))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

def keep_alive():
    handler = http.server.SimpleHTTPRequestHandler
    port = int(os.getenv("PORT", "8080"))
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()
app.run_polling()
