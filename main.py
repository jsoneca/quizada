import os
import json
import random
import asyncio
from datetime import datetime, time, timedelta
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, PollAnswerHandler, ContextTypes
import matplotlib.pyplot as plt

# CONFIGURAÇÕES
TOKEN = os.getenv("TELEGRAM_TOKEN")
QUIZ_FILE = "quizzes.json"
USERS_FILE = "usuarios.json"
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
INTERVALO_MINUTOS = 45
INICIO = time(7, 0)
FIM = time(23, 0)

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
        usuarios[user_id] = {"nome": resposta.user.first_name, "pontos": 50, "pontos_semana": 0}

    if resposta.option_ids and resposta.option_ids[0] == correta:
        usuarios[user_id]["pontos"] += 35
        usuarios[user_id]["pontos_semana"] += 35
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

# === Funções de ranking e gráfico ===
def gerar_grafico_semana(usuarios):
    nomes = [data["nome"] for data in usuarios.values()]
    pontos = [data.get("pontos_semana",0) for data in usuarios.values()]

    plt.figure(figsize=(10,6))
    plt.barh(nomes, pontos, color="orange")
    plt.xlabel("Pontos Semanais")
    plt.title("🏆 Ranking Semanal")
    plt.tight_layout()
    arquivo = "ranking_semanal.png"
    plt.savefig(arquivo)
    plt.close()
    return arquivo

async def ranking_semanal():
    while True:
        agora = datetime.now()
        if agora.weekday() == 0 and agora.hour == 0 and agora.minute < 1:
            usuarios = carregar_usuarios()
            ranking = sorted(usuarios.items(), key=lambda x: x[1].get("pontos_semana",0), reverse=True)
            bonus = [730, 500, 250]

            mensagem_bonus = "🎉 **Bônus Semanal Top 3** 🎉\n\n"
            for i, (user_id, data) in enumerate(ranking[:3]):
                data["pontos"] += bonus[i]
                mensagem_bonus += f"{i+1}º {data['nome']}: +{bonus[i]} pontos!\n"
                data["pontos_semana"] = 0
                await bot.send_message(chat_id=user_id, text=f"🏆 Parabéns! Você ficou em {i+1}º lugar da semana e recebeu +{bonus[i]} pontos!")

            for user_id, data in ranking[3:]:
                data["pontos_semana"] = 0

            salvar_usuarios(usuarios)

            # Enviar gráfico
            arquivo_grafico = gerar_grafico_semana(usuarios)
            with open(arquivo_grafico, "rb") as f:
                await bot.send_photo(chat_id=CHAT_ID, photo=f, caption=mensagem_bonus)

            print("🏆 Bônus e gráfico semanal enviados!")
            await asyncio.sleep(61)
        else:
            await asyncio.sleep(30)

# === Loop diário com shuffle ===
async def loop_quizzes(app):
    quizzes = carregar_quizzes()
    ultimo_dia = None
    perguntas_ordenadas = []

    while True:
        agora = datetime.now()
        dia_atual = agora.date()

        if dia_atual != ultimo_dia:
            perguntas_ordenadas = quizzes.copy()
            random.shuffle(perguntas_ordenadas)
            ultimo_dia = dia_atual
            print("🔀 Perguntas embaralhadas para o dia!")

        if hora_valida():
            if not perguntas_ordenadas:
                perguntas_ordenadas = quizzes.copy()
                random.shuffle(perguntas_ordenadas)

            q = perguntas_ordenadas.pop(0)
            q = embaralhar_opcoes(q)
            print(f"⏰ Enviando quiz: {q['pergunta']}")
            quizzes_enviadas = await enviar_quiz(q)
            app.bot_data.update(quizzes_enviadas)
            await asyncio.sleep(INTERVALO_MINUTOS * 60)
        else:
            proximo_inicio = datetime.combine(agora.date(), INICIO)
            if agora.time() > FIM:
                proximo_inicio += timedelta(days=1)
            segundos_ate_inicio = (proximo_inicio - agora).total_seconds()
            print(f"🛌 Fora do horário. Dormindo {int(segundos_ate_inicio/60)} minutos")
            await asyncio.sleep(segundos_ate_inicio)

# === Inicialização ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(PollAnswerHandler(receber_resposta))

    asyncio.create_task(loop_quizzes(app))
    asyncio.create_task(ranking_semanal())

    print("🤖 Bot rodando com shuffle diário, ranking semanal e gráfico!")

    app.run_polling()
