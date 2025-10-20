import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)

# ============================================================
# 🔐 Configurações
# ============================================================
TOKEN = os.getenv("BOT_TOKEN")  # Defina no Render → Environment → BOT_TOKEN
OWNER_ID = 123456789  # coloque o ID do administrador

app = Flask(__name__)

# ============================================================
# 🤖 Comandos do Bot
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Olá! Sou o bot de quizzes e estou pronto!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Comandos disponíveis:\n"
        "/start - Inicia o bot\n"
        "/help - Mostra esta mensagem\n"
        "/addquiz - Adiciona um novo quiz (somente admin)"
    )

async def add_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("🚫 Você não tem permissão para adicionar quizzes.")
        return
    await update.message.reply_text("✏️ Envie a pergunta do novo quiz:")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Desculpe, não entendi esse comando.")

# ============================================================
# 🚀 Inicialização do Bot (Polling sem sinais)
# ============================================================
def iniciar_bot():
    async def main():
        print("🤖 Iniciando bot com polling (sem sinais)...")

        application = (
            ApplicationBuilder()
            .token(TOKEN)
            .build()
        )

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("addquiz", add_quiz))
        application.add_handler(MessageHandler(filters.COMMAND, unknown))

        # ✅ Corrigido: stop_signals=None evita erro de signal
        await application.run_polling(drop_pending_updates=True, stop_signals=None)

    asyncio.run(main())

# ============================================================
# 🌐 Flask (mantém o serviço ativo no Render)
# ============================================================
@app.route("/")
def home():
    return "✅ Bot de Quiz ativo e rodando!"

# ============================================================
# 🧵 Thread do Bot
# ============================================================
if __name__ == "__main__":
    bot_thread = threading.Thread(target=iniciar_bot, daemon=True)
    bot_thread.start()

    app.run(host="0.0.0.0", port=10000)
