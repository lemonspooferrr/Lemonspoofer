import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

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
        [InlineKeyboardButton("📩 Support", url="https://t.me/LemonSupportSL")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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

    now = datetime.now().strftime('%H:%M:%S')
    user_data = users[uid]
    license_status = "✅ Active" if user_data.get("license_expiry") else "❌ Inactive"

    msg = (
        f"👋 Bienvenue sur Lemon Spoofer {user.first_name} !\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"💳 Crédits : {user_data['credits']}\n"
        f"🪪 Licence : {license_status}\n"
        f"🕒 Heure : {now}"
    )
    await update.message.reply_text(msg, reply_markup=main_menu(uid), parse_mode="HTML")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💳 Pour acheter ta licence (120€), envoie la somme sur l'une des adresses suivantes :\n\n"
        "💰 Bitcoin (BTC) : <code>bc1q2zzg5unqtl4fvegzv6ehhevyrpkeasm4yzx5z4</code>\n"
        "🪙 Solana (SOL) : <code>2WXPZuqUDpwHfnkhR45CyUnj2g7HULMMX5xje8GzDGrT</code>\n"
        "🧠 Ethereum (ETH) : <code>0x621A53AB204513fFC5AeacC5bd9bfe15a42Cf2D0</code>\n\n"
        "📩 Puis clique sur l’un des boutons ci-dessous."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ J’ai payé", callback_data="paid")],
        [InlineKeyboardButton("➕ Recharger crédits", callback_data="recharge")]
    ])
    await update.callback_query.message.reply_text(msg, reply_markup=keyboard, parse_mode="HTML")

async def recharge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💸 Recharge disponible à partir de 5€ minimum. Merci d’envoyer sur :\n\n"
        "💰 Bitcoin (BTC) : <code>bc1q2zzg5unqtl4fvegzv6ehhevyrpkeasm4yzx5z4</code>\n"
        "📩 Puis clique sur '✅ J’ai payé' ou contacte @LemonSupportSL."
    )
    log_action(update.effective_user, 'Recharge demandée')
    await context.bot.send_message(chat_id=ADMIN_ID, text=f'🔄 Recharge demandée par @{update.effective_user.username} ({update.effective_user.id})')
    await update.callback_query.message.reply_text(msg, parse_mode="HTML")

async def paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_action(user, '/start command')
    log_action(update.effective_user, '✅ J’ai payé')
    await context.bot.send_message(chat_id=ADMIN_ID, text=f'🚨 Paiement signalé par @{update.effective_user.username} ({update.effective_user.id})')
    await update.callback_query.message.reply_text("🕵️ Paiement reçu ou en attente de validation. Tu seras notifié sous peu.")
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🔔 L'utilisateur @{user.username} ({user.id}) a cliqué sur ✅ J’ai payé."
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "buy":
        log_action(update.effective_user, 'Ouverture menu achat licence')
        await context.bot.send_message(chat_id=ADMIN_ID, text=f'🛒 Menu achat ouvert par @{update.effective_user.username} ({update.effective_user.id})')
        return await buy(update, context)
    if data == "paid":
        return await paid_callback(update, context)
    if data == "recharge":
        return await recharge(update, context)

    users = load_users()
    uid = str(query.from_user.id)
    if data in ["sip", "sms", "caller_id", "musique"]:
        if not users.get(uid, {}).get("license_expiry"):
            return await query.edit_message_text("🚫 Licence requise pour utiliser cette option.")
        log_action(update.effective_user, f'Utilisation fonction : {data}')
        await context.bot.send_message(chat_id=ADMIN_ID, text=f'📲 @{update.effective_user.username} ({update.effective_user.id}) a utilisé : {data}')
        await query.edit_message_text(f"✅ Fonctionnalité {data} activée (simulation)")


# Setup logging
logging.basicConfig(
    filename="logs.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_action(user, action):
    logging.info(f"User {user.username} ({user.id}) - {action}")

    try:
        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} - {user.username} ({user.id}) - {action}\n")
    except Exception as e:
        print(f"Logging error: {e}")


async def activate_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    try:
        args = context.args
        uid = args[0]
        days = int(args[1]) if len(args) > 1 else 60
        users = load_users()
        if uid not in users:
            return await update.message.reply_text("❌ Utilisateur introuvable.")
        expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        users[uid]["license_expiry"] = expiry_date
        save_users(users)
        log_action(update.effective_user, f"/active {uid} {days} jours")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f'🔓 Licence activée pour {uid} ({days} jours)')
        await update.message.reply_text(f"✅ Licence activée pour l'utilisateur {uid} jusqu’au {expiry_date}.")
    except:
        await update.message.reply_text("❗ Utilisation : /active <id> [jours]")

async def add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    try:
        uid = context.args[0]
        amount = int(context.args[1])
        users = load_users()
        if uid not in users:
            return await update.message.reply_text("❌ Utilisateur introuvable.")
        users[uid]["credits"] += amount
        save_users(users)
        log_action(update.effective_user, f"/credits {uid} +{amount}")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f'💰 Crédit ajouté : {uid} (+{amount})')
        await update.message.reply_text(f"✅ {amount} crédits ajoutés à l’utilisateur {uid}.")
    except:
        await update.message.reply_text("❗ Utilisation : /credits <id> <montant>")


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
    log_action(update.effective_user, "/admin consulté")
    await update.message.reply_text(msg)



async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    try:
        with open("logs.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()[-10:]
            content = "".join(lines)
        await update.message.reply_text(f"📝 Derniers logs :\n\n<code>{content}</code>", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text("❌ Impossible de lire les logs.")



async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 <b>Aide LemonSpoofer</b>\n\n"
        "🛠️ <b>Fonctionnalités disponibles :</b>\n"
        "📞 <b>Accès SIP</b> – Fonction VoIP\n"
        "💬 <b>Accès SMS</b> – Envoi de SMS via spoof\n"
        "📲 <b>Caller ID</b> – Modifier ton numéro d’appel\n"
        "🎵 <b>Musique d’attente</b> – Personnalisation\n\n"
        "🪪 <b>Licence :</b> Obligatoire pour utiliser les fonctionnalités.\n"
        "🔓 Pour acheter, clique sur 🛒 Acheter licence.\n"
        "⚠️ Tu peux payer via BTC, SOLANA ou ETH.\n\n"
        "💳 <b>Crédits :</b> Utiles pour certaines actions. Recharge via ➕ Recharger crédits.\n"
        "✅ Clique sur “J’ai payé” pour alerter un admin après paiement.\n\n"
        "📩 Besoin d’aide ? Contacte : @LemonSupportSL"
    )
    await update.message.reply_text(msg, parse_mode="HTML")



async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")

    msg = ' '.join(context.args)
    if not msg:
        return await update.message.reply_text("❗ Utilise: /broadcast Votre message")

    users = load_users()
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=msg)
            sent += 1
        except:
            continue

    log_action(update.effective_user, f"/broadcast envoyé à {sent} utilisateurs")
    await update.message.reply_text(f"✅ Message envoyé à {sent} utilisateurs.")


# Appel bot
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("logs", logs))
app.add_handler(CommandHandler("help", help))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CommandHandler("active", activate_license))
app.add_handler(CommandHandler("credits", add_credits))
app.add_handler(CallbackQueryHandler(handle_callback))
app.run_polling()
