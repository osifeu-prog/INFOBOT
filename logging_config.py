import os
import logging

# קבלו את הטוקן מה־env
TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# 1. הפכו את ה־root logger לפורמט עם שם המודול
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)

# 2. השביתו לוגינג HTTP של ה־telegram-wrapper
for lg in ("telegram._request", "telegram.ext.updater", "telegram.bot"):
    logging.getLogger(lg).setLevel(logging.WARNING)

# 3. הוסיפו Filter שמחליף כל מקום שבו מופיע הטוקן במחרוזת "<REDACTED>"
class RedactTokenFilter(logging.Filter):
    def __init__(self, secret: str):
        super().__init__()
        self.secret = secret

    def filter(self, record: logging.LogRecord) -> bool:
        if self.secret and hasattr(record, "msg"):
            record.msg = record.getMessage().replace(self.secret, "<REDACTED>")
        return True

# הוסיפו את הפילטר ל־root logger
root_logger = logging.getLogger()
root_logger.addFilter(RedactTokenFilter(TOKEN))

# -- עכשיו אפשר להמשיך בטעינת שאר הקוד שלכם --
