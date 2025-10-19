import asyncio
import json
import random
from datetime import datetime, timedelta
from telegram import Poll
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    PollAnswerHandler,
)

TOKEN = "SEU_TOKEN_AQUI"

# ------------------- BANCO DE DADOS -------------------
USUARIOS_FILE = "usuarios.json"
QUIZZES_FILE = "quizzes.json"

def carregar_json(caminho):
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

usuarios = carregar_json(USUARIOS_FILE)
quizzes = carregar_json(QUIZZES_FILE)

# ------------------- FUNÇÕES DO JOGO -------------------
def get_user(user_id):
    if str(user_id) not in usuarios:
        usuarios[str(user_id)] = {"pontos": 50, "nivel": 1, "acertos": 0}
        salvar_json(USUARIOS_FILE, usuarios)
    return usuarios[str(user_id)]

def atualizar_pontos(user_id, acertou):
    user = get_user(user_id)
    if acertou:
        user["pontos"] += 35
        user["acertos"] += 1
    if user["acertos"] % 5 == 0 and user["acertos"] > 0:
        user["nivel"] += 1
    salvar_json(USUARIOS_FILE, usuarios)

async def start(update, context):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(
        f"🎯 Bem-vindo(a) ao Quiz Bot!\n\n"
        f"Você começa com {user['pontos']} pontos.\n"
        f"Seu nível atual: {user['nivel']}.\n\n"
        f"Fique ligado — novos quizzes são postados automaticamente!"
    )

# ------------------- LOOP DE QUIZZES -------------------
async def enviar_quiz(app):
    if not quizzes:
        print("⚠️ Nenhum quiz encontrado em quizzes.json")
        return

    now = datetime.now().time()
    if not (7 <= now.hour < 23):
        print("⏸ Fora do horário (7h–23h), não enviando quiz.")
        return

    quiz = random.choice(list(quizzes.values()))
    pergunta = quiz["pergunta"]
    opcoes = quiz["opcoes"]
    resposta = quiz["resposta"]

    # Envia em formato de quiz (com resposta certa)
    chat_id = "SEU_CHAT_ID_AQUI"  # pode ser grupo ou canal
    message = await app.bot.send_poll(
        chat_id=chat_id,
        question=pergunta,
        options=opcoes,
        type=Poll.QUIZ,
        correct_option_id=resposta,
        is_anonymous=False,
    )
    print(f"✅ Quiz enviado: {pergunta}")

async def loop_quizzes(app):
    while True:
        await enviar_quiz(app)
        await asyncio.sleep(45 * 60)  # 45 minutos

# ------------------- RANKING SEMANAL -------------------
async def ranking_semanal():
    while True:
        agora = datetime.now()
        if agora.weekday() == 6 and agora.hour == 23:  # domingo 23h
            ranking = sorted(usuarios.items(), key=lambda x: x[1]["pontos"], reverse=True)
            top3 = ranking[:3]
            if len(top3) > 0:
                bonus = [730, 500, 300]
                for i, (uid, data) in enumerate(top3):
                    data["pontos"] += bonus[i]
                salvar_json(USUARIOS_FILE, usuarios)
                print(f"🏆 Ranking semanal atualizado! Bônus aplicados aos top 3.")
        await asyncio.sleep(3600)  # verifica a cada hora

# ------------------- RESPOSTAS -------------------
async def receber_resposta(update, context):
    resposta = update.poll_answer
    user_id = resposta.user.id
    user_respostas = resposta.option_ids

    quiz = quizzes.get(resposta.poll_id)
    if quiz:
        correta = quiz["resposta"]
        acertou = correta in user_respostas
        atualizar_pontos(user_id, acertou)
        print(f"✅ {'Acertou' if acertou else 'Errou'} - User {user_id}")

# ------------------- EXECUÇÃO PRINCIPAL -------------------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(PollAnswerHandler(receber_resposta))

    asyncio.create_task(loop_quizzes(app))
    asyncio.create_task(ranking_semanal())

    print("🤖 Bot rodando 24h no Render!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
