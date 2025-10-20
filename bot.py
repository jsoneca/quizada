import os
import json
import random
import asyncio
import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ==============================
# CONFIGURAÇÕES GERAIS
# ==============================
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))
TIMEZONE = pytz.timezone("America/Sao_Paulo")
QUIZ_INTERVALO = 45 * 60  # 45 minutos
ARQUIVO_PONTOS = "pontuacoes.json"
ARQUIVO_QUIZZES = "quizzes.json"
ULTIMO_QUIZ_MSG = {}

# ==============================
# FUNÇÕES DE ARQUIVOS
# ==============================
def carregar_dados(arquivo):
    if not os.path.exists(arquivo):
        return {}
    with open(arquivo, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_dados(arquivo, dados):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

pontuacoes = carregar_dados(ARQUIVO_PONTOS)
quizzes = carregar_dados(ARQUIVO_QUIZZES)

# ==============================
# FUNÇÕES DE QUIZ
# ==============================
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.datetime.now(TIMEZONE)
    if not (7 <= agora.hour < 23):
        return

    if not quizzes:
        return

    chat_id = context.job.chat_id
    quiz = random.choice(list(quizzes.values()))
    pergunta = quiz["pergunta"]
    opcoes = quiz["opcoes"]
    correta = quiz["correta"]

    # Apaga o quiz anterior
    if chat_id in ULTIMO_QUIZ_MSG:
        try:
            await context.bot.delete_message(chat_id, ULTIMO_QUIZ_MSG[chat_id])
        except Exception:
            pass

    botoes = [
        [InlineKeyboardButton(text=op, callback_data=f"quiz|{correta}|{op}")]
        for op in opcoes
    ]
    msg = await context.bot.send_message(
        chat_id,
        f"🧠 *Quiz Rápido!*\n\n{pergunta}",
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown"
    )
    ULTIMO_QUIZ_MSG[chat_id] = msg.message_id

async def responder_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, correta, resposta = query.data.split("|")
    user = query.from_user
    user_id = str(user.id)

    if user_id not in pontuacoes:
        pontuacoes[user_id] = {"nome": user.first_name, "pontos": 50, "nivel": 1}

    if resposta == correta:
        pontuacoes[user_id]["pontos"] += 35
        await query.answer("✅ Correto! +35 pontos!")
    else:
        await query.answer(f"❌ Errado! Resposta certa: {correta}")

    pontos = pontuacoes[user_id]["pontos"]
    pontuacoes[user_id]["nivel"] = pontos // 200 + 1
    salvar_dados(ARQUIVO_PONTOS, pontuacoes)

# ==============================
# COMANDOS
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Eu sou o Bot de Quiz!\n\n"
        "🧩 Enviarei quizzes automáticos a cada 45 minutos (entre 7h e 23h).\n"
        "🏆 Ganhe pontos, suba de nível e veja seu nome no ranking semanal e das estações!"
    )

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking_ordenado = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)
    texto = "🏅 *Top 10 Jogadores:*\n\n"
    for i, (uid, info) in enumerate(ranking_ordenado[:10], 1):
        estrela = "⭐" if i <= 3 else ""
        texto += f"{i}. {info['nome']} — {info['pontos']} pts {estrela}\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

async def addquiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 Você não tem permissão para adicionar quizzes.")
        return

    try:
        partes = " ".join(context.args).split("|")
        pergunta = partes[0].strip()
        opcoes = [p.strip() for p in partes[1:5]]
        correta = partes[5].strip()
        quizzes[pergunta] = {"pergunta": pergunta, "opcoes": opcoes, "correta": correta}
        salvar_dados(ARQUIVO_QUIZZES, quizzes)
        await update.message.reply_text("✅ Quiz adicionado com sucesso!")
    except Exception:
        await update.message.reply_text("❌ Formato inválido. Use:\n/addquiz Pergunta | Op1 | Op2 | Op3 | Op4 | Correta")

# ==============================
# BONIFICAÇÕES
# ==============================
async def aplicar_bonus_diario(context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        return
    mais_ativo = max(pontuacoes.items(), key=lambda x: x[1]["pontos"])
    pontuacoes[mais_ativo[0]]["pontos"] += 200
    salvar_dados(ARQUIVO_PONTOS, pontuacoes)
    await context.bot.send_message(
        context.job.chat_id,
        f"🎁 Bônus diário para {mais_ativo[1]['nome']}! +200 pontos!"
    )

async def aplicar_bonus_semanal(context: ContextTypes.DEFAULT_TYPE):
    ranking_ordenado = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)
    bonus = [500, 400, 300, 300]
    texto = "🏆 *Bônus Semanal!*\n\n"
    for i, (uid, info) in enumerate(ranking_ordenado[:4]):
        pontuacoes[uid]["pontos"] += bonus[i]
        texto += f"{i+1}. {info['nome']} +{bonus[i]} pts\n"
    salvar_dados(ARQUIVO_PONTOS, pontuacoes)
    await context.bot.send_message(context.job.chat_id, texto, parse_mode="Markdown")

# ==============================
# ESTAÇÕES / TEMPORADAS
# ==============================
async def resetar_temporada(context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        return
    ranking_ordenado = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)
    texto = "🍂 *Fim da Temporada!*\n\n🏅 *Top 10 da Estação:*\n"
    for i, (uid, info) in enumerate(ranking_ordenado[:10], 1):
        estrela = "🌟" if i <= 3 else ""
        texto += f"{i}. {info['nome']} — {info['pontos']} pts {estrela}\n"

    await context.bot.send_message(context.job.chat_id, texto, parse_mode="Markdown")

    for p in pontuacoes.values():
        p["pontos"] = 50
        p["nivel"] = 1
    salvar_dados(ARQUIVO_PONTOS, pontuacoes)

# ==============================
# MAIN
# ==============================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CommandHandler("addquiz", addquiz))
    app.add_handler(CallbackQueryHandler(responder_quiz, pattern="^quiz"))

    job_queue = app.job_queue
    job_queue.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO, first=10)
    job_queue.run_daily(aplicar_bonus_diario, time=datetime.time(hour=22, tzinfo=TIMEZONE))
    job_queue.run_daily(aplicar_bonus_semanal, time=datetime.time(hour=23, tzinfo=TIMEZONE), days=(6,))

    meses_estacoes = [1, 4, 7, 10]
    hoje = datetime.datetime.now(TIMEZONE)
    proxima_estacao = min((m for m in meses_estacoes if m > hoje.month), default=1)
    ano = hoje.year if proxima_estacao > hoje.month else hoje.year + 1
    data_reset = datetime.datetime(ano, proxima_estacao, 1, 0, 0, tzinfo=TIMEZONE)
    job_queue.run_once(resetar_temporada, when=(data_reset - hoje))

    print("🤖 Bot rodando com quiz, bônus, estações e limpeza automática.")
    await app.run_polling()

# ==============================
# LOOP SIMPLIFICADO (SEM CONFLITOS)
# ==============================
if __name__ == "__main__":
    asyncio.run(main())
