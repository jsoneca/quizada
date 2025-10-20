import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import logging

# ===============================
# 🔧 CONFIGURAÇÕES GERAIS
# ===============================
TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))  # 🔒 substitua pelo seu ID real
WEBHOOK_URL = f"https://quizada.onrender.com/webhook/{TOKEN}"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ===============================
# 🧠 HANDLERS DO BOT
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Eu sou o Quizada Bot.\nUse /quiz para jogar!"
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧩 Em breve: quizzes incríveis!")

async def add_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Somente o administrador pode adicionar quizzes"""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("🚫 Apenas o administrador pode adicionar quizzes.")
        return
    await update.message.reply_text("✅ Modo administrador: adicione seu quiz!")

# ===============================
# 🔁 CRIAÇÃO DO APLICATIVO TELEGRAM
# ===============================
async def create_app():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(CommandHandler("addquiz", add_quiz))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, quiz))

    # Remove webhook antigo e configura o novo
    await application.bot.delete_webhook()
    await application.bot.set_webhook(url=WEBHOOK_URL)

    logging.info(f"✅ Webhook configurado: {WEBHOOK_URL}")
    return application

# ===============================
# 🌐 FLASK (Render mantém vivo)
# ===============================
@app.route("/", methods=["GET"])
def home():
    return "🤖 Quizada Bot está ativo!"

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return "ok"

# ===============================
# 🚀 INICIALIZAÇÃO PRINCIPAL
# ===============================
async def main():
    global bot_app
    bot_app = await create_app()
    logging.info("🚀 Bot iniciado e aguardando atualizações via webhook.")

if __name__ == "__main__":
    asyncio.run(main())  # ✅ Correção do warning + execução segura
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
