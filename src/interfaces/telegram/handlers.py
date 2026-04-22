from telegram import Update
from telegram.ext import ContextTypes

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm your assistant.") # type:ignore

async def help_me(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ki help kormu re bhai") # type:ignore

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    # 👇 call your agent here later
    reply = f"tui bolli: {user_text}"
    await update.message.reply_text(reply) #type: ignore
