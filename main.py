import os
import json
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

import bot_manager   # מניח ש־bot_manager.py נמצא באותה תיקיה

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Load env & constants
# ─────────────────────────────────────────────────────────────
load_dotenv()
TOKEN    = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
REG_ROOT = "registrations"

if not TOKEN or not ADMIN_ID:
    logger.error("Missing TELEGRAM_TOKEN or TELEGRAM_ADMIN_ID")
    exit(1)

# ─────────────────────────────────────────────────────────────
# Conversation states (פשוטה: רק תמונה 1)
# ─────────────────────────────────────────────────────────────
CONTACT, BOT_TOKEN, IMG1, TITLE1, PRICE1 = range(5)

# ─────────────────────────────────────────────────────────────
# In-memory sessions
# ─────────────────────────────────────────────────────────────
sessions: dict[int, dict] = {}

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def ensure_dirs(path: str):
    os.makedirs(path, exist_ok=True)

def user_dir(uid: int, bot_token: str) -> str:
    return os.path.join(REG_ROOT, str(uid), bot_token)

# ─────────────────────────────────────────────────────────────
# Handler: /start
# ─────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("שתף אנשי קשר", request_contact=True)]]
    await update.message.reply_text(
        "ברוכים הבאים! כדי להרשם – שתפו את פרטי הקשר שלכם:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True),
    )
    return CONTACT

# ─────────────────────────────────────────────────────────────
# Handler: קליטת איש קשר
# ─────────────────────────────────────────────────────────────
async def contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    contact = (
        update.message.contact.phone_number
        if update.message.contact
        else update.message.text
    )
    sessions[uid] = {"contact": contact}
    await update.message.reply_text(
        "הדבק כאן את טוקן ה-Shop Bot שקיבלת:",
        reply_markup=ReplyKeyboardRemove()
    )
    return BOT_TOKEN

# ─────────────────────────────────────────────────────────────
# Handler: קליטת טוקן
# ─────────────────────────────────────────────────────────────
async def bot_token(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sessions[uid]["bot_token"] = token := update.message.text.strip()
    await update.message.reply_text("העלה תמונה אחת של החנות שלך:")
    return IMG1

# ─────────────────────────────────────────────────────────────
# Handler: קליטת תמונה #1
# ─────────────────────────────────────────────────────────────
async def img1(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sessions[uid]["file_id"] = update.message.photo[-1].file_id
    await update.message.reply_text("הכנס כותרת לתמונה:")
    return TITLE1

# ─────────────────────────────────────────────────────────────
# Handler: קליטת כותרת #1
# ─────────────────────────────────────────────────────────────
async def title1(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sessions[uid]["title"] = update.message.text.strip()
    await update.message.reply_text("הכנס מחיר (₪) לתמונה:")
    return PRICE1

# ─────────────────────────────────────────────────────────────
# Handler: קליטת מחיר #1 וסיום
# ─────────────────────────────────────────────────────────────
async def price1(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    try:
        price = float(text)
    except ValueError:
        return await update.message.reply_text("❗ מחיר לא חוקי, נסה שוב:")

    data = sessions.pop(uid)
    bot_token = data["bot_token"]
    folder = user_dir(uid, bot_token)
    ensure_dirs(os.path.join(folder, "images"))

    # הורדת התמונה
    file = await ctx.bot.get_file(data["file_id"])
    img_path = os.path.join(folder, "images", "1.jpg")
    await file.download_to_drive(img_path)

    # שמירת מטא
    meta = {
        "contact": data["contact"],
        "title":   data["title"],
        "price":   price,
        "ts":      datetime.now().isoformat()
    }
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)

    # התראה למנהל
    await ctx.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"✅ הרשמה חדשה!\n"
            f"• משתמש: {uid}\n"
            f"• טוקן בוט: `{bot_token}`\n"
            f"• פרטי קשר: {data['contact']}"
        ),
        parse_mode="Markdown"
    )

    # ─────────────────────────────────────────────────────────
    # השקת ה-Shop Bot באופן דינמי
    # ─────────────────────────────────────────────────────────
    asyncio.create_task(bot_manager.launch_bot(bot_token))

    # תגובה למשתמש שסיים
    await update.message.reply_text("🎉 הרשמת בהצלחה! בוט החנות שלך עולה כעת.")
    return ConversationHandler.END

# ─────────────────────────────────────────────────────────────
# ConversationHandler Registration
# ─────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONTACT:   [MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, contact)],
            BOT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_token)],
            IMG1:      [MessageHandler(filters.PHOTO, img1)],
            TITLE1:    [MessageHandler(filters.TEXT & ~filters.COMMAND, title1)],
            PRICE1:    [MessageHandler(filters.TEXT & ~filters.COMMAND, price1)],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: c.bot.send_message(u.effective_chat.id, "מבוטל."))],
    )

    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
