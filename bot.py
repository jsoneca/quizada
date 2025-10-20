import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
from apscheduler.schedulers.background import BackgroundScheduler

# 🔧 Configurações principais
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "https://quizada.onrender.com") + f"/webhook/{TOKEN}"

# ⚙️ Flask app
app = Flask(__name__)

# ⚙️ Inicialização do bot (Application)
application = Application.builder().token(TOKEN).build()

# ------------------------------------------------------
# 🧠 Handlers principais (comandos e mensagens)
# ------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 Bem-vindo ao Quizada! Prepare-se para o próximo quiz!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💡 Comandos disponíveis:\n/start - Iniciar o bot\n/help - Mostrar ajuda")

# Adiciona comandos
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))

# ------------------------------------------------------
# 🔄 Sistema de Quiz Automático (exemplo de tarefa APScheduler)
# ------------------------------------------------------

def enviar_quiz_automatico():
    asyncio.run(enviar_mensagem_para_todos("🧩 Um novo quiz começou! Responda rápido!"))

async def enviar_mensagem_para_todos(texto):
    try:
        # Aqui você pode iterar sobre uma lista de chat_ids se quiser enviar a múltiplos usuários
        # Exemplo: await application.bot.send_message(chat_id=chat_id, text=texto)
        print(f"[INFO] Mensagem automática enviada: {texto}")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar mensagem automática: {e}")

# Agenda o quiz automático
scheduler = BackgroundScheduler()
scheduler.add_job(enviar_quiz_automatico, "interval", minutes=45)
scheduler.start()

# ------------------------------------------------------
# 🌐 Webhook Flask route
# ------------------------------------------------------

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
async def webhook():
    """Recebe updates do Telegram via webhook"""
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.update_queue.put(update)
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot Quizada ativo no Render com webhook!"

# ------------------------------------------------------
# 🚀 Setup do webhook e inicialização
# ------------------------------------------------------

async def main():
    # Remove webhooks anteriores (importante para evitar conflitos)
    await application.bot.delete_webhook(drop_pending_updates=True)

    # Define o novo webhook
    await application.bot.set_webhook(url=WEBHOOK_URL)
    print(f"[OK] Webhook configurado em: {WEBHOOK_URL}")

    # Inicia o processamento assíncrono das filas de updates
    await application.start()
    await application.updater.start_polling()  # opcionalmente pode ser omitido, pois Flask cuida

if __name__ == "__main__":
    # Configura o loop de evento
    loop = asyncio.get_event_loop()
    loop.create_task(main())

    # Roda o Flask (Render usa porta definida automaticamente)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
