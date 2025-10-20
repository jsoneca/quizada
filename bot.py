import json
import random
import asyncio
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os

# --- CONFIGURAÇÕES ---
TOKEN = os.getenv("BOT_TOKEN")  # Pegando o token do Render
QUIZ_FILE = "quizzes.json"
PONTUACOES_FILE = "pontuacoes.json"

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🤖 Bot do Quiz rodando no Render com Flask!"

# --- FUNÇÕES DE SUPORTE ---
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

async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    chats = context.job.data["chats"]
    quizzes = carregar_quizzes()
    quiz = random.choice(quizzes)

    for chat_id in chats:
        try:
            # Limpa quiz anterior, se existir
            if "mensagem_quiz" in context.chat_data:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=context.chat_data["mensagem_quiz"])
                except:
                    pass

            opcoes = quiz["opcoes"]
            botoes = [[InlineKeyboardButton(opcao, callback_data=f"quiz|{quiz['correta']}|{opcao}")]
                      for opcao in opcoes]
            reply_markup = InlineKeyboardMarkup(botoes)

            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🧩 *Quiz:*\n\n{quiz['pergunta']}",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            context.chat_data["mensagem_quiz"] = msg.message_id

        except Exception as e:
            print(f"Erro ao enviar quiz: {e}")

# --- HANDLERS ---
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 Olá! Bem-vindo(a) ao Quiz!\n\n"
        "Use /entrar para participar da pontuação e competir nos quizzes automáticos!"
    )

async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pontuacoes = carregar_pontuacoes()
    if str(user.id) not in pontuacoes:
        pontuacoes[str(user.id)] = {"nome": user.first_name, "pontos": 0}
        salvar_pontuacoes(pontuacoes)
        await update.message.reply_text(f"✅ {user.first_name}, você foi adicionado(a) ao ranking!")
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
            f"✅ {user.first_name}, você acertou!\n\nA resposta correta era: *{correta}* 🎯",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"❌ {user.first_name}, resposta incorreta!\n\nA resposta certa era: *{correta}*.",
            parse_mode="Markdown"
        )

# --- LOOP PRINCIPAL DO BOT ---
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("iniciar", iniciar))
    app.add_handler(CommandHandler("entrar", entrar))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CallbackQueryHandler(resposta_quiz, pattern="^quiz\\|"))

    # IDs dos grupos/chats para enviar quizzes automáticos
    chats = []  # insira aqui manualmente se quiser testes diretos

    job_queue = app.job_queue
    job_queue.run_repeating(enviar_quiz, interval=45 * 60, first=10, data={"chats": chats})

    print("🤖 Bot do Quiz rodando normalmente (Render Web Service)!")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

# --- THREAD PARA FLASK + BOT ---
def iniciar_bot():
    asyncio.run(main())

if __name__ == "__main__":
    threading.Thread(target=iniciar_bot).start()
    app_flask.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
