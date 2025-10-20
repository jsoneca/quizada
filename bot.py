import os
import json
import random
import asyncio
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from telegram.constants import ParseMode

# ======================================================
# 🔹 CONFIGURAÇÕES
# ======================================================
TOKEN = os.getenv("BOT_TOKEN")  # Definido no Render
PONTUACOES_FILE = "pontuacoes.json"
QUIZZES_FILE = "quizzes.json"

# Flask para manter o serviço ativo
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "🤖 Bot de Quiz ativo no Render!"

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

    # Limpa o quiz anterior
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
        explanation=f"✅ Resposta correta: {opcoes[resposta_certa]}"
    )

    ultimo_quiz[update.effective_chat.id] = msg.message_id

# ======================================================
# 🔹 COMANDOS
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
# 🔹 ESTAÇÕES E RESET
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
# 🔹 EXECUÇÃO DO BOT E FLASK NO MESMO LOOP
# ======================================================
async def iniciar_bot():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("ranking", ranking))

    # Agendar resets das temporadas
    job_queue = app.job_queue
    for mes in [3, 6, 9, 12]:
        data = datetime(datetime.now().year, mes, 1)
        job_queue.run_once(resetar_temporada, when=data)

    print("🤖 Bot de Quiz iniciado com sucesso!")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

# ======================================================
# 🔹 INICIALIZAÇÃO (Render Web Service)
# ======================================================
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(iniciar_bot())

    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask ativo em http://0.0.0.0:{port}")
    web_app.run(host="0.0.0.0", port=port)
