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

    # במקום לשלוח הודעה – נדפיס ל־logs את ה־username של ה־Shop Bot
    me = await app.bot.get_me()
    logger.info(f"✅ Shop Bot launched as @{me.username}")

    return app

async def main():
    if not os.path.isdir("registrations"):
        os.makedirs("registrations", exist_ok=True)

    tasks = []
    for user_id in os.listdir("registrations"):
        user_path = os.path.join("registrations", user_id)
        if not os.path.isdir(user_path):
            continue
        for bot_token in os.listdir(user_path):
            tasks.append(launch_bot(bot_token))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    else:
        logger.info("No registered shop bots found.")

    # משאירים את התוכנית רצה לעד
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
