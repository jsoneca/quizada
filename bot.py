import os
import random
import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import logging

# === CONFIGURAÇÕES GERAIS ===
TOKEN = os.getenv("BOT_TOKEN")
DB = "quizbot.db"
QUIZ_INTERVALO = 45 * 60  # 45 minutos
HORARIO_INICIO = 7
HORARIO_FIM = 23
PONTOS_ACERTO = 35
BONUS_SEMANAIS = [500, 400, 300, 300]

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# === BANCO DE DADOS ===
def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            pontos INTEGER DEFAULT 50,
            ultima_interacao TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("📦 Banco de dados inicializado com sucesso.")

def add_pontos(user_id, nome, pontos):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios WHERE id=?", (user_id,))
    user = cur.fetchone()
    if user:
        cur.execute(
            "UPDATE usuarios SET pontos=pontos+?, ultima_interacao=? WHERE id=?",
            (pontos, datetime.now().isoformat(), user_id)
        )
    else:
        cur.execute(
            "INSERT INTO usuarios (id, nome, pontos, ultima_interacao) VALUES (?, ?, ?, ?)",
            (user_id, nome, 50 + pontos, datetime.now().isoformat())
        )
    conn.commit()
    conn.close()
    logger.info(f"🏅 {nome} recebeu {pontos} pontos (Total atualizado).")

def get_ranking():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT nome, pontos FROM usuarios ORDER BY pontos DESC LIMIT 10")
    ranking = cur.fetchall()
    conn.close()
    return ranking

# === QUIZZES ===
def load_quizzes():
    try:
        with open("quizzes.json", "r", encoding="utf-8") as f:
            quizzes = json.load(f)
            logger.info(f"✅ {len(quizzes)} quizzes carregados com sucesso.")
            return quizzes
    except Exception as e:
        logger.error(f"Erro ao carregar quizzes: {e}")
        return []

QUIZZES = load_quizzes()

# === FUNÇÕES DO BOT ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Bem-vindo ao QuizBot! Use /join para participar e /ranking para ver o ranking!")
    logger.info(f"👋 Novo usuário iniciou o bot: {update.effective_user.first_name}")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_pontos(user.id, user.first_name, 0)
    if "participantes" not in context.bot_data:
        context.bot_data["participantes"] = set()
    context.bot_data["participantes"].add(user.id)
    await update.message.reply_text(f"{user.first_name}, você entrou no quiz! Boa sorte!")
    logger.info(f"✅ {user.first_name} entrou na lista de participantes.")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = get_ranking()
    msg = "🏆 Ranking Atual:\n"
    for i, (nome, pontos) in enumerate(ranking, 1):
        msg += f"{i}. {nome} — {pontos} pts\n"
    await update.message.reply_text(msg)
    logger.info(f"📊 Ranking solicitado por {update.effective_user.first_name}")

# === ENVIO DE QUIZZES ===
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now()
    if not (HORARIO_INICIO <= agora.hour < HORARIO_FIM):
        logger.info("⏰ Fora do horário permitido. Nenhum quiz enviado.")
        return

    if "participantes" not in context.bot_data or not context.bot_data["participantes"]:
        logger.info("⚠️ Nenhum participante ativo. Quiz não enviado.")
        return

    quiz = random.choice(QUIZZES)
    keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in quiz["opts"]]
    markup = InlineKeyboardMarkup(keyboard)

    context.bot_data["quiz_atual"] = quiz
    logger.info(f"🧠 Novo quiz enviado: {quiz['q']}")

    for chat_id in context.bot_data["participantes"]:
        try:
            await context.bot.send_message(chat_id, quiz["q"], reply_markup=markup)
        except Exception as e:
            logger.error(f"Erro ao enviar quiz para {chat_id}: {e}")

# === RESPOSTAS ===
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    resposta = query.data
    quiz_atual = context.bot_data.get("quiz_atual")

    if quiz_atual and resposta == quiz_atual["ans"]:
        add_pontos(user.id, user.first_name, PONTOS_ACERTO)
        await query.edit_message_text(f"✅ Correto! +{PONTOS_ACERTO} pontos para {user.first_name}!")
        logger.info(f"🎯 {user.first_name} acertou a resposta!")
    else:
        await query.edit_message_text("❌ Errado!")
        logger.info(f"❌ {user.first_name} errou a resposta.")

# === ROTINA PRINCIPAL ===
async def main():
    logger.info("🚀 Iniciando o QuizBot...")
    app = ApplicationBuilder().token(TOKEN).build()
    init_db()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CallbackQueryHandler(responder))

    # Inicializar o JobQueue manualmente
    jq = app.job_queue
    jq.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO, first=10)
    logger.info("📆 Agendamento de quizzes configurado a cada 45 minutos (07h–23h).")

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
