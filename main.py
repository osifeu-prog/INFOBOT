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

import bot_manager  # מייבא את מנהל ה-Shop Bots

# ─────────────────────────────────────────────────────────────
# Logging to stdout for server debugging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Load ENV (לוקל) ובדיקת SERVICE vars ב-Docker
# ─────────────────────────────────────────────────────────────
load_dotenv()  # השאירו לשימוש מקומי בלבד; ב-Docker נעשו הגדרות ב-Service Variables
TOKEN    = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
REG_ROOT = "registrations"

if not TOKEN or not ADMIN_ID:
    logger.error("Missing TELEGRAM_TOKEN or TELEGRAM_ADMIN_ID")
    exit(1)

# ─────────────────────────────────────────────────────────────
# Conversation states
# ─────────────────────────────────────────────────────────────
CONTACT, BOT_TOKEN, IMG1, TITLE1, PRICE1, IMG2, TITLE2, PRICE2, IMG3, TITLE3, PRICE3 = range(11)

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
# /start → בקשת שיתוף אנשי קשר
# ─────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("שתף אנשי קשר", request_contact=True)]]
    await update.message.reply_text(
        "ברוכים הבאים! כדי להרשם – שתפו את פרטי הקשר שלכם:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True),
    )
    # השקה של כל ה-Shop Bots הקיימים ברקע
    asyncio.create_task(bot_manager.main())
    return CONTACT

# ─────────────────────────────────────────────────────────────
# קליטת אנשי קשר
# ─────────────────────────────────────────────────────────────
async def contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    contact = update.message.contact.phone_number if update.message.contact else update.message.text
    sessions[uid] = {
        "contact": contact,
        "file_ids": [],
        "titles": [],
        "prices": [],
    }
    await update.message.reply_text("העלה טוקן בוט (Shop Bot) שקיבלת:", reply_markup=ReplyKeyboardRemove())
    return BOT_TOKEN

# ─────────────────────────────────────────────────────────────
# קליטת טוקן בוט
# ─────────────────────────────────────────────────────────────
async def bot_token(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sessions[uid]["bot_token"] = update.message.text.strip()
    await update.message.reply_text("העלה תמונה #1 של החנות שלך:")
    return IMG1

# ─────────────────────────────────────────────────────────────
# עיבוד 3 תמונות: תמונה→כותרת→מחיר
# ─────────────────────────────────────────────────────────────
def make_img_handler(idx, next_state):
    async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        file_id = update.message.photo[-1].file_id
        sessions[uid]["file_ids"].append(file_id)
        await update.message.reply_text(f"הכנס כותרת לתמונה #{idx}:")
        return next_state
    return handler

def make_title_handler(idx, next_state):
    async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        sessions[uid]["titles"].append(update.message.text.strip())
        await update.message.reply_text(f"הכנס מחיר (₪) לתמונה #{idx}:")
        return next_state
    return handler

def make_price_handler(idx):
    async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        try:
            price = float(update.message.text.strip())
        except ValueError:
            return await update.message.reply_text("❗ מחיר לא חוקי, נסה שוב:")
        sessions[uid]["prices"].append(price)

        # אם idx < 3 עוברים תמונה הבאה, אחרת מסיימים
        if idx < 3:
            await update.message.reply_text(f"העלה תמונה #{idx+1}:")
            return [IMG2, IMG3][idx-1]

        # סיום רישום וכתיבה לדיסק
        data = sessions.pop(uid)
        bot_token = data["bot_token"]
        folder = user_dir(uid, bot_token)
        ensure_dirs(os.path.join(folder, "images"))

        # הורדת תמונות
        for i, file_id in enumerate(data["file_ids"], start=1):
            file = await ctx.bot.get_file(file_id)
            await file.download_to_drive(os.path.join(folder, "images", f"{i}.jpg"))

        # שמירת metadata
        meta = {
            "contact":   data["contact"],
            "titles":    data["titles"],
            "prices":    data["prices"],
            "timestamp": datetime.now().isoformat(),
        }
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # Notify למנהל
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
        await update.message.reply_text("🎉 הרשמת בהצלחה! הבוט שלך ייווצר ויתחיל לפעול.")
        return ConversationHandler.END
    return handler

# ─────────────────────────────────────────────────────────────
# Registration ConversationHandler
# ─────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONTACT:   [MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, contact)],
            BOT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_token)],
            IMG1:      [MessageHandler(filters.PHOTO, make_img_handler(1, TITLE1))],
            TITLE1:    [MessageHandler(filters.TEXT & ~filters.COMMAND, make_title_handler(1, PRICE1))],
            PRICE1:    [MessageHandler(filters.TEXT & ~filters.COMMAND, make_price_handler(1))],
            IMG2:      [MessageHandler(filters.PHOTO, make_img_handler(2, TITLE2))],
            TITLE2:    [MessageHandler(filters.TEXT & ~filters.COMMAND, make_title_handler(2, PRICE2))],
            PRICE2:    [MessageHandler(filters.TEXT & ~filters.COMMAND, make_price_handler(2))],
            IMG3:      [MessageHandler(filters.PHOTO, make_img_handler(3, TITLE3))],
            TITLE3:    [MessageHandler(filters.TEXT & ~filters.COMMAND, make_title_handler(3, PRICE3))],
            PRICE3:    [MessageHandler(filters.TEXT & ~filters.COMMAND, make_price_handler(3))],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: c.bot.send_message(u.effective_chat.id, "מבוטל."))],
    )

    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
