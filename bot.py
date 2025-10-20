import asyncio
import json
import random
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 🔑 Token do seu bot
TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

# 📂 Caminhos dos arquivos
QUIZ_FILE = "quizzes.json"
PONTUACOES_FILE = "pontuacoes.json"

# 🌐 Flask (Render exige uma porta aberta)
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot ativo e rodando!"

# 🧮 Funções auxiliares
def carregar_pontuacoes():
    try:
        with open(PONTUACOES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def salvar_pontuacoes(pontuacoes):
    with open(PONTUACOES_FILE, "w", encoding="utf-8") as f:
        json.dump(pontuacoes, f, ensure_ascii=False, indent=2)

def carregar_quizzes():
    try:
        with open(QUIZ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# 🧩 Enviar quiz automaticamente
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    chats = context.job.data.get("chats", [])
    quizzes = carregar_quizzes()

    if not quizzes or not chats:
        return

    quiz = random.choice(quizzes)
    pergunta = quiz["pergunta"]
    opcoes = quiz["opcoes"]
    resposta_correta = quiz["resposta"]

    keyboard = [
        [InlineKeyboardButton(text=opcao, callback_data=f"quiz|{opcao}|{resposta_correta}")]
        for opcao in opcoes
    ]

    for chat_id in chats:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🧠 *Quiz:*\n\n{pergunta}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# 🧍‍♂️ Entrar no ranking
async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pontuacoes = carregar_pontuacoes()

    if str(user.id) in pontuacoes:
        await update.message.reply_text("✅ Você já está participando do ranking!")
    else:
        pontuacoes[str(user.id)] = {"nome": user.first_name, "pontos": 0}
        salvar_pontuacoes(pontuacoes)
        await update.message.reply_text("🎉 Você entrou para o ranking de pontuações!")

# 🏁 Iniciar o bot
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Eu sou o *QuizadA Bot!* 🧩\n\n"
        "Fique ligado — quizzes serão enviados automaticamente a cada 45 minutos!",
        parse_mode="Markdown"
    )

# 🏅 Ver pontuação
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pontuacoes = carregar_pontuacoes()
    if not pontuacoes:
        await update.message.reply_text("📊 Ainda não há pontuações registradas.")
        return

    ranking = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)
    msg = "🏆 *Ranking Atual:*\n\n"
    for i, (user_id, dados) in enumerate(ranking[:10], start=1):
        msg += f"{i}. {dados['nome']} — {dados['pontos']} pontos\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# 🎯 Resposta ao quiz
async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, resposta_usuario, resposta_correta = query.data.split("|")

    pontuacoes = carregar_pontuacoes()
    user = query.from_user

    if resposta_usuario == resposta_correta:
        pontos = pontuacoes.get(str(user.id), {"nome": user.first_name, "pontos": 0})
        pontos["pontos"] += 10
        pontuacoes[str(user.id)] = pontos
        salvar_pontuacoes(pontuacoes)
        await query.answer("✅ Resposta certa! +10 pontos!")
    else:
        await query.answer("❌ Resposta errada!")

# 🚀 Loop principal do bot
async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Comandos
    application.add_handler(CommandHandler("iniciar", iniciar))
    application.add_handler(CommandHandler("entrar", entrar))
    application.add_handler(CommandHandler("ranking", ranking))
    application.add_handler(CallbackQueryHandler(resposta_quiz, pattern="^quiz"))

    # Agendamento automático
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    chats = [-1000000000000]  # coloque o ID do grupo aqui
    scheduler.add_job(enviar_quiz, "interval", minutes=45, args=[application.bot.create_task_context()], kwargs={"job": type("obj", (), {"data": {"chats": chats}})})
    scheduler.start()

    print("🤖 Bot rodando com python-telegram-bot 20.3 e Flask.")
    await application.run_polling()

# 🔄 Thread para rodar o bot e o Flask juntos
def iniciar_bot():
    asyncio.run(main())

if __name__ == "__main__":
    threading.Thread(target=iniciar_bot).start()
    app.run(host="0.0.0.0", port=10000)
