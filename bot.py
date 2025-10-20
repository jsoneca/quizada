import asyncio
import json
import random
from datetime import datetime, timedelta, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)
import os
import pytz

# === CONFIGURAÇÕES ===
TOKEN = os.getenv("BOT_TOKEN")  # Definido no Render
TIMEZONE = pytz.timezone("America/Sao_Paulo")
QUIZ_INTERVALO = 45 * 60  # 45 minutos
HORARIO_INICIO = 7
HORARIO_FIM = 23
PONTOS_ACERTO = 35
BONUS_DIARIO = 200
BONUS_SEMANAL = {1: 500, 2: 400, 3: 300, 4: 300}
PONTOS_INICIAIS = 50

# === BASE DE DADOS ===
PONTOS_FILE = "pontuacoes.json"
QUIZ_FILE = "quizzes.json"
CHATS_FILE = "chats_ativos.json"

# === CARREGAR QUIZZES ===
try:
    with open(QUIZ_FILE, "r", encoding="utf-8") as f:
        quizzes = json.load(f)
except FileNotFoundError:
    quizzes = []
    print("⚠️ Nenhum quiz encontrado. Adicione quizzes.json.")

# === FUNÇÕES AUXILIARES ===
def carregar_dados(arquivo, padrao):
    if os.path.exists(arquivo):
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    return padrao

def salvar_dados(arquivo, dados):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

pontuacoes = carregar_dados(PONTOS_FILE, {})
chats_ativos = carregar_dados(CHATS_FILE, [])

# === SISTEMA DE QUIZ ===
async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(TIMEZONE)
    if not (HORARIO_INICIO <= agora.hour < HORARIO_FIM):
        return

    if not quizzes:
        return

    quiz = random.choice(quizzes)
    keyboard = [
        [InlineKeyboardButton(opcao, callback_data=f"{quiz['ans']}|{opcao}")]
        for opcao in quiz["opts"]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    for chat_id in chats_ativos:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🧠 *{quiz['q']}*",
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"❌ Falha ao enviar quiz para {chat_id}: {e}")

async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    resposta_correta, resposta_usuario = query.data.split("|")
    user_id = str(query.from_user.id)
    nome = query.from_user.first_name

    if resposta_usuario == resposta_correta:
        pontos_atuais = pontuacoes.get(user_id, {}).get("pontos", PONTOS_INICIAIS)
        pontos_atuais += PONTOS_ACERTO
        pontuacoes[user_id] = {"nome": nome, "pontos": pontos_atuais}
        salvar_dados(PONTOS_FILE, pontuacoes)
        await query.edit_message_text(f"✅ Correto, {nome}! Você ganhou {PONTOS_ACERTO} pontos.")
    else:
        await query.edit_message_text(
            f"❌ Errado, {nome}! A resposta certa era *{resposta_correta}*.",
            parse_mode="Markdown"
        )

# === COMANDOS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in chats_ativos:
        chats_ativos.append(chat_id)
        salvar_dados(CHATS_FILE, chats_ativos)
    await update.message.reply_text(
        "🤖 Olá! Você está participando do *QuizBot!* 🎯\n"
        "A cada 45 minutos tem um novo quiz!\n"
        "Use /ranking para ver o placar atual.",
        parse_mode="Markdown"
    )

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        await update.message.reply_text("📊 Nenhum jogador ainda.")
        return

    ranking = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)
    msg = "🏆 *Ranking Atual:*\n\n"
    for i, (user_id, dados) in enumerate(ranking[:10], start=1):
        medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        msg += f"{medalha} {dados['nome']} — {dados['pontos']} pts\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# === BÔNUS E TEMPORADAS ===
async def aplicar_bonus_diario(context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        return
    user = max(pontuacoes.items(), key=lambda x: x[1]["pontos"])
    pontuacoes[user[0]]["pontos"] += BONUS_DIARIO
    salvar_dados(PONTOS_FILE, pontuacoes)
    print(f"🌞 Bônus diário de {BONUS_DIARIO} pontos para {user[1]['nome']}.")

async def aplicar_bonus_semanal(context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        return
    ranking = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)[:4]
    for pos, (uid, dados) in enumerate(ranking, start=1):
        bonus = BONUS_SEMANAL.get(pos, 0)
        pontuacoes[uid]["pontos"] += bonus
        print(f"🏅 {dados['nome']} recebeu bônus semanal de {bonus} pontos.")
    salvar_dados(PONTOS_FILE, pontuacoes)

async def resetar_temporada(context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        return
    ranking = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)
    print("🍂 Reset de temporada — Top 10:")
    for i, (uid, dados) in enumerate(ranking[:10], start=1):
        destaque = "⭐" if i <= 3 else ""
        print(f"{destaque}{i}. {dados['nome']} — {dados['pontos']} pts")
    pontuacoes.clear()
    salvar_dados(PONTOS_FILE, pontuacoes)

# === MAIN ===
async def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CallbackQueryHandler(resposta_quiz))

    # Jobs automáticos
    app.job_queue.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO, first=10)
    app.job_queue.run_daily(aplicar_bonus_diario, time=time(hour=22, tzinfo=TIMEZONE))
    app.job_queue.run_daily(aplicar_bonus_semanal, time=time(hour=23, tzinfo=TIMEZONE), days=(6,))
    
    # Reset a cada estação (1º de março, junho, setembro, dezembro)
    meses_reset = [3, 6, 9, 12]
    for mes in meses_reset:
        app.job_queue.run_monthly(
            resetar_temporada,
            when=time(hour=23, tzinfo=TIMEZONE),
            day=1,
            month=mes
        )

    print("🤖 Bot rodando com sistema de quizzes, bônus e temporadas.")
    await app.run_polling(close_loop=False)

if __name__ == "__main__":
    asyncio.run(main())
