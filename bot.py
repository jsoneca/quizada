import os
import random
import asyncio
import logging
import json
from datetime import datetime, timedelta, time
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
QUIZ_INTERVALO = 45 * 60  # 45 minutos (em segundos)
HORARIO_INICIO = 7
HORARIO_FIM = 23
PONTOS_POR_ACERTO = 35
PONTOS_INICIAIS = 50

# === Configuração de logs (visível no Render) ===
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Carregar quizzes ===
def load_quizzes():
    try:
        with open("quizzes.json", "r", encoding="utf-8") as f:
            quizzes = json.load(f)
            if not isinstance(quizzes, list):
                raise ValueError("O arquivo quizzes.json deve conter uma lista de quizzes.")
            logger.info(f"✅ {len(quizzes)} quizzes carregados com sucesso.")
            return quizzes
    except FileNotFoundError:
        logger.warning("⚠️ Arquivo quizzes.json não encontrado. Usando lista padrão.")
        return [
            {"q": "Qual a capital da França?", "opts": ["Paris", "Londres", "Roma", "Berlim"], "ans": "Paris"}
        ]
    except Exception as e:
        logger.error(f"Erro ao carregar quizzes: {e}")
        return []

QUIZZES = load_quizzes()

# === Banco de dados em memória ===
usuarios = defaultdict(lambda: {"pontos": PONTOS_INICIAIS, "level": 1, "acertos": 0, "erros": 0, "ultimo_quiz": None})
respostas_pendentes = {}

# === Funções ===
def get_level(pontos):
    return 1 + pontos // 200  # Exemplo: 1 nível a cada 200 pontos

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 Bem-vindo ao QuizBot! Use /join para participar.")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in usuarios:
        usuarios[user.id] = {"pontos": PONTOS_INICIAIS, "level": 1, "acertos": 0, "erros": 0}
        await update.message.reply_text(f"✅ {user.first_name}, você entrou no quiz! Boa sorte!")
    else:
        await update.message.reply_text("⚡ Você já está participando!")

async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now().time()
    if agora < time(HORARIO_INICIO, 0) or agora > time(HORARIO_FIM, 0):
        logger.info("⏸️ Fora do horário (07h–23h). Nenhum quiz enviado agora.")
        return

    if not QUIZZES:
        logger.warning("⚠️ Nenhum quiz disponível.")
        return

    quiz = random.choice(QUIZZES)
    keyboard = [
        [InlineKeyboardButton(opt, callback_data=opt)] for opt in quiz["opts"]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    chat_id = context.job.chat_id if context.job else None
    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🧩 {quiz['q']}",
            reply_markup=reply_markup
        )
        respostas_pendentes[chat_id] = quiz
        logger.info(f"📨 Quiz enviado para {chat_id}: {quiz['q']}")

async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat_id
    resposta = query.data
    quiz = respostas_pendentes.get(chat_id)

    if not quiz:
        await query.answer("⏳ Nenhum quiz ativo no momento.")
        return

    if resposta == quiz["ans"]:
        usuarios[user.id]["pontos"] += PONTOS_POR_ACERTO
        usuarios[user.id]["acertos"] += 1
        usuarios[user.id]["level"] = get_level(usuarios[user.id]["pontos"])
        await query.edit_message_text(f"✅ Correto, {user.first_name}! +{PONTOS_POR_ACERTO} pontos.")
    else:
        usuarios[user.id]["erros"] += 1
        await query.edit_message_text(f"❌ Errado, {user.first_name}! Resposta certa: {quiz['ans']}")

    logger.info(f"👤 {user.first_name} respondeu '{resposta}' (correta: {quiz['ans']})")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = sorted(usuarios.items(), key=lambda x: x[1]["pontos"], reverse=True)
    msg = "🏆 *Ranking Atual:*\n\n"
    for i, (uid, data) in enumerate(ranking[:10], 1):
        msg += f"{i}. {context.bot_data.get(uid, 'Jogador')} — {data['pontos']} pts (Lv {data['level']})\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CallbackQueryHandler(resposta_quiz))

    # Agendador
    job_queue = app.job_queue
    job_queue.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO, first=10, data={"chat_id": -100})  # Substitua -100 pelo ID do grupo

    logger.info("🤖 Bot rodando com sistema de temporadas, bônus e logs detalhados...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
