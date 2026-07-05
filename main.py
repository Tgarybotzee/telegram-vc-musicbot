import warnings
from telegram.warnings import PTBUserWarning

warnings.filterwarnings("ignore", category=PTBUserWarning)

from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from config import BOT_TOKEN, logger
from database import init_db
from handlers import (
    start_command, handle_callbacks, auth_conv_handler, 
    fetch_otp_conv_handler, download_session_conv_handler
)

async def setup(application: Application):
    logger.info("Initializing database...")
    await init_db()

def main():
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(setup)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(auth_conv_handler)
    application.add_handler(fetch_otp_conv_handler)
    application.add_handler(download_session_conv_handler)  # New handler added here
    application.add_handler(CallbackQueryHandler(handle_callbacks))

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()