import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Channel username ya ID (@ wala)
CHANNEL_ID = "@movies"

# Render ke Environment Variables se token read karega
BOT_TOKEN = os.environ["8325358044:AAFSfSpaW2gZBZGS3MHpwtT3XkVPjekYHFA"]

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Namaste! Main KTMovies bot hoon. Movie ka naam bhejo 🙂")

# Normal message reply
async def reply_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # User ko reply
    await update.message.reply_text(f"Aapne likha: {user_text}")
    
    # Channel me bhi post
    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=f"📢 User ne likha: {user_text}"
    )

# Main
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_user))

    app.run_polling()

if __name__ == "__main__":
    main()
