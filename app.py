import os

from adapters.telegram_bot import TelegramShopBot
from db import Database
from services.catalog import CatalogService


def main() -> None:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    admin_id_raw = os.getenv("ADMIN_ID", "").strip()
    db_path = os.getenv("DB_PATH", "shop.db").strip()

    if not token:
        raise RuntimeError("TELEGRAM_TOKEN not found in Railway Variables")
    if not admin_id_raw or not admin_id_raw.isdigit():
        raise RuntimeError("ADMIN_ID not found or invalid")

    db = Database(db_path)
    db.init()
    catalog = CatalogService(db)

    bot = TelegramShopBot(
        token=token,
        admin_id=int(admin_id_raw),
        catalog=catalog
    )

    app = bot.build_app()
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()