import os
import json
import asyncio
import aiohttp

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_URL = os.environ["API_URL"]

# NOTE: This in-memory set resets when the Render service restarts.
used_users = set()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Num information ke liye /lookup use karein.\n"
        "Har user ko sirf 1 successful lookup milega."
    )


async def lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in used_users:
        await update.message.reply_text(
            "❌ Aap apna 1 allowed lookup already use kar chuke hain. agle din aaye "
        )
        return

    context.user_data["waiting_for_input"] = True
    await update.message.reply_text(
        "🔎 Send me num"
    )


async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.user_data.get("waiting_for_input"):
        return

    if user_id in used_users:
        await update.message.reply_text(
            "❌ Aapka allowed lookup already use ho chuka hai."
        )
        context.user_data["waiting_for_input"] = False
        return

    value = update.message.text.strip()

    if not value:
        await update.message.reply_text("❌ Valid input bhejiye.")
        return

    context.user_data["waiting_for_input"] = False

    try:
        # API_URL should end with the parameter prefix, e.g.
        # https://example.com/api/demo?value=
        url = f"{API_URL}{value}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                if response.status != 200:
                    await update.message.reply_text(
                        f"❌ API error: HTTP {response.status}"
                    )
                    return

                result = await response.json(content_type=None)

        if result.get("status") == "success":
            used_users.add(user_id)

        formatted = json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )

        # Escape Telegram MarkdownV2 special characters
        escaped = (
            formatted.replace("\\", "\\\\")
            .replace("`", "\\`")
        )

        message = await update.message.reply_text(
            f"```json\n{escaped}\n```",
            parse_mode="MarkdownV2"
        )

        await asyncio.sleep(10)

        try:
            await message.delete()
        except Exception:
            pass

    except asyncio.TimeoutError:
        await update.message.reply_text("❌ API request timeout.")
    except Exception as e:
        print("ERROR:", repr(e))
        await update.message.reply_text("❌ Data fetch nahi ho saka.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lookup", lookup))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input)
    )

    print("🤖 Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
