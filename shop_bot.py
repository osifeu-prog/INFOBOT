import os
import json
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# States
UPLOAD_IMAGE, SET_SHOP, SET_TITLE, SET_DESC, SET_PRICE, PURCHASE_WAIT = range(6)
_upload_sessions: dict[int, dict] = {}

def ensure_dirs(path: str):
    os.makedirs(path, exist_ok=True)

def shop_dir(name: str) -> str:
    return os.path.join("shops", name)

def card_dir(shop: str) -> str:
    return os.path.join(shop_dir(shop), "cards")

def purchases_dir(shop: str, card_id: str) -> str:
    return os.path.join(shop_dir(shop), "purchases", card_id)

# Upload flow
async def upload_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📤 שלח תמונת קלף (JPEG/PNG).")
    return UPLOAD_IMAGE

async def upload_image(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    _upload_sessions[uid] = {"file_id": update.message.photo[-1].file_id}
    await update.message.reply_text("🏬 בחר שם לחנות:")
    return SET_SHOP

async def set_shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    _upload_sessions[uid]["shop"] = update.message.text.strip()
    ensure_dirs(card_dir(_upload_sessions[uid]["shop"]))
    await update.message.reply_text("🔖 כותרת הקלף:")
    return SET_TITLE

async def set_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    _upload_sessions[uid]["title"] = update.message.text.strip()
    await update.message.reply_text("✏️ תיאור הקלף:")
    return SET_DESC

async def set_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    _upload_sessions[uid]["desc"] = update.message.text.strip()
    await update.message.reply_text("💰 מחיר בשקלים:")
    return SET_PRICE

async def set_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = _upload_sessions.pop(uid)
    try:
        data["price"] = float(update.message.text.strip())
    except ValueError:
        return await update.message.reply_text("❗ מחיר לא חוקי.")
    card_id = datetime.now().strftime("%Y%m%d%H%M%S")

    # שמירת תמונה
    ensure_dirs(card_dir(data["shop"]))
    img_path = os.path.join(card_dir(data["shop"]), f"{card_id}.jpg")
    file = await ctx.bot.get_file(data["file_id"])
    await file.download_to_drive(img_path)

    # שמירת מטה
    meta = {
        "title":       data["title"],
        "description": data["desc"],
        "price":       data["price"],
        "owner_id":    uid,
        "created_at":  datetime.now().isoformat()
    }
    with open(os.path.join(card_dir(data["shop"]), f"{card_id}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    await update.message.reply_text(f"✅ קלף נוצר!\n/purchase {data['shop']} {card_id}")
    return ConversationHandler.END

# Purchase flow
async def purchase_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) != 2:
        return await update.message.reply_text("❗ /purchase <shop> <card_id>")
    shop, card_id = args
    meta_path = os.path.join(card_dir(shop), f"{card_id}.json")
    if not os.path.isfile(meta_path):
        return await update.message.reply_text("❌ לא נמצא קלף.")
    meta = json.load(open(meta_path, "r", encoding="utf-8"))

    await update.message.reply_photo(
        photo=open(os.path.join(card_dir(shop), f"{card_id}.jpg"), "rb"),
        caption=(
            f"🎴 {meta['title']}\n"
            f"{meta['description']}\n"
            f"💰 {meta['price']}₪\n"
            "שלח צילום מסך של התשלום."
        )
    )
    ctx.user_data["shop"] = shop
    ctx.user_data["card_id"] = card_id
    return PURCHASE_WAIT

async def purchase_screenshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    shop = ctx.user_data["shop"]
    card_id = ctx.user_data["card_id"]
    purchase_id = f"{card_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ensure_dirs(purchases_dir(shop, card_id))
    img_path = os.path.join(purchases_dir(shop, card_id), f"{purchase_id}.jpg")
    file = await ctx.bot.get_file(update.message.photo[-1].file_id)
    await file.download_to_drive(img_path)
    await update.message.reply_text(f"✅ תודה! ID רכישה: {purchase_id}")
    return ConversationHandler.END

def register_handlers(app):
    upload_conv = ConversationHandler(
        entry_points=[CommandHandler("upload_card", upload_start)],
        states={
            UPLOAD_IMAGE: [MessageHandler(filters.PHOTO, upload_image)],
            SET_SHOP:     [MessageHandler(filters.TEXT & ~filters.COMMAND, set_shop)],
            SET_TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, set_title)],
            SET_DESC:     [MessageHandler(filters.TEXT & ~filters.COMMAND, set_desc)],
            SET_PRICE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, set_price)],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: c.bot.send_message(u.effective_chat.id, "מבוטל."))],
    )
    purchase_conv = Conversation
