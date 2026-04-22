from telegram.ext import Application, CommandHandler, MessageHandler, filters
from .handlers import start, help_me, handle_message
from config.settings import settings


def run():
    TELEGRAM_TOKEN = settings.TELEGRAM_TOKEN
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help_me", help_me))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    run()
