import json
import os
import random
import asyncio
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberUpdated
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ChatMemberHandler, ContextTypes
)
from apscheduler.schedulers.background import BackgroundScheduler

# === TOKEN DO TELEGRAM ===
TOKEN = os.getenv("BOT_TOKEN")

# === ARQUIVOS DE DADOS ===
QUIZZES_FILE = "quizzes.json"
PONTUACOES_FILE = "pontuacoes.json"

# === LEITURA E SALVAMENTO DE DADOS ===
def carregar_quizzes():
    with open(QUIZZES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def carregar_pontuacoes():
    if not os.path.exists(PONTUACOES_FILE):
        with open(PONTUACOES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(PONTUACOES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_pontuacoes(pontuacoes):
    with open(PONTUACOES_FILE, "w", encoding="utf-8") as f:
        json.dump(pontuacoes, f, ensure_ascii=False, indent=2)

# === VARIÁVEIS ===
quizzes = carregar_quizzes()
pontuacoes = carregar_pontuacoes()
ultimo_quiz_id = None
mensagem_quiz_id = None
chat_id = None
estacao_atual = "Verão"

# === ESTAÇÕES DO ANO ===
def obter_estacao():
    mes = datetime.now().month
    if mes in [12, 1, 2]:
        return "☃️ Inverno"
    elif mes in [3, 4, 5]:
        return "🌸 Primavera"
    elif mes in [6, 7, 8]:
        return "🌞 Verão"
    else:
        return "🍂 Outono"

def resetar_temporada():
    global pontuacoes, estacao_atual
    estacao_atual = obter_estacao()
    pontuacoes = {}
    salvar_pontuacoes(pontuacoes)
    print(f"🌿 Nova temporada iniciada: {estacao_atual}")

# === QUIZ AUTOMÁTICO ===
async def enviar_quiz(app):
    global ultimo_quiz_id, mensagem_quiz_id, chat_id
    if not chat_id:
        return

    quiz = random.choice(quizzes)
    ultimo_quiz_id = quiz["id"]

    botoes = [
        [InlineKeyboardButton(opcao, callback_data=f"responder|{quiz['id']}|{i}")]
        for i, opcao in enumerate(quiz["opcoes"])
    ]
    markup = InlineKeyboardMarkup(botoes)

    # Apaga quiz anterior (mantém o chat limpo)
    if mensagem_quiz_id:
        try:
            await app.bot.delete_message(chat_id=chat_id, message_id=mensagem_quiz_id)
        except Exception:
            pass

    msg = await app.bot.send_message(
        chat_id=chat_id,
        text=f"🧩 *Quiz:*\n\n{quiz['pergunta']}",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    mensagem_quiz_id = msg.message_id

# === RESPOSTAS DO QUIZ ===
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, quiz_id, opcao = query.data.split("|")
    quiz = next(q for q in quizzes if str(q["id"]) == quiz_id)
    user = query.from_user

    pontuacoes = carregar_pontuacoes()
    nome = user.first_name

    if nome not in pontuacoes:
        pontuacoes[nome] = 0

    opcao = int(opcao)
    correta = int(quiz["correta"])

    if opcao == correta:
        pontuacoes[nome] += 10
        texto = f"✅ Correto, {nome}! +10 pontos!"
    else:
        texto = f"❌ Errado, {nome}! A resposta certa era: *{quiz['opcoes'][correta]}*."

    salvar_pontuacoes(pontuacoes)
    await query.edit_message_text(f"🧩 *Quiz:*\n\n{quiz['pergunta']}\n\n{texto}", parse_mode="Markdown")

# === COMANDOS ===
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global chat_id
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "👋 Olá! Eu sou o *Quiz Bot*.\n\n"
        "Use /entrar para participar do ranking e começar a acumular pontos nos quizzes automáticos 🧠",
        parse_mode="Markdown"
    )

async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.from_user.first_name
    pontuacoes = carregar_pontuacoes()

    if nome in pontuacoes:
        await update.message.reply_text("⚠️ Você já está participando do ranking!")
    else:
        pontuacoes[nome] = 0
        salvar_pontuacoes(pontuacoes)
        await update.message.reply_text("✅ Você foi adicionado ao ranking! Boa sorte nos próximos quizzes!")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pontuacoes = carregar_pontuacoes()
    if not pontuacoes:
        await update.message.reply_text("📊 Nenhum participante ainda!")
        return

    ranking = sorted(pontuacoes.items(), key=lambda x: x[1], reverse=True)
    texto = "🏆 *Ranking Atual:*\n\n"
    for i, (nome, pontos) in enumerate(ranking[:10], start=1):
        texto += f"{i}. {nome} — {pontos} pts\n"

    await update.message.reply_text(texto, parse_mode="Markdown")

async def minhapontuacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.from_user.first_name
    pontuacoes = carregar_pontuacoes()
    pontos = pontuacoes.get(nome, 0)
    await update.message.reply_text(f"👤 {nome}, você tem {pontos} pontos atualmente.")

async def estacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🌸 Estação atual: {obter_estacao()}")

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 *Comandos disponíveis:*\n\n"
        "/iniciar — Inicia o bot\n"
        "/entrar — Entra no ranking\n"
        "/ranking — Mostra o top 10\n"
        "/minhapontuacao — Mostra sua pontuação\n"
        "/estacao — Mostra a estação atual\n"
        "/ajuda — Exibe esta mensagem",
        parse_mode="Markdown"
    )

# === BOAS-VINDAS AUTOMÁTICAS ===
async def boas_vindas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    membro = update.my_chat_member
    if membro.new_chat_member.status == "member":
        chat = membro.chat
        await context.bot.send_message(
            chat.id,
            "👋 Olá, pessoal!\n\n"
            "Eu sou o *Quiz Bot*! 🎯\n"
            "Os quizzes serão enviados automaticamente a cada 45 minutos.\n"
            "Use /entrar para participar do ranking e competir com os amigos 🧠",
            parse_mode="Markdown"
        )

# === APLICAÇÃO PRINCIPAL ===
async def main():
    global estacao_atual
    estacao_atual = obter_estacao()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("iniciar", iniciar))
    app.add_handler(CommandHandler("entrar", entrar))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CommandHandler("minhapontuacao", minhapontuacao))
    app.add_handler(CommandHandler("estacao", estacao))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CallbackQueryHandler(responder, pattern="^responder"))
    app.add_handler(ChatMemberHandler(boas_vindas, ChatMemberHandler.MY_CHAT_MEMBER))

    scheduler = BackgroundScheduler()
    scheduler.add_job(resetar_temporada, "date", run_date="2025-12-01")
    scheduler.add_job(lambda: asyncio.run_coroutine_threadsafe(enviar_quiz(app), asyncio.get_event_loop()),
                      "interval", minutes=45)
    scheduler.start()

    print("🤖 Bot rodando com quizzes automáticos, ranking, estações e boas-vindas.")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

# === FLASK PARA RENDER ===
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Bot está ativo e rodando!"

def iniciar_bot():
    asyncio.run(main())

if __name__ == "__main__":
    t = threading.Thread(target=iniciar_bot)
    t.start()
    flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
