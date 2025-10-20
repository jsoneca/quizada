import json
import random
import asyncio
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, Poll
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    PollAnswerHandler,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

# ==============================
# CONFIGURAÇÕES
# ==============================
TOKEN = os.getenv("BOT_TOKEN")

PONTUACOES_FILE = "pontuacoes.json"
QUIZZES_FILE = "quizzes.json"
TEMPORADA_FILE = "temporada_atual.json"

app_flask = Flask(__name__)

# ==============================
# FUNÇÕES DE ARQUIVOS
# ==============================
def carregar_arquivo(caminho, padrao):
    if not os.path.exists(caminho):
        salvar_arquivo(caminho, padrao)
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_arquivo(caminho, conteudo):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, indent=4, ensure_ascii=False)


# ==============================
# DADOS INICIAIS
# ==============================
pontuacoes = carregar_arquivo(PONTUACOES_FILE, {})
quizzes = carregar_arquivo(QUIZZES_FILE, [])
temporada = carregar_arquivo(TEMPORADA_FILE, {"estacao": "🌸 Primavera"})

# ==============================
# FUNÇÕES DO BOT
# ==============================
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌟 Olá! Sou o Quizada!\n"
        "Use /entrar para participar do ranking.\n"
        "Os quizzes são postados automaticamente a cada 45 minutos!"
    )


async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if str(user.id) not in pontuacoes:
        pontuacoes[str(user.id)] = {"nome": user.first_name, "pontos": 0, "chat_id": update.effective_chat.id}
        salvar_arquivo(PONTUACOES_FILE, pontuacoes)
        await update.message.reply_text(f"🎮 {user.first_name} entrou no ranking!")
    else:
        await update.message.reply_text("⚡ Você já está participando!")


async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        await update.message.reply_text("Nenhum jogador ainda 😢")
        return

    ranking_ordenado = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)
    texto = f"🏆 Ranking - {temporada['estacao']}\n\n"
    for i, (_, dados) in enumerate(ranking_ordenado[:10], start=1):
        texto += f"{i}. {dados['nome']} - {dados['pontos']} pts\n"
    await update.message.reply_text(texto)


async def pontuacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pontos = pontuacoes.get(str(user.id), {}).get("pontos", 0)
    await update.message.reply_text(f"🎯 {user.first_name}, você tem {pontos} pontos.")


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "📚 Comandos disponíveis:\n"
        "/iniciar - Apresenta o bot\n"
        "/entrar - Entra no ranking\n"
        "/ranking - Mostra o ranking\n"
        "/pontuacao - Mostra seus pontos\n"
        "/ajuda - Mostra esta mensagem"
    )
    await update.message.reply_text(texto)


# ==============================
# QUIZ AUTOMÁTICO
# ==============================
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    if not quizzes or not pontuacoes:
        return

    quiz = random.choice(quizzes)
    pergunta = quiz["pergunta"]
    opcoes = quiz["opcoes"]
    resposta_correta = quiz["correta"]

    for user_id, dados in pontuacoes.items():
        chat_id = dados.get("chat_id")
        if not chat_id:
            continue

        mensagem = await context.bot.send_poll(
            chat_id=chat_id,
            question=f"🧩 Quiz:\n\n{pergunta}",
            options=opcoes,
            type=Poll.QUIZ,
            correct_option_id=resposta_correta,
            is_anonymous=False,
        )

        # Apaga a mensagem após 45 minutos (2700 segundos)
        context.job_queue.run_once(
            apagar_mensagem, 2700, data={"chat_id": chat_id, "msg_id": mensagem.message_id}
        )


async def apagar_mensagem(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.delete_message(context.job.data["chat_id"], context.job.data["msg_id"])
    except Exception:
        pass


# ==============================
# PONTUAÇÃO AO ACERTAR
# ==============================
async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.poll_answer.user
    if not user:
        return
    if str(user.id) not in pontuacoes:
        return
    pontuacoes[str(user.id)]["pontos"] += 5
    salvar_arquivo(PONTUACOES_FILE, pontuacoes)


# ==============================
# RESET DE ESTAÇÕES
# ==============================
async def resetar_temporada():
    mes = datetime.now().month
    if 3 <= mes < 6:
        temporada["estacao"] = "🌸 Primavera"
    elif 6 <= mes < 9:
        temporada["estacao"] = "☀️ Verão"
    elif 9 <= mes < 12:
        temporada["estacao"] = "🍁 Outono"
    else:
        temporada["estacao"] = "❄️ Inverno"

    salvar_arquivo(TEMPORADA_FILE, temporada)
    for user_id in pontuacoes:
        pontuacoes[user_id]["pontos"] = 0
    salvar_arquivo(PONTUACOES_FILE, pontuacoes)


# ==============================
# BÔNUS SEMANAL
# ==============================
async def bonus_semanal():
    for user_id in pontuacoes:
        pontuacoes[user_id]["pontos"] += 10
    salvar_arquivo(PONTUACOES_FILE, pontuacoes)


# ==============================
# EXECUÇÃO PRINCIPAL
# ==============================
async def main():
    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # Agendador de tarefas
    scheduler = AsyncIOScheduler()
    scheduler.add_job(enviar_quiz, "interval", minutes=45, args=[application])
    scheduler.add_job(resetar_temporada, "cron", month="3,6,9,12", day=1, hour=0)
    scheduler.add_job(bonus_semanal, "cron", day_of_week="sun", hour=12)
    scheduler.start()

    # Handlers
    application.add_handler(CommandHandler("iniciar", iniciar))
    application.add_handler(CommandHandler("entrar", entrar))
    application.add_handler(CommandHandler("ranking", ranking))
    application.add_handler(CommandHandler("pontuacao", pontuacao))
    application.add_handler(CommandHandler("ajuda", ajuda))
    application.add_handler(PollAnswerHandler(resposta_quiz))

    print("🤖 Quizada (v21.4) rodando com sucesso!")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)


def iniciar_bot():
    asyncio.run(main())


@app_flask.route("/")
def home():
    return "🎮 Quizada está ativo e rodando na nuvem!"


if __name__ == "__main__":
    threading.Thread(target=iniciar_bot).start()
    app_flask.run(host="0.0.0.0", port=10000)
