import os
import json
import random
import asyncio
import datetime
import pytz
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
)

# 🌎 Fuso horário
TIMEZONE = pytz.timezone("America/Sao_Paulo")

# ⚙️ Configurações principais
TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

QUIZ_INTERVALO = 45 * 60  # 45 minutos
PONTOS_POR_ACERTO = 35
ARQUIVO_PONTOS = "pontuacoes.json"
ARQUIVO_QUIZZES = "quizzes.json"

ultima_mensagem_id = None


# ===============================
# 🔹 FUNÇÕES DE SUPORTE
# ===============================

def carregar_pontuacoes():
    if not os.path.exists(ARQUIVO_PONTOS):
        return {}
    with open(ARQUIVO_PONTOS, "r") as f:
        return json.load(f)


def salvar_pontuacoes(pontuacoes):
    with open(ARQUIVO_PONTOS, "w") as f:
        json.dump(pontuacoes, f, indent=4)


def carregar_quizzes():
    if not os.path.exists(ARQUIVO_QUIZZES):
        with open(ARQUIVO_QUIZZES, "w") as f:
            json.dump([], f)
        return []
    with open(ARQUIVO_QUIZZES, "r") as f:
        return json.load(f)


def salvar_quizzes(quizzes):
    with open(ARQUIVO_QUIZZES, "w") as f:
        json.dump(quizzes, f, indent=4)


def escolher_quiz():
    quizzes = carregar_quizzes()
    return random.choice(quizzes) if quizzes else None


def adicionar_pontos(usuario_id, nome, pontos):
    pontuacoes = carregar_pontuacoes()
    if usuario_id not in pontuacoes:
        pontuacoes[usuario_id] = {"nome": nome, "pontos": 50}
    pontuacoes[usuario_id]["pontos"] += pontos
    salvar_pontuacoes(pontuacoes)


# ===============================
# 🔹 FUNÇÕES DO BOT
# ===============================

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "👋 Olá! Eu sou o bot de quizzes!\n"
        "Responda os quizzes, ganhe pontos e suba no ranking.\n\n"
        "📚 Use /ranking para ver o Top 10.\n"
        "⚙️ Use /addquiz (apenas admin) para adicionar novas perguntas.\n\n"
        "🕒 Novos quizzes a cada 45 minutos, entre 07h e 23h."
    )


async def add_quiz(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 Você não tem permissão para isso.")
        return
    try:
        texto = " ".join(context.args)
        pergunta, resposta = texto.split("|")
        quizzes = carregar_quizzes()
        quizzes.append({"pergunta": pergunta.strip(), "resposta": resposta.strip()})
        salvar_quizzes(quizzes)
        await update.message.reply_text("✅ Quiz adicionado com sucesso!")
    except Exception:
        await update.message.reply_text("⚠️ Use o formato: /addquiz pergunta | resposta")


async def responder(update: Update, context: CallbackContext):
    resposta = update.message.text.strip().lower()
    quizzes = carregar_quizzes()

    for quiz in quizzes:
        if resposta == quiz["resposta"].lower():
            adicionar_pontos(update.effective_user.id, update.effective_user.first_name, PONTOS_POR_ACERTO)
            await update.message.reply_text(f"✅ Acertou, {update.effective_user.first_name}! +{PONTOS_POR_ACERTO} pontos!")
            return

    await update.message.reply_text("❌ Errou! Tente novamente!")


async def enviar_quiz(context: CallbackContext):
    global ultima_mensagem_id
    agora = datetime.datetime.now(TIMEZONE)

    if not (7 <= agora.hour < 23):
        return

    quiz = escolher_quiz()
    if not quiz:
        print("❌ Nenhum quiz disponível.")
        return

    chat_id = context.job.chat_id or context.job.data.get("chat_id")

    try:
        if ultima_mensagem_id:
            await context.bot.delete_message(chat_id=chat_id, message_id=ultima_mensagem_id)
    except Exception:
        pass

    msg = await context.bot.send_message(chat_id=chat_id, text=f"🧩 Quiz:\n\n{quiz['pergunta']}")
    ultima_mensagem_id = msg.message_id


async def resetar_temporada(context: CallbackContext):
    pontuacoes = carregar_pontuacoes()
    if not pontuacoes:
        return

    top10 = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)[:10]
    msg = "🏁 *Fim da Temporada!*\n\n🏆 *Top 3 jogadores:*\n"

    for i, (uid, data) in enumerate(top10[:3], start=1):
        medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
        msg += f"{medalha} {data['nome']} — {data['pontos']} pontos\n"

    msg += "\n🎉 Parabéns a todos! A nova temporada começa agora!"
    await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode="Markdown")

    salvar_pontuacoes({})


async def ranking(update: Update, context: CallbackContext):
    pontuacoes = carregar_pontuacoes()
    if not pontuacoes:
        await update.message.reply_text("📊 Ainda não há pontuações registradas.")
        return

    top10 = sorted(pontuacoes.items(), key=lambda x: x[1]["pontos"], reverse=True)[:10]
    msg = "🏆 *Top 10 Jogadores da Temporada*\n\n"
    for i, (uid, data) in enumerate(top10, start=1):
        medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}️⃣"
        msg += f"{medalha} {data['nome']} — {data['pontos']} pts\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


# ===============================
# 🔹 MAIN (compatível com Render)
# ===============================

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addquiz", add_quiz))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    job_queue = app.job_queue
    job_queue.run_repeating(enviar_quiz, interval=QUIZ_INTERVALO, first=10, data={"chat_id": OWNER_ID})

    ano_atual = datetime.datetime.now().year
    for mes in [3, 6, 9, 12]:
        data_reset = datetime.datetime(ano_atual, mes, 1, 0, 0, tzinfo=TIMEZONE)
        job_queue.run_once(resetar_temporada, when=data_reset)

    print("🤖 Bot rodando normalmente com Python 3.13 no Render...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()  # mantém o bot rodando sem fechar o loop


if __name__ == "__main__":
    asyncio.run(main())
