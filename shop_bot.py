import os
import uuid
import json
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# ─────────────────────────────────────────────────────────────
# הגדרות וסידור לוגים
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# קבלת ADMIN_ID מה־env
# ─────────────────────────────────────────────────────────────
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))

# ─────────────────────────────────────────────────────────────
# Conversation states
# ─────────────────────────────────────────────────────────────
(
    UPLOAD_IMG,
    SET_SHOP,
    SET_TITLE,
    SET_DESC,
    SET_PRICE,
    PURCHASE_WAIT
) = range(6)

# In-memory storage זמני לרישומי Upload
_upload_sessions: dict[int, dict] = {}

# ─────────────────────────────────────────────────────────────
# Helpers ליצירת ספריות
# ─────────────────────────────────────────────────────────────
def ensure_dirs(path: str):
    os.makedirs(path, exist_ok=True)

def shop_dir(name: str) -> str:
    return os.path.join("shops", name)

def card_dir(shop: str) -> str:
    return os.path.join(shop_dir(shop), "cards")

def purchases_dir(shop: str, card_id: str) -> str:
    return os.path.join(shop_dir(shop), "purchases", card_id)

# ─────────────────────────────────────────────────────────────
# תפריט ראשי דינמי (Admin vs Customer)
# ─────────────────────────────────────────────────────────────
def main_menu(is_admin: bool) -> InlineKeyboardMarkup:
    if is_admin:
        buttons = [
            [InlineKeyboardButton("🚀 Launch All Shops", callback_data="admin_launch")],
            [InlineKeyboardButton("📊 View Sales",     callback_data="admin_sales")],
            [InlineKeyboardButton("💳 Customer View",  callback_data="switch_customer")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("🛍 Browse Shop",   callback_data="cust_browse")],
            [InlineKeyboardButton("🔑 My Tokens",     callback_data="cust_tokens")],
            [InlineKeyboardButton("⚙️ Admin View",    callback_data="switch_admin")]
        ]
    return InlineKeyboardMarkup(buttons)

# ─────────────────────────────────────────────────────────────
# /menu → הצגת התפריט הראשי
# ─────────────────────────────────────────────────────────────
async def show_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    is_admin = (uid == ADMIN_ID)
    await update.message.reply_text(
        "בחר אופציה בתפריט:",
        reply_markup=main_menu(is_admin)
    )

# ─────────────────────────────────────────────────────────────
# Callback לניווט בתפריטים ולביצוע פעולות
# ─────────────────────────────────────────────────────────────
async def callback_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    is_admin = (uid == ADMIN_ID)
    key = query.data

    # מעבר בין מצבי תצוגה
    if key == "switch_admin" and not is_admin:
        return await query.edit_message_text("🛠 Admin View:", reply_markup=main_menu(True))
    if key == "switch_customer" and is_admin:
        return await query.edit_message_text("🙂 Customer View:", reply_markup=main_menu(False))

    # Admin: השקה מחדש של כל ה־Shop Bots
    if key == "admin_launch" and is_admin:
        # פה אפשר להתקשר ל־bot_manager.main() במידת הצורך
        return await query.edit_message_text("✅ All Shop Bots launched.")

    # Admin: סיכום מכירות לכל חנות
    if key == "admin_sales" and is_admin:
        lines = []
        root = "shops"
        if os.path.isdir(root):
            for shop in os.listdir(root):
                sales_root = os.path.join(root, shop, "purchases")
                count = 0
                if os.path.isdir(sales_root):
                    for card in os.listdir(sales_root):
                        folder = os.path.join(sales_root, card)
                        count += len(os.listdir(folder))
                lines.append(f"{shop}: {count} sales")
        text = "\n".join(lines) or "אין מכירות עדיין."
        return await query.edit_message_text(text)

    # Customer: גלישה בחנויות
    if key == "cust_browse":
        buttons = []
        for shop in os.listdir("shops"):
            buttons.append([InlineKeyboardButton(shop, callback_data=f"shop_{shop}")])
        kb = InlineKeyboardMarkup(buttons)
        return await query.edit_message_text("בחר חנות:", reply_markup=kb)

    # Customer: הצגת קלפים בחנות
    if key.startswith("shop_"):
        shop = key.split("_",1)[1]
        cards = os.listdir(card_dir(shop))
        buttons = [[InlineKeyboardButton(c.split(".")[0], callback_data=f"buy_{shop}_{c.split('.')[0]}")] for c in cards]
        kb = InlineKeyboardMarkup(buttons)
        return await query.edit_message_text(f"📋 קלפים ב־{shop}:", reply_markup=kb)

    # Customer: רכישת קלף ויצירת NFT Token
    if key.startswith("buy_"):
        _, shop, card_id = key.split("_",2)
        token = str(uuid.uuid4())
        folder = purchases_dir(shop, card_id)
        ensure_dirs(folder)
        token_path = os.path.join(folder, f"{uid}.token")
        with open(token_path, "w") as f:
            f.write(token)
        text = f"✅ רכישה בוצעה!\nYour NFT-Token: `{token}`"
        return await query.edit_message_text(text, parse_mode="Markdown")

    # Customer: הצגת ה־Tokens שברשותו
    if key == "cust_tokens":
        lines = []
        root = "shops"
        for shop in os.listdir(root):
            sales_root = os.path.join(root, shop, "purchases")
            if not os.path.isdir(sales_root):
                continue
            for card in os.listdir(sales_root):
                tf = os.path.join(sales_root, card, f"{uid}.token")
                if os.path.isfile(tf):
                    token = open(tf).read().strip()
                    lines.append(f"{shop}/{card}: `{token}`")
        text = "\n".join(lines) or "אין לך NFT-Tokens."
        return await query.edit_message_text(text, parse_mode="Markdown")

# ─────────────────────────────────────────────────────────────
# Registration של Handlers
# ─────────────────────────────────────────────────────────────
def register_handlers(app):
    # תפריט דינמי
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CallbackQueryHandler(callback_menu))

    # (ניתן להוסיף כאן גם handlers של upload_card, purchase if דרוש)
