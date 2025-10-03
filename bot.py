import uuid
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from config import settings
from database import AsyncSessionLocal, init_db
from models import User, Shop, Card, Purchase, Score
from sqlalchemy.future import select
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Helpers לדאטה ---
async def get_or_create_user(telegram_id: int, phone: str=None):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id==telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_id, phone=phone, is_admin=(telegram_id==settings.ADMIN_ID))
            session.add(user)
            await session.commit()
        return user

# --- Command Handlers ---
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    await update.message.reply_text("ברוך/ה הבא/ה! שלח /dashboard כדי לראות תפריט.")

async def dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = await get_or_create_user(uid)
    buttons = []
    if user.is_admin:
        buttons = [
            [InlineKeyboardButton("📊 דשבורד מנהל", callback_data="admin_dashboard")],
            [InlineKeyboardButton("➕ הרשמת צוות", callback_data="admin_invite")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton("🏬 קניות חנויות", callback_data="cust_browse")],
            [InlineKeyboardButton("🔖 החנויות שלי", callback_data="cust_myshops")],
            [InlineKeyboardButton("💼 הצטרף כצוות", callback_data="cust_join")],
        ]
    kb = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("בחר אופציה:", reply_markup=kb)

# … כאן תצרפו CallbackQueryHandler לטיפול במעבר בין המצבים,
# כולל רכישות, אישורי תשלום, יצירת NFT token (uuid.uuid4()), ניקוד, דירוג וכו’.

def main():
    app = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dashboard", dashboard))
    # … הוסיפו CallbackQueryHandler, MessageHandler ועוד
    # אתחול DB
    app.run_polling(allowed_updates=["message","callback_query"])

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())
    main()
