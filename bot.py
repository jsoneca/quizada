import os
import random
import asyncio
import logging
import json
from datetime import datetime, timedelta, time, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from collections import defaultdict

# === Configurações do bot ===
TOKEN = os.getenv("BOT_TOKEN")
QUIZ_INTERVALO = 45 * 60  # 45 minutos
HORARIO_INICIO = 7
HORARIO_FIM = 23
PONTOS_POR_ACERTO = 35
PONTOS_INICIAIS = 50

# === Logging (mostra logs no Render) ===
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# === Banco de dados em memória ===
usuarios = defaultdict(lambda: {"pontos": PONTOS_INICIAIS, "level": 1, "acertos": 0, "erros": 0, "interacoes": 0})
respostas_pendentes = {}

# === Carregar quizzes do arquivo JSON ===
def load_quizzes():
    try:
        with open("quizzes.json", "r", encoding="utf-8") as f:
            quizzes = json.load(f)
            if not isinstance(quizzes, list):
                raise ValueError("O arquivo quizzes.json deve conter uma lista.")
            logger.info(f"✅ {len(quizzes)} quizzes carregados com sucesso.")
            return quizzes
    except FileNotFoundError:
        logger.warning("⚠️ quizzes.json não encontrado, usando perguntas padrão.")
        return [
            {"q": "Qual a capital da França?", "opts": ["Paris", "Londres", "Roma", "Berlim"], "ans": "Paris"},
            {"q": "Quem pintou a Mona Lisa?", "opts": ["Van Gogh", "Da Vinci", "Picasso", "Michelangelo"], "ans": "Da Vinci"},
        ]

QUIZZES = load_quizzes()

# === Funções utilitárias ===
def get_level(pontos):
    return 1 + pontos // 200

def get_top_usuarios(limit=10):
    return sorted(usuarios.items(), key=lambda x: x[1]["pontos"], reverse=True)[:limit]

def reset_interacoes():
    for data in usuarios.values():
        data["interacoes"] = 0

def get_estacao(data: date):
    mes = data.month
    if mes in [12, 1, 2]:
        return "Verão"
    elif mes in [3, 4, 5]:
        return "Outono"
    elif mes in [6, 7, 8]:
        return "Inverno"
    else:
        return "Primavera"

# === Comandos do bot ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 Bem-vindo ao *QuizBot*! Use /join para participar.", parse_mode="Markdown")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in usuarios:
        usuarios[user.id] = {"pontos": PONTOS_INICIAIS, "level": 1, "acertos": 0, "erros": 0, "interacoes": 0}
        await update.message.reply_text(f"✅ {user.first_name}, você entrou no quiz! Boa sorte!")
    else:
        await update.message.reply_text("⚡ Você já está participando!")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = get_top_usuarios()
    msg = "🏆 *Ranking Atual:*\n\n"
    for i, (uid, data) in enumerate(ranking, 1):
        msg += f"{i}. {context.bot_data.get(uid, 'Jogador')} — {data['pontos']} pts (Lv {data['level']})\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# === Envio de quiz ===
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now().time()
    if agora < time(HORARIO_INICIO, 0) or agora > time(HORARIO_FIM, 0):
        logger.info("⏸️ Fora do horário (07h–23h). Nenhum quiz enviado agora.")
        return

    if not QUIZZES:
        logger.warning("⚠️ Nenhum quiz disponível.")
        return

    quiz = random.choice(QUIZZES)
    keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in quiz["opts"]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    chat_id = context.job.data["chat_id"]
    await context.bot.send_message(chat_id=chat_id, text=f"🧩 {quiz['q']}", reply_markup=reply_markup)
    respostas_pendentes[chat_id] = quiz
    logger.info(f"📨 Quiz enviado para {chat_id}: {quiz['q']}")

# === Respostas ===
async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat_id
    resposta = query.data
    quiz = respostas_pendentes.get(chat_id)

    if not quiz:
        await query.answer("⏳ Nenhum quiz ativo no momento.")
        return

    usuarios[user.id]["interacoes"] += 1

    if resposta == quiz["ans"]:
        usuarios[user.id]["pontos"] += PONTOS_POR_ACERTO
        usuarios[user.id]["acertos"] += 1
        usuarios[user.id]["level"] = get_level(usuarios[user.id]["pontos"])
        await query.edit_message_text(f"✅ Correto, {user.first_name}! +{PONTOS_POR_ACERTO} pontos.")
    else:
        usuarios[user.id]["erros"] += 1
        await query.edit_message_text(f"❌ Errado, {user.first_name}! Resposta certa: {quiz['ans']}")

    logger.info(f"👤 {user.first_name} respondeu '{resposta}' (correta: {quiz['ans']})")

# === Bônus diário ===
async def bonus_diario(context: ContextTypes.DEFAULT_TYPE):
    if not usuarios:
        return
    mais_ativo = max(usuarios.items(), key=lambda x: x[1]["interacoes"])
    uid, data = mais_ativo
    data["pontos"] += 200
    reset_interacoes()
    logger.info(f"🌞 Bônus diário de 200 pontos para {uid}")

# === Bônus semanal ===
async def bonus_semanal(context: ContextTypes.DEFAULT_TYPE):
    ranking = get_top_usuarios(4)
    bonus = [500, 400, 300, 300]
    for (i, (uid, data)) in enumerate(ranking):
        data["pontos"] += bonus[i]
        logger.info(f"🏅 Bônus semanal de {bonus[i]} pontos para {uid}")

# === Reset a cada estação ===
async def reset_estacao(context: ContextTypes.DEFAULT_TYPE):
    top10 = get_top_usuarios(10)
    logger.info("🍂 Reset de estação — top 10:")
    for i, (uid, data) in enumerate(top10, 1):
        logger.info(f"{i}. {uid} — {data['pontos']} pts")

    # Reset geral
    for data in usuarios.values():
        data["pontos"] = PONTOS_INICIAIS
        data["level"] = 1
        data["acertos"] = 0
        data["erros"] = 0
        data["interacoes"] = 0
    logger.info("🔄 Pontuações resetadas para nova estação.")

# === Inicialização do bot ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CallbackQueryHandler(resposta_quiz))

    # JobQueue
    job_queue = app.job_queue
    chat_id = int(os.getenv("CHAT_ID", "-100"))  # ID do grupo ou chat
    job_queue.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO, first=10, data={"chat_id": chat_id})
    job_queue.run_daily(bonus_diario, time=time(0, 0))
    job_queue.run_daily(bonus_semanal, time=time(0, 0), days=(0,))  # Segunda-feira
    job_queue.run_monthly(reset_estacao, when="1st")  # Início de cada estação

    logger.info("🤖 Bot rodando com sistema de temporadas, bônus e logs detalhados...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
