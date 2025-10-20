import asyncio
import json
import os
import random
import threading
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
)

TOKEN = os.getenv("BOT_TOKEN")

QUIZZES_FILE = "quizzes.json"
PONTUACOES_FILE = "pontuacoes.json"

# --- Utilidades ---
def carregar_dados(arquivo, padrao):
    if not os.path.exists(arquivo):
        with open(arquivo, "w") as f:
            json.dump(padrao, f)
    with open(arquivo, "r") as f:
        return json.load(f)

def salvar_dados(arquivo, dados):
    with open(arquivo, "w") as f:
        json.dump(dados, f, indent=4)

# --- Comandos ---
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Eu sou o Quizada!\n\n"
        "Use /entrar para participar dos quizzes e competir com outros jogadores 🎮"
    )

async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    pontuacoes = carregar_dados(PONTUACOES_FILE, {})

    if chat_id not in pontuacoes:
        pontuacoes[chat_id] = {"usuarios": {}, "nome_grupo": update.effective_chat.title}

    if str(user.id) not in pontuacoes[chat_id]["usuarios"]:
        pontuacoes[chat_id]["usuarios"][str(user.id)] = {"nome": user.first_name, "pontos": 0}
        salvar_dados(PONTUACOES_FILE, pontuacoes)
        await update.message.reply_text(f"✅ {user.first_name}, você entrou no ranking deste grupo!")
    else:
        await update.message.reply_text("⚠️ Você já está participando!")

# --- Envio de quizzes automáticos ---
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    pontuacoes = carregar_dados(PONTUACOES_FILE, {})
    quizzes = carregar_dados(QUIZZES_FILE, [])

    if not quizzes or not pontuacoes:
        return

    quiz = random.choice(quizzes)
    pergunta = quiz["pergunta"]
    opcoes = quiz["opcoes"]
    correta = quiz["correta"]

    for chat_id in pontuacoes.keys():
        try:
            await context.bot.send_poll(
                chat_id=int(chat_id),
                question=f"🧩 Quiz:\n\n{pergunta}",
                options=opcoes,
                type="quiz",
                correct_option_id=correta,
                is_anonymous=False
            )
        except Exception as e:
            print(f"Erro ao enviar quiz para {chat_id}: {e}")

# --- Reset de temporada ---
async def resetar_temporada(context: ContextTypes.DEFAULT_TYPE):
    pontuacoes = carregar_dados(PONTUACOES_FILE, {})
    for chat_id in pontuacoes.keys():
        try:
            await context.bot.send_message(chat_id=int(chat_id), text="🌸 Nova temporada iniciada! Pontuações zeradas!")
        except Exception:
            pass
    salvar_dados(PONTUACOES_FILE, {})

# --- Setup principal ---
async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("iniciar", iniciar))
    application.add_handler(CommandHandler("entrar", entrar))

    job_queue: JobQueue = application.job_queue

    # Envia quizzes a cada 45 minutos
    job_queue.run_repeating(enviar_quiz, interval=45*60, first=10)

    # Reseta a cada 3 meses
    datas_reset = ["2025-03-01", "2025-06-01", "2025-09-01", "2025-12-01"]
    for data in datas_reset:
        dt = datetime.strptime(data, "%Y-%m-%d")
        job_queue.run_once(resetar_temporada, when=dt)

    print("🤖 Bot rodando com sucesso (Python 3.13 + PTB 21.4)")
    await application.run_polling()

# --- Flask (para manter serviço vivo no Render) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Quizada rodando no Render (Python 3.13)"

def iniciar_bot():
    asyncio.run(main())

if __name__ == "__main__":
    t = threading.Thread(target=iniciar_bot)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
