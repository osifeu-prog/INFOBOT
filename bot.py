import os
import uuid
import logging
from datetime import datetime

from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from config import settings
from database import AsyncSessionLocal, init_db
from models import User, Shop, Card, Purchase, Score
from sqlalchemy.future import select

# ─────────────────────────────────────────────────────────────
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger("bot")

# ─────────────────────────────────────────────────────────────
# Conversation states
# ─────────────────────────────────────────────────────────────
(
    CREATE_NAME,
    CREATE_IMG,
    CREATE_TITLE,
    CREATE_PRICE,
    ADD_CARD,
) = range(5)

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
async def get_or_create_user(telegram_id: int, phone: str = None):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=telegram_id,
                phone=phone,
                is_admin=(telegram_id == settings.ADMIN_ID)
            )
            session.add(user)
            await session.commit()
        return user

# ─────────────────────────────────────────────────────────────
# /start → ברוך הבא
# ─────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user.id)
    kb = [[KeyboardButton("שתף אנשי קשר", request_contact=True)]]
    await update.message.reply_text(
        "ברוך/ה הבא/ה לפלטפורמת NFTII! אנא שתף/י אנשי קשר כדי להתחיל.",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True),
    )

# ─────────────────────────────────────────────────────────────
# קליטת אנשי קשר → להצגת /dashboard
# ─────────────────────────────────────────────────────────────
async def contact_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    contact = (update.message.contact.phone_number
               if update.message.contact
               else update.message.text)
    await get_or_create_user(update.effective_user.id, phone=contact)
    await update.message.reply_text(
        "✅ תודה! עכשיו שלח/י `/dashboard` כדי לראות אפשרויות."
    )

# ─────────────────────────────────────────────────────────────
# /dashboard → תפריט ראשי (Admin vs Customer)
# ─────────────────────────────────────────────────────────────
def dashboard_menu(user: User):
    if user.is_admin:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 כל החנויות", callback_data="admin_shops")],
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="admin_lb")],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ צור חנות מלאה", callback_data="cust_new_full")],
            [InlineKeyboardButton("➕ צור חנות קלף יחיד", callback_data="cust_new_single")],
            [InlineKeyboardButton("🛒 דפדף חנויות", callback_data="cust_browse")],
            [InlineKeyboardButton("🏬 החנויות שלי", callback_data="cust_myshops")],
            [InlineKeyboardButton("🔑 ה-NFT tokens שלי", callback_data="cust_tokens")],
        ])

async def dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = await get_or_create_user(uid)
    await update.message.reply_text(
        "בחר/י אפשרות מהתפריט:",
        reply_markup=dashboard_menu(user)
    )

# ─────────────────────────────────────────────────────────────
# CallbackQueryHandler → ניתוב לפי data
# ─────────────────────────────────────────────────────────────
async def callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    uid = query.from_user.id
    user = await get_or_create_user(uid)

    # Admin: רישום כל החנויות
    if data == "admin_shops" and user.is_admin:
        async with AsyncSessionLocal() as session:
            shops = (await session.execute(select(Shop))).scalars().all()
        text = "\n".join([f"{s.id}. {s.name} (בעלים: {s.owner_id})" for s in shops]) or "אין חנויות עדיין."
        return await query.edit_message_text(text)

    # Admin: Leaderboard
    if data == "admin_lb" and user.is_admin:
        async with AsyncSessionLocal() as session:
            purchases = (await session.execute(select(Purchase))).scalars().all()
            totals = {}
            for p in purchases:
                totals[p.user_id] = totals.get(p.user_id, 0) + p.amount
        sorted_lb = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        text = "\n".join([f"{uid}: ₪{amt}" for uid, amt in sorted_lb]) or "אין פעילות."
        return await query.edit_message_text(text)

    # Customer: יצירת חנות חדשה
    if data in ("cust_new_full", "cust_new_single"):
        ctx.user_data["full"] = (data == "cust_new_full")
        await query.edit_message_text("הכנס/י שם לחנות שלך:")
        return CREATE_NAME

    # Customer: דפדוף חנויות
    if data == "cust_browse":
        async with AsyncSessionLocal() as session:
            shops = (await session.execute(select(Shop))).scalars().all()
        kb = [[InlineKeyboardButton(s.name, callback_data=f"browse_{s.id}")] for s in shops]
        return await query.edit_message_text("בחר/י חנות לדפדף:", reply_markup=InlineKeyboardMarkup(kb))

    # Customer: החנויות שלי
    if data == "cust_myshops":
        async with AsyncSessionLocal() as session:
            rows = await session.execute(select(Shop).where(Shop.owner_id == user.id))
            myshops = rows.scalars().all()
        kb = [[InlineKeyboardButton(s.name, callback_data=f"myshop_{s.id}")] for s in myshops]
        return await query.edit_message_text("החנויות שלך:", reply_markup=InlineKeyboardMarkup(kb))

    # Customer: הצגת ה-NFT tokens
    if data == "cust_tokens":
        async with AsyncSessionLocal() as session:
            rows = await session.execute(select(Purchase).where(Purchase.user_id == user.id))
            ps = rows.scalars().all()
        lines = [f"{p.token} (₪{p.amount})" for p in ps]
        return await query.edit_message_text("\n".join(lines) or "אין לך tokens.")

    # דפדוף לקנייה
    if data.startswith("browse_"):
        shop_id = int(data.split("_")[1])
        async with AsyncSessionLocal() as session:
            cards = (await session.execute(select(Card).where(Card.shop_id == shop_id))).scalars().all()
        kb = [[InlineKeyboardButton(f"{c.title} — ₪{c.price}", callback_data=f"buy_{c.id}")] for c in cards]
        return await query.edit_message_text("בחר/י קלף לרכישה:", reply_markup=InlineKeyboardMarkup(kb))

    # בצע רכישה
    if data.startswith("buy_"):
        card_id = int(data.split("_")[1])
        token = str(uuid.uuid4())
        async with AsyncSessionLocal() as session:
            card = (await session.execute(select(Card).where(Card.id == card_id))).scalar_one()
            purchase = Purchase(
                user_id=user.id,
                card_id=card.id,
                token=token,
                amount=card.price,
                created_at=datetime.utcnow()
            )
            session.add(purchase)
            await session.commit()
        return await query.edit_message_text(f"✅ רכישה בוצעה!\nYour NFT-Token: `{token}`", parse_mode="Markdown")

    # הצגת קלפים בחנות הפרטית שלי
    if data.startswith("myshop_"):
        shop_id = int(data.split("_")[1])
        async with AsyncSessionLocal() as session:
            cards = (await session.execute(select(Card).where(Card.shop_id == shop_id))).scalars().all()
        kb = [
            [InlineKeyboardButton("➕ הוסף קלף", callback_data=f"addcard_{shop_id}")],
            *[[InlineKeyboardButton(f"{c.title}", callback_data=f"viewcard_{c.id}")] for c in cards]
        ]
        return await query.edit_message_text("נהל קלפים:", reply_markup=InlineKeyboardMarkup(kb))

    # מעבר לטיפול בוספת קלף
    if data.startswith("addcard_"):
        ctx.user_data["shop_id"] = int(data.split("_")[1])
        return await query.edit_message_text("העלה תמונה לקלף חדש:"), ADD_CARD

    return await query.edit_message_text("לא מזוהה.")

# ─────────────────────────────────────────────────────────────
# Conversation: ADD_CARD → צילום, כותרת, מחיר
# ─────────────────────────────────────────────────────────────
async def add_card_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["file_id"] = update.message.photo[-1].file_id
    await update.message.reply_text("הכנס/י כותרת לקלף:")
    return CREATE_TITLE

async def add_card_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["title"] = update.message.text.strip()
    await update.message.reply_text("הכנס/י מחיר (₪):")
    return CREATE_PRICE

async def add_card_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        price = float(text)
    except ValueError:
        return await update.message.reply_text("❗ מחיר לא חוקי, נסה שוב:")
    shop_id = ctx.user_data["shop_id"]

    # שמירת קלף DB
    async with AsyncSessionLocal() as session:
        # הורדת תמונה
        file = await ctx.bot.get_file(ctx.user_data["file_id"])
        folder = f"shops/{shop_id}"
        os.makedirs(folder, exist_ok=True)
        path = f"{folder}/{uuid.uuid4()}.jpg"
        await file.download_to_drive(path)

        card = Card(
            shop_id=shop_id,
            title=ctx.user_data["title"],
            image_path=path,
            price=price,
            created_at=datetime.utcnow()
        )
        session.add(card)
        await session.commit()

    await update.message.reply_text("✅ קלף נוסף בהצלחה!")
    return ConversationHandler.END

# ─────────────────────────────────────────────────────────────
# Registration & Polling
# ─────────────────────────────────────────────────────────────
def main():
    # init DB
    import asyncio
    asyncio.run(init_db())

    app = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CallbackQueryHandler(callback_router))

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u,c: None, pattern="addcard_.*")],
        states={
            ADD_CARD: [MessageHandler(filters.PHOTO, add_card_photo)],
            CREATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_card_title)],
            CREATE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_card_price)],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: c.bot.send_message(u.effective_chat.id, "מבוטל."))],
    )
    app.add_handler(conv)

    app.run_polling()

if __name__ == "__main__":
    main()
