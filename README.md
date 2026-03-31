# Universal Telegram Shop Bot Template

This template is a beginner-friendly Telegram shop bot with:
- buttons-only flow after the first `/start`
- dynamic categories and products
- admin menu for non-technical users
- product photos via Telegram `file_id`
- cart, checkout, order notifications
- modular architecture for future messenger adapters

## Project structure
- `app.py` — entry point
- `db.py` — SQLite layer
- `services/catalog.py` — business logic
- `adapters/telegram_bot.py` — Telegram transport/UI layer
- `requirements.txt` — Python dependency list
- `.env.example` — environment variables example
- `.gitignore` — local files and secrets excluded from git
- `shop_dev.db` — local SQLite dev database file created/used by the bot

## Quick start
1. Create a Telegram bot in BotFather and get the token.
2. Get your numeric Telegram ID.
3. Copy `.env.example` to `.env` and fill in the values.
4. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```
5. Run:
   ```bash
   python3 app.py
   ```

## Environment variables
- `TELEGRAM_TOKEN` — Telegram bot token from BotFather
- `ADMIN_ID` — numeric Telegram user ID of the administrator
- `DB_PATH` — path to SQLite database file, defaults to `shop_dev.db`

## Important note
Telegram does not allow a bot to message a user before that user opens the chat and presses Start. So the first `/start` (or Start button in the Telegram UI) is still required once. After that, the bot works with buttons.
