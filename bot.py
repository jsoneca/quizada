import os
import json
import random
import asyncio
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
)
from telegram.constants import ParseMode

# ======================================================
# 🔹 CONFIGURAÇÕES
# ======================================================
TOKEN = os.getenv("BOT_TOKEN")  # Token configurado no Render
PONTUACOES_FILE = "pontuacoes.json"
QUIZZES_FILE = "quizzes.json"

# Flask para manter o serviço ativo no Render
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "🤖 Bot de Quiz está rodando!"

# ======================================================
# 🔹 FUNÇÕES DE ARQUIVOS
# ======================================================
def carregar_pontuacoes():
    if os.path.exists(PONTUACOES_FILE):
        with open(PONTUACOES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_pontuacoes(pontuacoes):
    with open(PONTUACOES_FILE, "w", encoding="utf-8") as f:
        json.dump(pontuacoes, f, ensure_ascii=False, indent=2)

def carregar_quizzes():
    if os.path.exists(QUIZZES_FILE):
        with open(QUIZZES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ======================================================
# 🔹 QUIZ E PONTUAÇÃO
# ======================================================
pontuacoes = carregar_pontuacoes()
ultimo_quiz = {}

async def enviar_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ultimo_quiz
    quizzes = carregar_quizzes()
    if not quizzes:
        await update.message.reply_text("⚠️ Nenhum quiz disponível.")
        return

    # Deleta o quiz anterior (limpeza do chat)
    if update.effective_chat.id in ultimo_quiz:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=ultimo_quiz[update.effective_chat.id])
        except:
            pass

    quiz = random.choice(quizzes)
    opcoes = quiz["options"]
    resposta_certa = quiz["correct_option_id"]

    msg = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=f"🧩 {quiz['question']}",
        options=opcoes,
        type="quiz",
        correct_option_id=resposta_certa,
        is_anonymous=False,
        explanation=f"✅ Resposta correta: {opcoes[resposta_certa]}",
    )

    ultimo_quiz[update.effective_chat.id] = msg.message_id

# ======================================================
# 🔹 COMANDOS DE USUÁRIO
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Bem-vindo ao Quiz! Use /quiz para começar.")

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar_quiz(update, context)

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pontuacoes = carregar_pontuacoes()
    if not pontuacoes:
        await update.message.reply_text("📊 Ainda não há pontuações.")
        return

    ranking_texto = "🏆 *Ranking de Jogadores:*\n\n"
    for user, pontos in sorted(pontuacoes.items(), key=lambda x: x[1], reverse=True)[:10]:
        ranking_texto += f"• {user}: {pontos} pontos\n"

    await update.message.reply_text(ranking_texto, parse_mode=ParseMode.MARKDOWN)

# ======================================================
# 🔹 ESTAÇÕES E RESET DE TEMPORADA
# ======================================================
def obter_estacao():
    mes = datetime.now().month
    if mes in [12, 1, 2]:
        return "❄️ Inverno"
    elif mes in [3, 4, 5]:
        return "🌸 Primavera"
    elif mes in [6, 7, 8]:
        return "☀️ Verão"
    else:
        return "🍂 Outono"

async def resetar_temporada(context: ContextTypes.DEFAULT_TYPE):
    global pontuacoes
    pontuacoes = {}
    salvar_pontuacoes(pontuacoes)
    print("🔄 Temporada resetada!")

# ======================================================
# 🔹 LOOP PRINCIPAL
# ======================================================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("ranking", ranking))

    # Agendamentos das estações
    job_queue = app.job_queue
    datas_reset = [
        datetime(datetime.now().year, 3, 1),
        datetime(datetime.now().year, 6, 1),
        datetime(datetime.now().year, 9, 1),
        datetime(datetime.now().year, 12, 1),
    ]
    for data in datas_reset:
        job_queue.run_once(resetar_temporada, when=data)

    print("🤖 Bot rodando com quiz, bônus, estações e limpeza automática.")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

# ======================================================
# 🔹 EXECUÇÃO (modo Render Web Service)
# ======================================================
if __name__ == "__main__":
    def iniciar_bot():
        asyncio.run(main())

    bot_thread = Thread(target=iniciar_bot)
    bot_thread.start()

    # Mantém o Flask ativo para o Render detectar porta aberta
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask ativo em http://0.0.0.0:{port}")
    web_app.run(host="0.0.0.0", port=port)
