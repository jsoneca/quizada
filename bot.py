import os
import asyncio
import json
import random
import datetime
from collections import defaultdict
from pytz import timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# ===================== CONFIGURAÇÕES =====================

TOKEN = os.getenv("TELEGRAM_TOKEN")  # obtido do ambiente do Render
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))  # seu ID pessoal
CHAT_ID_PRINCIPAL = int(os.getenv("CHAT_ID_PRINCIPAL", "-1000000000000"))  # ID do grupo do bot

TIMEZONE = timezone("America/Sao_Paulo")

QUIZ_FILE = "quizzes.json"
SCORES_FILE = "pontuacoes.json"

QUIZ_INTERVALO_MINUTOS = 45
HORARIO_INICIO = 7
HORARIO_FIM = 23

PONTOS_ACERTO = 35
PONTOS_INICIAL = 50

BONUS_SEMANAL = {1: 500, 2: 400, 3: 300, 4: 300}

# ===================== ARMAZENAMENTO =====================

pontuacoes = defaultdict(int)
interacoes_diarias = defaultdict(int)
mensagem_anterior = {}  # guarda ID da última mensagem do quiz enviada


def carregar_dados():
    """Carrega pontuações salvas"""
    global pontuacoes
    try:
        with open(SCORES_FILE, "r") as f:
            pontuacoes.update(json.load(f))
    except FileNotFoundError:
        pass


def salvar_dados():
    """Salva pontuações"""
    with open(SCORES_FILE, "w") as f:
        json.dump(pontuacoes, f)


def carregar_quizzes():
    """Carrega lista de quizzes"""
    try:
        with open(QUIZ_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def salvar_quizzes(quizzes):
    """Salva novos quizzes"""
    with open(QUIZ_FILE, "w") as f:
        json.dump(quizzes, f)


# ===================== FUNÇÕES DO QUIZ =====================

async def enviar_quiz(context: ContextTypes.DEFAULT_TYPE):
    """Envia quiz a cada intervalo"""
    now = datetime.datetime.now(TIMEZONE)
    if not (HORARIO_INICIO <= now.hour < HORARIO_FIM):
        return

    quizzes = carregar_quizzes()
    if not quizzes:
        return

    quiz = random.choice(quizzes)
    chat_id = context.job.chat_id
    keyboard = [
        [InlineKeyboardButton(opt, callback_data=f"{quiz['id']}|{i}")]
        for i, opt in enumerate(quiz['opcoes'])
    ]

    # Apagar quiz anterior para manter o chat limpo
    if chat_id in mensagem_anterior:
        try:
            await context.bot.delete_message(chat_id, mensagem_anterior[chat_id])
        except Exception:
            pass

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🧠 *{quiz['pergunta']}*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    mensagem_anterior[chat_id] = msg.message_id


async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa respostas dos usuários"""
    query = update.callback_query
    await query.answer()

    quiz_id, opcao_idx = query.data.split("|")
    quizzes = carregar_quizzes()
    quiz = next((q for q in quizzes if q["id"] == quiz_id), None)

    if not quiz:
        await query.edit_message_text("❌ Quiz expirado.")
        return

    usuario = query.from_user
    correto = int(opcao_idx) == quiz["correta"]

    if correto:
        pontuacoes[str(usuario.id)] = pontuacoes.get(str(usuario.id), PONTOS_INICIAL) + PONTOS_ACERTO
        interacoes_diarias[str(usuario.id)] = interacoes_diarias.get(str(usuario.id), 0) + 1
        texto = f"✅ *Correto!* +{PONTOS_ACERTO} pontos!\nTotal: {pontuacoes[str(usuario.id)]}"
    else:
        texto = f"❌ *Errado!* A resposta certa era: {quiz['opcoes'][quiz['correta']]}"

    salvar_dados()
    await query.edit_message_text(texto, parse_mode="Markdown")


# ===================== BÔNUS E RESET =====================

async def aplicar_bonus_diario(context: ContextTypes.DEFAULT_TYPE):
    """Dá bônus diário para o mais ativo"""
    if not interacoes_diarias:
        return

    mais_ativo = max(interacoes_diarias, key=interacoes_diarias.get)
    pontuacoes[mais_ativo] += 200
    salvar_dados()
    interacoes_diarias.clear()

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"🏆 Bônus diário de 200 pontos para o usuário `{mais_ativo}`!",
        parse_mode="Markdown"
    )


async def aplicar_bonus_semanal(context: ContextTypes.DEFAULT_TYPE):
    """Bônus semanal para top 4"""
    if not pontuacoes:
        return

    ranking = sorted(pontuacoes.items(), key=lambda x: x[1], reverse=True)[:4]
    texto = "🏅 *Top 4 da Semana:*\n"

    for pos, (uid, pts) in enumerate(ranking, start=1):
        bonus = BONUS_SEMANAL[pos]
        pontuacoes[uid] += bonus
        texto += f"{pos}º — `{uid}` +{bonus} pontos (Total: {pontuacoes[uid]})\n"

    salvar_dados()
    await context.bot.send_message(context.job.chat_id, texto, parse_mode="Markdown")


async def resetar_temporada(context: ContextTypes.DEFAULT_TYPE):
    """Reseta pontuação a cada estação"""
    if not pontuacoes:
        return

    ranking = sorted(pontuacoes.items(), key=lambda x: x[1], reverse=True)[:10]
    texto = "🌸 *Fim da Temporada!*\n🏆 *Top 10:* \n\n"
    for i, (uid, pts) in enumerate(ranking, start=1):
        if i <= 3:
            texto += f"🥇" if i == 1 else ("🥈" if i == 2 else "🥉")
        texto += f" {i}º — `{uid}`: {pts} pontos\n"

    pontuacoes.clear()
    salvar_dados()

    await context.bot.send_message(context.job.chat_id, texto, parse_mode="Markdown")


# ===================== COMANDOS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensagem de boas-vindas"""
    await update.message.reply_text("👋 Olá! Eu sou o bot de quizzes. Prepare-se para aprender e ganhar pontos!")


async def add_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona novos quizzes (somente admin)"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 Você não tem permissão para adicionar quizzes.")
        return

    try:
        pergunta = context.args[0]
        opcoes = context.args[1:5]
        correta = int(context.args[5])
        quizzes = carregar_quizzes()
        quizzes.append({
            "id": str(len(quizzes) + 1),
            "pergunta": pergunta,
            "opcoes": opcoes,
            "correta": correta
        })
        salvar_quizzes(quizzes)
        await update.message.reply_text("✅ Quiz adicionado com sucesso!")
    except Exception:
        await update.message.reply_text("❗ Uso: /addquiz <pergunta> <op1> <op2> <op3> <op4> <num_correta>")


# ===================== INICIALIZAÇÃO =====================

async def main():
    carregar_dados()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addquiz", add_quiz))
    app.add_handler(CallbackQueryHandler(resposta_quiz))

    # Agendamentos
    app.job_queue.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO_MINUTOS * 60, first=10, chat_id=CHAT_ID_PRINCIPAL)
    app.job_queue.run_daily(aplicar_bonus_diario, time=datetime.time(22, 0, tzinfo=TIMEZONE), chat_id=CHAT_ID_PRINCIPAL)
    app.job_queue.run_repeating(aplicar_bonus_semanal, interval=7 * 24 * 3600, first=30, chat_id=CHAT_ID_PRINCIPAL)
    app.job_queue.run_repeating(resetar_temporada, interval=90 * 24 * 3600, first=60, chat_id=CHAT_ID_PRINCIPAL)

    print("🤖 Bot rodando com quiz, bônus, boas-vindas e /addquiz protegido.")
    await app.run_polling()


# ===================== EXECUÇÃO SEGURA PARA RENDER =====================

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(main())
        else:
            loop.run_until_complete(main())
    except RuntimeError:
        asyncio.run(main())
