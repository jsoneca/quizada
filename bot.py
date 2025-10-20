import asyncio
import random
from datetime import datetime, time, timedelta
import pytz
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ChatMemberHandler,
    filters,
)

# === CONFIGURAÇÕES ===
TOKEN = "SEU_TOKEN_AQUI"

TIMEZONE = pytz.timezone("America/Sao_Paulo")
QUIZ_INTERVALO = 45 * 60  # 45 minutos em segundos
HORARIO_INICIO = 7
HORARIO_FIM = 23
PONTOS_ACERTO = 35
PONTOS_INICIAIS = 50

# IDs de administradores autorizados a usar /addquiz
ADMIN_IDS = [
    8126443922,  # coloque aqui seu ID do Telegram
]

# === DADOS TEMPORÁRIOS ===
quizzes = [
    {"q": "Qual é a capital da França?", "opts": ["Paris", "Roma", "Londres"], "ans": "Paris"},
]
pontuacoes = {}
chats_ativos = set()

# === ESTADOS DA CONVERSA /addquiz ===
PERGUNTA, OPCOES, RESPOSTA = range(3)


# === BOAS-VINDAS ===
async def boas_vindas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    novo_membro = update.chat_member.new_chat_member
    if novo_membro.status == "member":
        await update.effective_chat.send_message(
            f"👋 Bem-vindo, {novo_membro.user.first_name}! Prepare-se para participar dos quizzes! 🎯\n"
            "Use /ranking para ver sua posição e /top10 para ver os melhores da temporada!"
        )


# === COMANDOS BÁSICOS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chats_ativos.add(update.effective_chat.id)
    if user.id not in pontuacoes:
        pontuacoes[user.id] = {"pontos": PONTOS_INICIAIS, "nivel": 1}
    await update.message.reply_text(
        f"🎯 Olá {user.first_name}! Bem-vindo ao QuizBot!\n"
        "Os quizzes são enviados automaticamente das 7h às 23h a cada 45 minutos."
    )


async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        await update.message.reply_text("🏆 Ainda não há pontuações registradas.")
        return

    texto = "📊 *Ranking Atual:*\n\n"
    for user_id, dados in sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True):
        texto += f"👤 {user_id} — {dados['pontos']} pontos (Nível {dados['nivel']})\n"
    await update.message.reply_text(texto, parse_mode="Markdown")


async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not pontuacoes:
        await update.message.reply_text("🏆 Ainda não há jogadores no ranking.")
        return

    texto = "🏅 *Top 10 Jogadores da Temporada:*\n\n"
    top = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)[:10]
    for i, (user_id, dados) in enumerate(top, start=1):
        medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}️⃣"
        texto += f"{medalha} {user_id} — {dados['pontos']} pts\n"
    await update.message.reply_text(texto, parse_mode="Markdown")


# === SISTEMA DE QUIZ AUTOMÁTICO ===
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

    if not hasattr(context.bot_data, "ultimos_quizzes"):
        context.bot_data["ultimos_quizzes"] = {}

    for chat_id in chats_ativos:
        try:
            # Se houver um quiz anterior, exibe aviso e apaga
            ultimo_id = context.bot_data["ultimos_quizzes"].get(chat_id)
            if ultimo_id:
                try:
                    await context.bot.send_message(chat_id, "⏳ Este quiz expirou!")
                    await asyncio.sleep(3)
                    await context.bot.delete_message(chat_id=chat_id, message_id=ultimo_id)
                except Exception as e:
                    print(f"⚠️ Erro ao apagar quiz anterior: {e}")

            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🧠 *{quiz['q']}*",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            context.bot_data["ultimos_quizzes"][chat_id] = msg.message_id

        except Exception as e:
            print(f"Erro ao enviar quiz: {e}")


# === RESPOSTAS ===
async def resposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    correta, resposta = query.data.split("|")

    user = query.from_user
    if user.id not in pontuacoes:
        pontuacoes[user.id] = {"pontos": PONTOS_INICIAIS, "nivel": 1}

    if resposta == correta:
        pontuacoes[user.id]["pontos"] += PONTOS_ACERTO
        await query.edit_message_text(f"✅ Correto, {user.first_name}! +{PONTOS_ACERTO} pontos.")
    else:
        await query.edit_message_text(f"❌ Errou, {user.first_name}! A resposta era: {correta}")

    # Atualiza nível
    pontuacoes[user.id]["nivel"] = pontuacoes[user.id]["pontos"] // 100 + 1


# === BÔNUS ===
async def aplicar_bonus_diario(context: ContextTypes.DEFAULT_TYPE):
    if pontuacoes:
        top_user = max(pontuacoes, key=lambda k: pontuacoes[k]["pontos"])
        pontuacoes[top_user]["pontos"] += 200
        print(f"🎁 Bônus diário aplicado a {top_user}!")


async def aplicar_bonus_semanal(context: ContextTypes.DEFAULT_TYPE):
    if pontuacoes:
        top = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)[:4]
        bonus = [500, 400, 300, 300]
        for (user_id, _), pontos in zip(top, bonus):
            pontuacoes[user_id]["pontos"] += pontos
        print("🏅 Bônus semanal aplicado!")


async def resetar_temporada(context: ContextTypes.DEFAULT_TYPE):
    if pontuacoes:
        top = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)[:10]
        print("🌱 Nova temporada! Top 3:")
        for i, (user_id, dados) in enumerate(top[:3], start=1):
            print(f"{i}º - {user_id} ({dados['pontos']} pts)")
    pontuacoes.clear()


# === ADDQUIZ (somente admins) ===
async def addquiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🚫 Você não tem permissão para adicionar quizzes.")
        return ConversationHandler.END

    await update.message.reply_text("✏️ Envie a *pergunta* do novo quiz:")
    return PERGUNTA


async def addquiz_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pergunta"] = update.message.text
    await update.message.reply_text("📋 Agora envie as *opções*, separadas por vírgula (,):")
    return OPCOES


async def addquiz_opcoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["opcoes"] = [x.strip() for x in update.message.text.split(",")]
    await update.message.reply_text("✅ Qual é a *resposta correta*?")
    return RESPOSTA


async def addquiz_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pergunta = context.user_data["pergunta"]
    opcoes = context.user_data["opcoes"]
    resposta = update.message.text.strip()
    quizzes.append({"q": pergunta, "opts": opcoes, "ans": resposta})
    await update.message.reply_text("🎉 Quiz adicionado com sucesso!")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ A criação do quiz foi cancelada.")
    return ConversationHandler.END


# === MAIN ===
async def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CommandHandler("top10", top10))
    app.add_handler(CallbackQueryHandler(resposta_quiz))

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
    app.add_handler(ChatMemberHandler(boas_vindas, ChatMemberHandler.CHAT_MEMBER))

    # Jobs automáticos
    app.job_queue.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO, first=10)
    app.job_queue.run_daily(aplicar_bonus_diario, time=time(hour=22, tzinfo=TIMEZONE))
    app.job_queue.run_daily(aplicar_bonus_semanal, time=time(hour=23, tzinfo=TIMEZONE), days=(6,))

    async def verificar_reset_temporada(context: ContextTypes.DEFAULT_TYPE):
        mes_atual = datetime.now(TIMEZONE).month
        if mes_atual in [3, 6, 9, 12]:
            await resetar_temporada(context)

    app.job_queue.run_daily(
        verificar_reset_temporada,
        time=time(hour=23, tzinfo=TIMEZONE),
        days=(1,),
    )

    print("🤖 Bot rodando com quiz, bônus, boas-vindas e /addquiz protegido.")
    await app.run_polling()


if __name__ == "__main__":
    import sys
    import asyncio

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

