import os
import asyncio
import logging
from telegram.ext import ApplicationBuilder
from shop_bot import register_handlers

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("bot_manager")

ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))

async def launch_bot(token: str):
    logger.info(f"Launching Shop Bot for token: {token[:8]}…")
    app = ApplicationBuilder().token(token).build()
    register_handlers(app)
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    # דווח על ה-username של ה-Shop Bot לצ'אט של ה-Admin
    me = await app.bot.get_me()
    await app.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"✅ Shop Bot launched as @{me.username}\n"
            "שלחו לו בפרטי /menu כדי להתחיל."
        )
    )
    return app

async def main():
    # ודא שקיימת תיקיית registrations/
    if not os.path.isdir("registrations"):
        os.makedirs("registrations", exist_ok=True)

    tasks = []
    # מציאת כל הטוקנים ב-registrations/USER_ID/TOKEN
    for user_id in os.listdir("registrations"):
        path = os.path.join("registrations", user_id)
        if not os.path.isdir(path):
            continue
        for bot_token in os.listdir(path):
            tasks.append(launch_bot(bot_token))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    else:
        logger.info("No registered shop bots found.")

    # השאר את התוכנית רצה ללא הפסקה
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
