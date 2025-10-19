import os
import json
import random
import asyncio
from datetime import datetime, time, timedelta
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, PollAnswerHandler, ContextTypes

# CONFIGURAÇÕES
TOKEN = os.getenv("TELEGRAM_TOKEN")
QUIZ_FILE = "quizzes.json"
USERS_FILE = "usuarios.json"
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # grupo/canal
INTERVALO_MINUTOS = 45
INICIO = time(7, 0)   # 07:00
FIM = time(23, 0)     # 23:00

bot = Bot(token=TOKEN)

# === Funções auxiliares ===
def carregar_quizzes():
    with open(QUIZ_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def carregar_usuarios():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({}, f)
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_usuarios(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def calcular_nivel(pontos):
    if pontos < 50:
        return 1
    else:
        return (pontos - 50) // 50 + 2

def hora_valida():
    agora = datetime.now().time()
    return INICIO <= agora <= FIM

# Embaralhar opções mantendo correta
def embaralhar_opcoes(pergunta):
    opcoes = pergunta["opcoes"].copy()
    correta = pergunta["correta"]
    combinacoes = list(enumerate(opcoes))
    random.shuffle(combinacoes)
    novas_opcoes = [o for i, o in combinacoes]
    nova_correta = [i for i, (orig_i, _) in enumerate(combinacoes) if orig_i == correta][0]
    pergunta["opcoes"] = novas_opcoes
    pergunta["correta"] = nova_correta
    return pergunta

# Enviar quiz
async def enviar_quiz(q):
    msg = await bot.send_poll(
        chat_id=CHAT_ID,
        question=q["pergunta"],
        options=q["opcoes"],
        type="quiz",
        correct_option_id=q["correta"],
        is_anonymous=False
    )
    return {msg.poll.id: q}

# Receber resposta
async def receber_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.poll_answer
    user_id = str(resposta.user.id)
    poll_id = resposta.poll_id
    usuarios = carregar_usuarios()
    quizzes_enviadas = context.bot_data

    if poll_id not in quizzes_enviadas:
        return

    q = quizzes_enviadas[poll_id]
    correta = q["correta"]

    if user_id not in usuarios:
        usuarios[user_id] = {"nome": resposta.user.first_name, "pontos": 50}

    if resposta.option_ids and resposta.option_ids[0] == correta:
        usuarios[user_id]["pontos"] += 35
        resultado = "✅ Acertou! +35 pontos"
    else:
        resultado = f"❌ Errou! Resposta correta: {q['opcoes'][correta]}"

    salvar_usuarios(usuarios)
    pontos = usuarios[user_id]["pontos"]
    nivel = calcular_nivel(pontos)

    await bot.send_message(
        chat_id=resposta.user.id,
        text=f"{resultado}\n⭐ Pontos: {pontos}\n🏅 Nível: {nivel}"
    )

# Loop automático
async def loop_quizzes(app):
    quizzes = carregar_quizzes()
    while True:
        if hora_valida():
            q = random.choice(quizzes)
            q = embaralhar_opcoes(q)
            print(f"⏰ Enviando quiz: {q['pergunta']}")
            quizzes_enviadas = await enviar_quiz(q)
            app.bot_data.update(quizzes_enviadas)
            await asyncio.sleep(INTERVALO_MINUTOS * 60)
        else:
            agora = datetime.now()
            proximo_inicio = datetime.combine(agora.date(), INICIO)
            if agora.time() > FIM:
                proximo_inicio += timedelta(days=1)
            segundos_ate_inicio = (proximo_inicio - agora).total_seconds()
            print(f"🛌 Fora do horário. Dormindo {int(segundos_ate_inicio/60)} minutos")
            await asyncio.sleep(segundos_ate_inicio)

# Inicialização
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(PollAnswerHandler(receber_resposta))
    asyncio.create_task(loop_quizzes(app))
    print("🤖 Bot rodando automaticamente...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
