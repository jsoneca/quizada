import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# ==========================
# CONFIGURAÇÕES INICIAIS
# ==========================
TOKEN = os.getenv("BOT_TOKEN") or "COLOQUE_SEU_TOKEN_AQUI"
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))  # seu ID de admin do bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================
# FLASK
# ==========================
app = Flask(__name__)

# ==========================
# COMANDOS DO BOT
# ==========================

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Eu sou o Quizada Bot.\n"
        "Use /entrar para participar do ranking.\n"
        "Os quizzes rodam automaticamente a cada 45 minutos!"
    )

async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"✅ {user.first_name}, você foi adicionado à lista de pontuação!")

async def add_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("🚫 Apenas administradores podem adicionar novos quizzes.")
        return

    quiz_text = " ".join(context.args)
    if not quiz_text:
        await update.message.reply_text("❗ Use: /addquiz <pergunta|resposta>")
        return

    await update.message.reply_text(f"🧠 Novo quiz adicionado:\n{quiz_text}")

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎁 Você recebeu seu bônus semanal!")

# ==========================
# SISTEMAS AUTOMÁTICOS
# ==========================

async def enviar_quiz_automatico(application: Application):
    logger.info("⏰ Enviando quiz automático para todos os usuários cadastrados...")
    # Aqui você pode ler do banco os usuários e enviar a pergunta
    # Exemplo simples:
    await application.bot.send_message(chat_id=OWNER_ID, text="🧩 Quiz automático enviado!")

def configurar_scheduler(app_telegram: Application):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        enviar_quiz_automatico,
        "interval",
        minutes=45,
        args=[app_telegram]
    )
    scheduler.start()

# ==========================
# CONFIGURAÇÃO DO TELEGRAM
# ==========================

async def create_app():
    app_telegram = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app_telegram.add_handler(CommandHandler("iniciar", iniciar))
    app_telegram.add_handler(CommandHandler("entrar", entrar))
    app_telegram.add_handler(CommandHandler("addquiz", add_quiz))
    app_telegram.add_handler(CommandHandler("bonus", bonus))

    configurar_scheduler(app_telegram)

    return app_telegram

# ==========================
# WEBHOOK DO FLASK
# ==========================

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
async def webhook():
    """Recebe atualizações do Telegram via Webhook"""
    data = request.get_json(force=True)
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return "ok", 200


@app.route("/", methods=["GET"])
def home():
    return "🤖 Quizada Bot está ativo!", 200


# ==========================
# EXECUÇÃO PRINCIPAL
# ==========================
async def main():
    global bot_app
    bot_app = await create_app()

    # Configurar o webhook para o Render
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TOKEN}"
    await bot_app.bot.set_webhook(webhook_url)

    logger.info(f"✅ Webhook configurado com sucesso em: {webhook_url}")

if __name__ == "__main__":
    asyncio.run(main())
    app.run(host="0.0.0.0", port=10000)
