import asyncio
import json
import os
import random
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

# =========================================================
# 🔐 TOKEN DO BOT
# (usando variável de ambiente do Render)
TOKEN = os.getenv("BOT_TOKEN")

# =========================================================
# 📁 ARQUIVOS DE DADOS
QUIZ_FILE = "quizzes.json"
PONTOS_FILE = "pontuacoes.json"

# =========================================================
# 🔄 FUNÇÕES AUXILIARES
def carregar_json(caminho, padrao):
    if not os.path.exists(caminho):
        salvar_json(caminho, padrao)
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# =========================================================
# ⚙️ CARREGAMENTO INICIAL
quizzes = carregar_json(QUIZ_FILE, [])
pontuacoes = carregar_json(PONTOS_FILE, {})

mensagens_quiz = {}

# =========================================================
# 🧠 FUNÇÕES DO QUIZ
async def enviar_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia um quiz aleatório e remove o anterior."""
    chat_id = update.effective_chat.id

    # Apaga quiz anterior
    if chat_id in mensagens_quiz:
        try:
            await context.bot.delete_message(chat_id, mensagens_quiz[chat_id])
        except:
            pass

    if not quizzes:
        await update.message.reply_text("❌ Nenhum quiz disponível.")
        return

    quiz = random.choice(quizzes)
    pergunta = quiz["pergunta"]
    opcoes = quiz["opcoes"]
    correta = quiz["correta"]

    botoes = [
        [InlineKeyboardButton(text=o, callback_data=f"quiz|{correta}|{o}")]
        for o in opcoes
    ]
    markup = InlineKeyboardMarkup(botoes)

    msg = await update.message.reply_text(f"🧩 {pergunta}", reply_markup=markup)
    mensagens_quiz[chat_id] = msg.message_id

async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica a resposta e atualiza pontuação."""
    query = update.callback_query
    await query.answer()
    _, correta, escolha = query.data.split("|")

    user_id = str(query.from_user.id)
    nome = query.from_user.first_name

    if user_id not in pontuacoes:
        pontuacoes[user_id] = {"nome": nome, "pontos": 0}

    if escolha == correta:
        pontuacoes[user_id]["pontos"] += 10
        texto = f"✅ Correto, {nome}! +10 pontos."
    else:
        texto = f"❌ Errado, {nome}. A resposta certa era: {correta}"

    salvar_json(PONTOS_FILE, pontuacoes)
    await query.edit_message_text(texto)

# =========================================================
# 🏆 COMANDOS DE PONTUAÇÃO
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        await update.message.reply_text("📊 Ninguém pontuou ainda!")
        return

    ranking = sorted(
        pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True
    )
    texto = "🏅 *Ranking Geral*\n\n"
    for i, (uid, info) in enumerate(ranking[:10], start=1):
        texto += f"{i}. {info['nome']} — {info['pontos']} pts\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dá bônus diário de 20 pontos."""
    user_id = str(update.effective_user.id)
    nome = update.effective_user.first_name

    if user_id not in pontuacoes:
        pontuacoes[user_id] = {"nome": nome, "pontos": 0}

    pontuacoes[user_id]["pontos"] += 20
    salvar_json(PONTOS_FILE, pontuacoes)
    await update.message.reply_text(f"🎁 {nome}, você ganhou +20 pontos de bônus!")

# =========================================================
# 🌦 ESTAÇÕES (pontuação reinicia a cada estação)
def proxima_estacao(data):
    ano = data.year
    estacoes = [
        datetime(ano, 3, 1),
        datetime(ano, 6, 1),
        datetime(ano, 9, 1),
        datetime(ano, 12, 1)
    ]
    for e in estacoes:
        if e > data:
            return e
    return datetime(ano + 1, 3, 1)

def resetar_temporada():
    global pontuacoes
    pontuacoes = {}
    salvar_json(PONTOS_FILE, pontuacoes)
    print("🔄 Pontuações resetadas para nova temporada!")

# =========================================================
# 🌐 FLASK WEB SERVICE (para Render)
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "🤖 Bot do Telegram ativo no Render!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# =========================================================
# 🚀 EXECUÇÃO DO BOT
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("quiz", enviar_quiz))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CommandHandler("bonus", bonus))
    app.add_handler(CallbackQueryHandler(resposta_quiz, pattern=r"^quiz\|"))

    # Scheduler das estações
    scheduler = AsyncIOScheduler()
    hoje = datetime.now()
    prox = proxima_estacao(hoje)
    scheduler.add_job(resetar_temporada, trigger=DateTrigger(run_date=prox))
    scheduler.start()

    print("🤖 Bot rodando com quiz, bônus, estações e limpeza automática.")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())
