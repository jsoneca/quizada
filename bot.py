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

TOKEN = os.getenv("BOT_TOKEN")  # obtido do ambiente do Render
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))  # seu ID do Telegram

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
mensagem_anterior = {}
chats_ativos = set()  # grupos ou usuários onde o bot foi ativado


def carregar_dados():
    """Carrega pontuações"""
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

async def enviar_quiz_para_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Envia quiz a um chat específico"""
    now = datetime.datetime.now(TIMEZONE)
    if not (HORARIO_INICIO <= now.hour < HORARIO_FIM):
        return

    quizzes = carregar_quizzes()
    if not quizzes:
        return

    quiz = random.choice(quizzes)
    keyboard = [
        [InlineKeyboardButton(opt, callback_data=f"{quiz['id']}|{i}")]
        for i, opt in enumerate(quiz['opcoes'])
    ]

    # Apagar quiz anterior
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


async def enviar_quizzes(context: ContextTypes.DEFAULT_TYPE):
    """Envia quiz para todos os chats ativos"""
    for chat_id in chats_ativos:
        await enviar_quiz_para_chat(context, chat_id)


async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa respostas"""
    query = update.callback_query
    await query.answer()

    quiz_id, opcao_idx = query.data.split("|")
    quizzes = carregar_quizzes()
    quiz = next((q for q in quizzes if q["id"] == quiz_id), None)

    if not quiz:
        await query.edit_message_text("❌ Quiz expirado.")
        return

    user = query.from_user
    correto = int(opcao_idx) == quiz["correta"]

    if correto:
        pontuacoes[str(user.id)] += PONTOS_ACERTO
        interacoes_diarias[str(user.id)] += 1
        texto = f"✅ *Correto!* +{PONTOS_ACERTO} pontos!\nTotal: {pontuacoes[str(user.id)]}"
    else:
        texto = f"❌ *Errado!* A resposta certa era: {quiz['opcoes'][quiz['correta']]}"

    salvar_dados()
    await query.edit_message_text(texto, parse_mode="Markdown")


# ===================== BÔNUS E RESET =====================

async def aplicar_bonus_diario(context: ContextTypes.DEFAULT_TYPE):
    """Bônus diário para o mais ativo"""
    if not interacoes_diarias:
        return
    mais_ativo = max(interacoes_diarias, key=interacoes_diarias.get)
    pontuacoes[mais_ativo] += 200
    salvar_dados()
    interacoes_diarias.clear()
    for chat_id in chats_ativos:
        await context.bot.send_message(chat_id, f"🏆 Bônus diário de 200 pontos para `{mais_ativo}`!", parse_mode="Markdown")


async def aplicar_bonus_semanal(context: ContextTypes.DEFAULT_TYPE):
    """Bônus semanal"""
    if not pontuacoes:
        return
    ranking = sorted(pontuacoes.items(), key=lambda x: x[1], reverse=True)[:4]
    texto = "🏅 *Top 4 da Semana:*\n"
    for pos, (uid, pts) in enumerate(ranking, start=1):
        bonus = BONUS_SEMANAL[pos]
        pontuacoes[uid] += bonus
        texto += f"{pos}º — `{uid}` +{bonus} pontos (Total: {pontuacoes[uid]})\n"
    salvar_dados()
    for chat_id in chats_ativos:
        await context.bot.send_message(chat_id, texto, parse_mode="Markdown")


# ===================== COMANDOS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ativa quizzes no chat"""
    chat_id = update.effective_chat.id
    chats_ativos.add(chat_id)
    await update.message.reply_text("👋 Bot de quiz ativado neste chat! Vou enviar quizzes automaticamente.")


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia quiz manualmente"""
    chat_id = update.effective_chat.id
    await enviar_quiz_para_chat(context, chat_id)


async def add_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona quizzes (somente OWNER)"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 Você não tem permissão para isso.")
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
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("addquiz", add_quiz))
    app.add_handler(CallbackQueryHandler(resposta_quiz))

    # Tarefas agendadas
    app.job_queue.run_repeating(enviar_quizzes, interval=QUIZ_INTERVALO_MINUTOS * 60, first=10)
    app.job_queue.run_daily(aplicar_bonus_diario, time=datetime.time(22, 0, tzinfo=TIMEZONE))
    app.job_queue.run_repeating(aplicar_bonus_semanal, interval=7 * 24 * 3600, first=30)

    print("🤖 Bot rodando com quiz automático, bônus e /addquiz protegido.")
    await app.run_polling()


# ===================== EXECUÇÃO SEGURA =====================

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
