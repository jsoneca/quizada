import json
import random
import threading
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import os

# === CONFIGURAÇÕES ===
TOKEN = os.getenv("BOT_TOKEN")  # token do Render
QUIZ_FILE = "quizzes.json"
PONTUACOES_FILE = "pontuacoes.json"

# === FLASK SERVER PARA O RENDER ===
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "🤖 Bot de Quiz está rodando no Render (modo Web Service)!"


# === FUNÇÕES AUXILIARES ===
def carregar_quizzes():
    with open(QUIZ_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def carregar_pontuacoes():
    try:
        with open(PONTUACOES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def salvar_pontuacoes(pontuacoes):
    with open(PONTUACOES_FILE, "w", encoding="utf-8") as f:
        json.dump(pontuacoes, f, indent=4, ensure_ascii=False)


# === FUNÇÕES DE JOGO ===
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    chats = context.job.data["chats"]
    quizzes = carregar_quizzes()
    quiz = random.choice(quizzes)

    for chat_id in chats:
        try:
            botoes = [
                [InlineKeyboardButton(opcao, callback_data=f"quiz|{quiz['correta']}|{opcao}")]
                for opcao in quiz["opcoes"]
            ]
            reply_markup = InlineKeyboardMarkup(botoes)

            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🧩 *Quiz:*\n\n{quiz['pergunta']}",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

            print(f"[LOG] Quiz enviado para chat {chat_id}")
        except Exception as e:
            print(f"[ERRO] Falha ao enviar quiz: {e}")


# === COMANDOS ===
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 Olá! Bem-vindo(a) ao Quiz!\n"
        "Use /entrar para participar do ranking e disputar os quizzes automáticos!"
    )

async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pontuacoes = carregar_pontuacoes()

    if str(user.id) not in pontuacoes:
        pontuacoes[str(user.id)] = {"nome": user.first_name, "pontos": 0}
        salvar_pontuacoes(pontuacoes)
        await update.message.reply_text(f"✅ {user.first_name}, você entrou no ranking!")
    else:
        await update.message.reply_text("⚠️ Você já está participando do ranking!")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pontuacoes = carregar_pontuacoes()
    ranking_ordenado = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)
    msg = "🏆 *Ranking Geral:*\n\n"
    for i, (user_id, dados) in enumerate(ranking_ordenado[:10], 1):
        msg += f"{i}️⃣ {dados['nome']}: {dados['pontos']} pontos\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    correta, resposta = query.data.split("|")[1:]
    user = query.from_user

    pontuacoes = carregar_pontuacoes()
    if str(user.id) not in pontuacoes:
        pontuacoes[str(user.id)] = {"nome": user.first_name, "pontos": 0}

    if resposta == correta:
        pontuacoes[str(user.id)]["pontos"] += 1
        salvar_pontuacoes(pontuacoes)
        await query.edit_message_text(
            f"✅ {user.first_name}, você acertou!\nA resposta correta era: *{correta}* 🎯",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"❌ {user.first_name}, resposta errada!\nA resposta certa era: *{correta}*.",
            parse_mode="Markdown"
        )


# === MAIN DO BOT ===
async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("iniciar", iniciar))
    application.add_handler(CommandHandler("entrar", entrar))
    application.add_handler(CommandHandler("ranking", ranking))
    application.add_handler(CallbackQueryHandler(resposta_quiz, pattern="^quiz\\|"))

    # chats aonde o bot enviará quizzes automáticos
    chats = []  # coloque IDs de grupos aqui, ex: [-1001234567890]

    # agendamento automático de quizzes
    job_queue = application.job_queue
    job_queue.run_repeating(enviar_quiz, interval=45 * 60, first=10, data={"chats": chats})

    print("🤖 Bot rodando com Flask + Telegram (modo Web Service)")
    await application.run_polling()


# === THREAD PARA FLASK + BOT ===
def iniciar_bot():
    asyncio.run(main())

if __name__ == "__main__":
    threading.Thread(target=iniciar_bot, daemon=True).start()
    app_flask.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
