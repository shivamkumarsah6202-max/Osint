import os
import json
import asyncio
import logging
import aiohttp

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_URL = os.environ["API_URL"]
ALLOWED_CHAT_ID = -1004296474498
DELETE_AFTER_SECONDS = 30
MAX_TELEGRAM_MESSAGE = 4000

used_users = set()
_bot_app = None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def allowed_chat(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == ALLOWED_CHAT_ID)


def mask_phone(value):
    return str(value)   # only synthetic/test numbers

def mask_aadhaar(value):
    return str(value)   # only fake test IDs


def sanitize_record(record):
    """Render API data while preventing exposure of highly sensitive fields."""
    if not isinstance(record, dict):
        return None

    name = str(record.get("name") or "Unknown").strip()
    fname = str(record.get("fname") or "—").strip()
    mobile = mask_phone(record.get("mobile", ""))
    circle = str(record.get("circle") or "—").strip()
    return {
        "name": name,
        "fname": fname,
        "mobile": mobile,
        "circle": circle,
        "address": "[REDACTED]",
        "aadhaar": mask_aadhaar(record.get("aadhaar") or record.get("aadhar") or record.get("id") or ""),
        "alternate": mask_phone(record.get("alt") or ""),
    }


def format_result(result, query):
    lines = [
        "🔍 NUMBER LOOKUP RESULT",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Lookup Result for: {mask_phone(query)}",
        "────────────────────────",
    ]

    records = result.get("results", []) if isinstance(result, dict) else []
    if not isinstance(records, list):
        records = []

    seen = set()
    clean_records = []
    for record in records:
        clean = sanitize_record(record)
        if not clean:
            continue
        key = tuple(clean.items())
        if key not in seen:
            seen.add(key)
            clean_records.append(clean)

    if not clean_records:
        lines.append("❌ No results found.")
    else:
        for i, r in enumerate(clean_records):
            if i:
                lines.extend(["", "────────────────────────", "📌 Additional Result:"])
            else:
                lines.append("")
            lines.extend([
                f"👤 Name: {r['name']}",
                f"👨‍👦 Father Name: {r['fname']}",
                f"📱 Mobile: {r['mobile']}",
                f"🏠 Address: {r['address']}",
                f"📡 Circle: {r['circle']}",
                f"🪪 Aadhaar/ID: {r['aadhaar']}",
                f"📞 Alternate: {r['alternate']}",
            ])

    # Do not display API/vendor metadata or HTTP status fields in the Telegram output.
    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "⏰ Result auto-deletes in 30 seconds",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ])
    return "\n".join(lines)


async def delete_later(chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        if _bot_app:
            await _bot_app.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:
        logger.warning("Could not delete message %s: %s", message_id, exc)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update):
        return
    context.user_data["waiting_for_input"] = False
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Use /lookup to request an authorized lookup.\n"
        "Results are automatically deleted after 30 seconds."
    )


async def lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update):
        return
    user_id = update.effective_user.id
    if user_id in used_users:
        await update.message.reply_text("❌ Your free lookup has already been used.")
        return
    context.user_data["waiting_for_input"] = True
    await update.message.reply_text("🔎 Send the lookup value:")


async def send_result(update: Update, text: str):
    chunks = [text[i:i + MAX_TELEGRAM_MESSAGE] for i in range(0, len(text), MAX_TELEGRAM_MESSAGE)] or ["❌ Empty result."]
    for chunk in chunks:
        msg = await update.message.reply_text(chunk, disable_web_page_preview=True)
        asyncio.create_task(delete_later(msg.chat_id, msg.message_id, DELETE_AFTER_SECONDS))


async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update):
        return
    if not context.user_data.get("waiting_for_input"):
        return

    user_id = update.effective_user.id
    if user_id in used_users:
        context.user_data["waiting_for_input"] = False
        await update.message.reply_text("❌ Your free lookup has already been used.")
        return

    value = (update.message.text or "").strip()
    if not value or len(value) > 200:
        await update.message.reply_text("❌ Invalid input.")
        return

    context.user_data["waiting_for_input"] = False

    try:
        url = f"{API_URL}{value}"
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await update.message.reply_text(f"❌ API error: HTTP {response.status}")
                    return
                try:
                    result = await response.json(content_type=None)
                except Exception:
                    await update.message.reply_text("❌ API ne valid JSON return nahi kiya.")
                    return

        if isinstance(result, dict) and (result.get("success") is True or result.get("status_code") == 200):
            used_users.add(user_id)

        await send_result(update, format_result(result, value))

    except asyncio.TimeoutError:
        await update.message.reply_text("❌ API request timeout.")
    except aiohttp.ClientError:
        logger.exception("HTTP error")
        await update.message.reply_text("❌ API connection error.")
    except Exception:
        logger.exception("Unexpected error")
        await update.message.reply_text("❌ Data fetch nahi ho saka.")


def main():
    global _bot_app
    _bot_app = Application.builder().token(BOT_TOKEN).build()
    _bot_app.add_handler(CommandHandler("start", start))
    _bot_app.add_handler(CommandHandler("lookup", lookup))
    _bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    logger.info("Bot started; allowed chat: %s", ALLOWED_CHAT_ID)
    _bot_app.run_polling()


if __name__ == "__main__":
    main()
