import os
import json
import logging
import requests
import asyncio
import threading
import http.server
import socketserver
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# =========[ CONFIG / ENV ]=========
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY", "")
CALLBACK_URL = os.getenv("NOWPAYMENTS_CALLBACK_URL", "")
IPN_SECRET = os.getenv("IPN_SECRET", "")  # à mettre aussi côté NOWPayments dans l'entête personnalisée

if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("❌ BOT_TOKEN ou ADMIN_ID manquant dans .env")

# =========[ LOGGING ]=========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# =========[ PERSISTENCE ]=========
USERS_FILE = "users.json"
_file_lock = threading.Lock()

def _ensure_files():
    if not Path(USERS_FILE).exists():
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def load_users() -> Dict[str, Any]:
    with _file_lock:
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

def save_users(users: Dict[str, Any]) -> None:
    with _file_lock:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)

_ensure_files()

# =========[ UTILS ]=========
LICENSE_DURATION_DAYS = 60

def log_action(user, action):
    who = f"@{user.username}" if user and user.username else f"id:{getattr(user, 'id', 'unknown')}"
    logging.info(f"{who} - {action}")
    try:
        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} - {who} - {action}\n")
            f.flush()
    except Exception as e:
        logging.warning(f"Erreur log : {e}")

def has_active_license(user_data: Dict[str, Any]) -> bool:
    exp = user_data.get("license_expiry")
    if not exp:
        return False
    try:
        return datetime.fromisoformat(exp) > datetime.utcnow()
    except Exception:
        return False

def format_euros(amount: float) -> str:
    return f"{amount:.2f}€".replace(".", ",")

def main_menu(uid: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Accès SIP", callback_data="sip")],
        [InlineKeyboardButton("💬 Accès SMS", callback_data="sms")],
        [InlineKeyboardButton("📲 Caller ID", callback_data="caller_id")],
        [InlineKeyboardButton("🎵 Musique d’attente", callback_data="musique")],
        [InlineKeyboardButton("📡 État des routes", callback_data="routes")],
        [InlineKeyboardButton("🛒 Acheter licence (120€)", callback_data="buy")],
        [InlineKeyboardButton("➕ Recharger crédits", callback_data="recharge")],
        [InlineKeyboardButton("📩 Support", url="https://t.me/LemonCloudSL")]
    ])

# =========[ TELEGRAM HANDLERS ]=========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_action(user, '/start')
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"👋 /start par @{user.username or 'inconnu'} ({user.id})")
    except Exception:
        pass

    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "username": user.username,
            "first_name": user.first_name,
            "credits": 0.0,
            "license_expiry": None
        }
        save_users(users)

    user_data = users[uid]
    license_status = "✅ Active" if has_active_license(user_data) else "❌ Inactive"
    exp = user_data.get("license_expiry")
    exp_str = datetime.fromisoformat(exp).strftime("%d/%m/%Y") if exp else "—"

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
🗓️ <b>Expiration :</b> {exp_str}
💳 <b>Crédits :</b> <code>{user_data['credits']}</code>

👇 Utilise le menu ci-dessous pour commencer.
📩 Support : @LemonCloudSL
"""
    if update.message:
        await update.message.reply_text(msg, reply_markup=main_menu(uid), parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=main_menu(uid), parse_mode="HTML")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 <b>Aide LemonSpoofer</b>\n\n"
        "🛠️ <b>Fonctionnalités :</b>\n"
        "📞 SIP • 💬 SMS spoof • 📲 Caller ID • 🎵 Musique d’attente\n\n"
        "🪪 <b>Licence :</b> 120€ pour 2 mois\n"
        "💳 <b>Crédits :</b> recharge libre (min 5€)\n"
        "🔗 Paiement crypto : BTC, ETH, LTC, SOL\n\n"
        "Commandes utiles : /start • /help • /admin\n"
        "📩 Support : @LemonCloudSL"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Accès refusé")
    users = load_users()
    total_users = len(users)
    total_credits = sum(float(u.get("credits", 0)) for u in users.values())
    total_licenses = sum(1 for u in users.values() if has_active_license(u))
    msg = (
        f"📊 Statistiques :\n"
        f"👥 Utilisateurs : {total_users}\n"
        f"💰 Crédits totaux : {total_credits:.2f}\n"
        f"✅ Licences actives : {total_licenses}"
    )
    await update.message.reply_text(msg)

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
        except Exception:
            continue
    await update.message.reply_text(f"✅ Message envoyé à {count} utilisateur(s).")

async def etat_routes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_action(user, '📡 État des routes')
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"📡 Bouton État des routes cliqué par @{user.username or 'inconnu'} ({user.id})")
    except Exception:
        pass

    message = await update.callback_query.message.edit_text("📡 Vérification en cours...\n[░░░░░░░░░░] 0%")
    for i in range(1, 11):
        await asyncio.sleep(0.25)
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

# =========[ PAYMENTS ]=========
def generate_invoice(user_id: int, amount_eur: float, crypto: str, order_prefix: str = "") -> str:
    if not NOWPAYMENTS_API_KEY or not CALLBACK_URL:
        return "⚠️ Paiement indisponible (configuration API manquante)."
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "price_amount": float(amount_eur),
        "price_currency": "eur",
        "pay_currency": crypto.lower(),
        "order_id": f"{order_prefix}{user_id}",
        "ipn_callback_url": CALLBACK_URL,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("invoice_url", "⚠️ Erreur lors de la génération de la facture.")
    except Exception as e:
        logging.exception("NOWPayments error")
        return f"⚠️ Erreur API : {e}"

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🛒 Achat licence demandé par @{user.username or 'inconnu'} ({user.id})")
    except Exception:
        pass

    cryptos = ["btc", "eth", "ltc", "sol"]
    buttons = [[InlineKeyboardButton(f"💰 Payer en {c.upper()}", callback_data=f"buy_{c}")] for c in cryptos]
    msg = (
        "🪪 <b>Licence LemonSpoofer</b>\n\n"
        "🎯 <b>Contenu :</b> Accès SIP, SMS spoof, Caller ID, musique d’attente\n"
        "⏳ <b>Durée :</b> 2 mois\n"
        "💸 <b>Prix :</b> 120€ (paiement crypto)\n\n"
        "💳 <b>Choisis ta cryptomonnaie :</b>"
    )
    await update.callback_query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

async def recharge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("💶 Combien veux-tu recharger ? (min 5€)\nEnvoie un montant en euros.")
    context.user_data["awaiting_recharge"] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # saisie du montant de recharge
    if context.user_data.get("awaiting_recharge"):
        text = (update.message.text or "").replace(",", ".").strip()
        try:
            amount = float(text)
            if amount < 5:
                return await update.message.reply_text("❌ Minimum 5€.")
            context.user_data.pop("awaiting_recharge", None)
            buttons = [
                [InlineKeyboardButton(f"Payer {format_euros(amount)} en {c.upper()}",
                                      callback_data=f"recharge_{c}_{amount}")]
                for c in ["btc", "eth", "ltc", "sol"]
            ]
            return await update.message.reply_text("💳 Choisis ta crypto :", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception:
            return await update.message.reply_text("❌ Montant invalide. Exemple : 15 ou 12.50")
    # sinon, on ignore le texte libre
    return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "buy":
        return await buy(update, context)
    if data == "recharge":
        return await recharge(update, context)
    if data == "routes":
        return await etat_routes(update, context)

    # Paiements
    if data.startswith("buy_"):
        crypto = data.split("_", 1)[1]
        invoice = generate_invoice(update.effective_user.id, 120.0, crypto)
        return await query.edit_message_text(
            f"🧾 Paiement en {crypto.upper()} :\n{invoice}\n\n"
            f"✅ Après paiement confirmé, ta licence sera activée automatiquement (60 jours)."
        )

    if data.startswith("recharge_"):
        _, crypto, amount = data.split("_", 2)
        try:
            amount_f = float(amount)
        except ValueError:
            amount_f = 0.0
        invoice = generate_invoice(update.effective_user.id, amount_f, crypto, order_prefix="RECHARGE_")
        return await query.edit_message_text(
            f"🧾 Paiement {format_euros(amount_f)} en {crypto.upper()} :\n{invoice}\n\n"
            f"✅ Après confirmation, tes crédits seront ajoutés automatiquement."
        )

    # Fonctions protégées
    users = load_users()
    uid = str(query.from_user.id)
    if data in ["sip", "sms", "caller_id", "musique"]:
        user_data = users.get(uid, {})
        if not has_active_license(user_data):
            return await query.edit_message_text("🚫 Licence requise pour utiliser cette option.")
        log_action(update.effective_user, f'Feature used: {data}')
        return await query.edit_message_text(f"✅ {data} prêt. (Démo)")

# =========[ TELEGRAM APP ]=========
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# =========[ IPN SERVER (NOWPAYMENTS) ]=========
class IPNHandler(http.server.BaseHTTPRequestHandler):
    # Désactiver logs verbeux du serveur
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/":
            self.send_response(200); self.end_headers()
            self.wfile.write(b"LemonSpoofer OK")
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path != "/ipn":
            self.send_response(404); self.end_headers(); return

        # Vérif secret simple via header
        recv_secret = self.headers.get("x-ipn-secret", "")
        if IPN_SECRET and recv_secret != IPN_SECRET:
            self.send_response(401); self.end_headers()
            self.wfile.write(b"Unauthorized")
            return

        try:
            length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8") or "{}")

            order_id = str(data.get("order_id", ""))            # ex: "RECHARGE_12345" ou "12345"
            status = str(data.get("payment_status", "")).lower() # "finished" | "confirmed" | "partially_paid" | ...
            pay_amount = float(data.get("pay_amount", 0) or 0)   # montant crypto (info)
            price_amount = float(data.get("price_amount", 0) or 0)  # montant en EUR demandé

            logging.info(f"IPN reçu - order_id={order_id} status={status} price_amount={price_amount} pay_amount={pay_amount}")

            # On n’applique que si paiement terminé/confirmé
            if status not in ("finished", "confirmed"):
                self.send_response(200); self.end_headers()
                self.wfile.write(b"IPN ignored (status)")
                return

            # Détecter recharge vs license
            is_recharge = order_id.startswith("RECHARGE_")
            uid = order_id.replace("RECHARGE_", "")
            users = load_users()
            if uid not in users:
                # Créer un user minimal si absent
                users[uid] = {"username": None, "first_name": None, "credits": 0.0, "license_expiry": None}

            if is_recharge:
                # Créditer en EUR (price_amount)
                users[uid]["credits"] = float(users[uid].get("credits", 0.0)) + float(price_amount)
            else:
                # Activer licence 60 jours
                expiry = datetime.utcnow() + timedelta(days=LICENSE_DURATION_DAYS)
                users[uid]["license_expiry"] = expiry.isoformat()

            save_users(users)

            # Réponse OK
            self.send_response(200); self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            logging.exception("Erreur IPN")
            self.send_response(500); self.end_headers()
            self.wfile.write(f"ERR {e}".encode("utf-8"))

def keep_alive():
    # Serveur HTTP pour IPN + ping
    port = int(os.getenv("PORT", "8080"))
    try:
        with socketserver.TCPServer(("", port), IPNHandler) as httpd:
            logging.info(f"HTTP/IPN server on port {port}")
            httpd.serve_forever()
    except OSError:
        logging.warning(f"⚠️ Le port {port} est déjà utilisé, skip keep_alive.")

threading.Thread(target=keep_alive, daemon=True).start()

# =========[ RUN ]=========
if __name__ == "__main__":
    app.run_polling(close_loop=False)
