import os
import asyncio
import logging
from telegram.ext import ApplicationBuilder
from shop_bot import register_handlers  # וודאו שקיים shop_bot.py עם register_handlers

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("bot_manager")

ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
REG_ROOT = "registrations"

async def launch_bot(token: str):
    logger.info(f"Launching Shop Bot for token: {token[:8]}…")
    app = ApplicationBuilder().token(token).build()
    register_handlers(app)
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    me = await app.bot.get_me()
    logger.info(f"✅ Shop Bot launched as @{me.username}")
    return app

async def main():
    if not os.path.isdir(REG_ROOT):
        os.makedirs(REG_ROOT, exist_ok=True)

    tasks = []
    for user_id in os.listdir(REG_ROOT):
        user_path = os.path.join(REG_ROOT, user_id)
        if not os.path.isdir(user_path):
            continue
        for bot_token in os.listdir(user_path):
            tasks.append(launch_bot(bot_token))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    else:
        logger.info("No registered shop bots found.")

    # משאירים את הלולאה פתוחה
    await asyncio.Event().wait()
