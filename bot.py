import asyncio
import json
import random
from datetime import datetime, timedelta, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import os
import pytz

# === CONFIGURAÇÕES ===
TOKEN = os.getenv("BOT_TOKEN")
TIMEZONE = pytz.timezone("America/Sao_Paulo")
QUIZ_INTERVALO = 45 * 60  # 45 minutos
HORARIO_INICIO = 7
HORARIO_FIM = 23
PONTOS_ACERTO = 35
BONUS_DIARIO = 200
BONUS_SEMANAL = {1: 500, 2: 400, 3: 300, 4: 300}
PONTOS_INICIAIS = 50

# === ARQUIVOS ===
QUIZ_FILE = "quizzes.json"
PONTOS_FILE = "pontuacoes.json"
CHATS_FILE = "chats_ativos.json"

# === FUNÇÕES DE DADOS ===
def carregar_dados(arquivo, padrao):
    if os.path.exists(arquivo):
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    return padrao

def salvar_dados(arquivo, dados):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

# === CARREGAMENTO INICIAL ===
quizzes = carregar_dados(QUIZ_FILE, [])
pontuacoes = carregar_dados(PONTOS_FILE, {})
chats_ativos = carregar_dados(CHATS_FILE, [])

# === QUIZ AUTOMÁTICO ===
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
            print(f"Erro ao enviar quiz para {chat_id}: {e}")

async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    resposta_correta, resposta_usuario = query.data.split("|")
    user_id = str(query.from_user.id)
    nome = query.from_user.first_name

    if resposta_usuario == resposta_correta:
        pontos = pontuacoes.get(user_id, {}).get("pontos", PONTOS_INICIAIS)
        pontos += PONTOS_ACERTO
        pontuacoes[user_id] = {"nome": nome, "pontos": pontos}
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

# === SISTEMA DE BÔNUS ===
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

# === RESET DE TEMPORADA ===
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

# === /ADDQUIZ ===
PERGUNTA, OPCOES, RESPOSTA = range(3)

async def addquiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✏️ Envie a *pergunta* do novo quiz:")
    return PERGUNTA

async def addquiz_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"] = update.message.text
    await update.message.reply_text("Agora envie as *opções de resposta*, separadas por vírgula (ex: A,B,C,D):")
    return OPCOES

async def addquiz_opcoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    opcoes = [x.strip() for x in update.message.text.split(",") if x.strip()]
    context.user_data["opts"] = opcoes
    await update.message.reply_text(f"Qual é a *resposta correta*?\nEscolha uma das opções: {', '.join(opcoes)}")
    return RESPOSTA

async def addquiz_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = update.message.text.strip()
    if ans not in context.user_data["opts"]:
        await update.message.reply_text("❌ Resposta inválida. Deve ser uma das opções enviadas.")
        return RESPOSTA

    quiz = {
        "q": context.user_data["q"],
        "opts": context.user_data["opts"],
        "ans": ans
    }
    quizzes.append(quiz)
    salvar_dados(QUIZ_FILE, quizzes)
    await update.message.reply_text("✅ Novo quiz adicionado com sucesso!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Criação de quiz cancelada.")
    return ConversationHandler.END

# === MAIN ===
async def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Handlers principais
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CallbackQueryHandler(resposta_quiz))

    # /addquiz handler (modo conversa)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addquiz", addquiz_start)],
        states={
            PERGUNTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, addquiz_pergunta)],
            OPCOES: [MessageHandler(filters.TEXT & ~filters.COMMAND, addquiz_opcoes)],
            RESPOSTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, addquiz_resposta)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)

    # Jobs automáticos
    app.job_queue.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO, first=10)
    app.job_queue.run_daily(aplicar_bonus_diario, time=time(hour=22, tzinfo=TIMEZONE))
    app.job_queue.run_daily(aplicar_bonus_semanal, time=time(hour=23, tzinfo=TIMEZONE), days=(6,))
    app.job_queue.run_monthly(
        resetar_temporada,
        when=time(hour=23, tzinfo=TIMEZONE),
        day=1,
        months=3
    )

    print("🤖 Bot rodando com sistema de quizzes, bônus e /addquiz ativo.")
    await app.run_polling(close_loop=False)

if __name__ == "__main__":
    asyncio.run(main())
