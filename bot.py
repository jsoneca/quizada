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

# === CONFIGURAÇÕES ===
TOKEN = os.getenv("BOT_TOKEN", "COLOQUE_SEU_TOKEN_AQUI")
QUIZES_PATH = "quizzes.json"
PONTUACOES_PATH = "pontuacoes.json"
INTERVALO_QUIZ = 45 * 60  # 45 minutos
CHATS_FILE = "chats.json"

# === FLASK ===
app_flask = Flask(__name__)

@app_flask.route("/")
def index():
    return "🤖 Bot ativo no Render!"

# === UTILITÁRIOS ===
def carregar_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def salvar_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# === QUIZES E PONTUAÇÕES ===
quizzes = carregar_json(QUIZES_PATH, [])
pontuacoes = carregar_json(PONTUACOES_PATH, {})
chats = carregar_json(CHATS_FILE, [])

# === COMANDOS ===
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 Olá! Eu sou o Quizada!\n\n"
        "👉 Use /entrar para participar do ranking de pontuações.\n"
        "Os quizzes são postados automaticamente a cada 45 minutos!"
    )

async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    if user_id not in pontuacoes:
        pontuacoes[user_id] = {"nome": user.first_name, "pontos": 0}
        salvar_json(PONTUACOES_PATH, pontuacoes)
        await update.message.reply_text("✅ Você entrou para o ranking! Boa sorte! 🍀")
    else:
        await update.message.reply_text("👋 Você já está participando do ranking!")

async def pontuacoes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        await update.message.reply_text("Ainda não há pontuações registradas.")
        return
    texto = "🏆 *Pontuações Atuais:*\n\n"
    for user_id, dados in pontuacoes.items():
        texto += f"{dados['nome']}: {dados['pontos']} pontos\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        await update.message.reply_text("Nenhum jogador ainda 😢")
        return
    top = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)[:10]
    texto = "🥇 *Ranking Geral:*\n\n"
    for i, (_, dados) in enumerate(top, start=1):
        texto += f"{i}. {dados['nome']} — {dados['pontos']} pontos\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

# === ENVIO DE QUIZ ===
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    if not quizzes:
        print("⚠️ Nenhum quiz disponível.")
        return

    quiz = random.choice(quizzes)
    pergunta = quiz["pergunta"]
    opcoes = quiz["opcoes"]
    resposta_correta = quiz["correta"]

    for chat_id in chats:
        try:
            await context.bot.send_poll(
                chat_id=chat_id,
                question=f"🧩 Quiz:\n\n{pergunta}",
                options=opcoes,
                type="quiz",
                correct_option_id=resposta_correta,
                is_anonymous=False
            )
        except Exception as e:
            print(f"Erro ao enviar quiz para {chat_id}: {e}")

# === LOOP PRINCIPAL ===
async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Corrigir JobQueue para Python 3.13
    job_queue = JobQueue()
    job_queue._application = application  # Força referência direta
    job_queue.set_dispatcher(application)  # Evita weakref
    job_queue.scheduler.start()

    # Registrar comandos
    application.add_handler(CommandHandler("iniciar", iniciar))
    application.add_handler(CommandHandler("entrar", entrar))
    application.add_handler(CommandHandler("pontuacoes", pontuacoes_cmd))
    application.add_handler(CommandHandler("ranking", ranking))

    # Agendar quizzes
    job_queue.run_repeating(enviar_quiz, interval=INTERVALO_QUIZ, first=10)

    await application.initialize()
    await application.start()
    print("🤖 Bot rodando com quizzes automáticos!")
    await application.updater.start_polling()
    await asyncio.Event().wait()  # Mantém rodando indefinidamente

def iniciar_bot():
    asyncio.run(main())

# === THREADS ===
threading.Thread(target=iniciar_bot, daemon=True).start()

# === INICIAR FLASK ===
if __name__ == "__main__":
    app_flask.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
