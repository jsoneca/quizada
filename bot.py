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

TOKEN = os.getenv("BOT_TOKEN")  # defina no Render
DB = "quizbot.db"

# === Configurações ===
QUIZ_INTERVALO = 45 * 60  # 45 minutos
HORARIO_INICIO = 7
HORARIO_FIM = 23
PONTOS_ACERTO = 35
BONUS_SEMANAIS = [500, 400, 300, 300]

# === Banco de dados ===
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

def get_ranking():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT nome, pontos FROM usuarios ORDER BY pontos DESC LIMIT 10")
    ranking = cur.fetchall()
    conn.close()
    return ranking

# === Carregar quizzes ===
def load_quizzes():
    try:
        with open("quizzes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Erro ao carregar quizzes:", e)
        return []

QUIZZES = load_quizzes()

# === Funções do bot ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Bem-vindo ao QuizBot! Use /join para participar e /ranking para ver o ranking!")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_pontos(user.id, user.first_name, 0)
    await update.message.reply_text(f"{user.first_name}, você entrou no quiz! Boa sorte!")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = get_ranking()
    msg = "🏆 Ranking Atual:\n"
    for i, (nome, pontos) in enumerate(ranking, 1):
        msg += f"{i}. {nome} — {pontos} pts\n"
    await update.message.reply_text(msg)

# === Sistema de quiz ===
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now()
    if not (HORARIO_INICIO <= agora.hour < HORARIO_FIM):
        return

    quiz = random.choice(QUIZZES)
    keyboard = [
        [InlineKeyboardButton(opt, callback_data=opt)] for opt in quiz["opts"]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    for chat_id in context.bot_data.get("participantes", []):
        try:
            await context.bot.send_message(chat_id, quiz["q"], reply_markup=markup)
            context.bot_data["quiz_atual"] = quiz
        except Exception:
            pass

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    resposta = query.data
    quiz_atual = context.bot_data.get("quiz_atual")

    if quiz_atual and resposta == quiz_atual["ans"]:
        add_pontos(user.id, user.first_name, PONTOS_ACERTO)
        await query.edit_message_text(f"✅ Correto! +{PONTOS_ACERTO} pontos para {user.first_name}!")
    else:
        await query.edit_message_text("❌ Errado!")

# === Rotina principal ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    init_db()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CallbackQueryHandler(responder))

    app.job_queue.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO, first=10)

    print("🤖 Bot rodando com sistema de temporadas e bônus...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
