import os
import json
import random
import asyncio
from datetime import datetime, time, timedelta
from telegram import Update, Poll
from telegram.ext import ApplicationBuilder, CommandHandler, PollAnswerHandler, ContextTypes

# ================= CONFIGURAÇÃO =================
TOKEN = os.getenv("TELEGRAM_TOKEN")      # Token do bot
QUIZZES_FILE = "quizzes.json"
USUARIOS_FILE = "usuarios.json"
INTERVALO_MINUTOS = 45
HORA_INICIO = time(7, 0)
HORA_FIM = time(23, 0)

# ================= FUNÇÕES AUXILIARES =================
def carregar_json(caminho):
    if not os.path.exists(caminho):
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def calcular_nivel(pontos):
    if pontos < 50:
        return 1
    return (pontos - 50) // 50 + 2

def hora_valida():
    agora = datetime.now().time()
    return HORA_INICIO <= agora <= HORA_FIM

def embaralhar_pergunta(q):
    opcoes = q["opcoes"].copy()
    correta = q["correta"]
    combinacoes = list(enumerate(opcoes))
    random.shuffle(combinacoes)
    novas_opcoes = [o for i, o in combinacoes]
    nova_correta = [i for i, (orig_i, _) in enumerate(combinacoes) if orig_i == correta][0]
    q["opcoes"] = novas_opcoes
    q["correta"] = nova_correta
    return q

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    usuarios = carregar_json(USUARIOS_FILE)
    if user_id not in usuarios:
        usuarios[user_id] = {"pontos": 50, "nivel": 1, "pontos_semana": 0}
        salvar_json(USUARIOS_FILE, usuarios)
    user = usuarios[user_id]
    await update.message.reply_text(
        f"🎯 Bem-vindo ao Quiz Bot!\n"
        f"⭐ Pontos: {user['pontos']}\n"
        f"🏅 Nível: {user['nivel']}\n"
        f"Novos quizzes serão enviados automaticamente!"
    )

# ================= LOOP DE QUIZZES =================
async def enviar_quiz(app):
    quizzes = carregar_json(QUIZZES_FILE)
    usuarios = carregar_json(USUARIOS_FILE)
    if not quizzes or not usuarios:
        print("⚠️ Nenhum quiz ou usuário encontrado.")
        return

    q = random.choice(list(quizzes.values()))
    q = embaralhar_pergunta(q)

    # envia o quiz para todos os usuários que já deram /start
    for user_id in usuarios.keys():
        try:
            message = await app.bot.send_poll(
                chat_id=int(user_id),
                question=q["pergunta"],
                options=q["opcoes"],
                type=Poll.QUIZ,
                correct_option_id=q["correta"],
                is_anonymous=False
            )
            app.bot_data[message.poll.id] = q
        except Exception as e:
            print(f"Erro ao enviar quiz para {user_id}: {e}")
    print(f"⏰ Quiz enviado: {q['pergunta']}")

async def loop_quizzes(app):
    while True:
        if hora_valida():
            await enviar_quiz(app)
            await asyncio.sleep(INTERVALO_MINUTOS * 60)
        else:
            agora = datetime.now()
            proximo_inicio = datetime.combine(agora.date(), HORA_INICIO)
            if agora.time() > HORA_FIM:
                proximo_inicio += timedelta(days=1)
            segundos_ate_inicio = (proximo_inicio - agora).total_seconds()
            print(f"🛌 Fora do horário. Dormindo {int(segundos_ate_inicio/60)} minutos")
            await asyncio.sleep(segundos_ate_inicio)

# ================= RANKING SEMANAL =================
async def ranking_semanal(app):
    while True:
        agora = datetime.now()
        if agora.weekday() == 0 and agora.hour == 0 and agora.minute < 5:  # segunda-feira 00:00
            usuarios = carregar_json(USUARIOS_FILE)
            ranking = sorted(usuarios.items(), key=lambda x: x[1].get("pontos_semana",0), reverse=True)
            bonus = [730, 500, 250]
            for i, (uid, data) in enumerate(ranking[:3]):
                data["pontos"] += bonus[i]
                data["pontos_semana"] = 0
            for uid, data in ranking[3:]:
                data["pontos_semana"] = 0
            salvar_json(USUARIOS_FILE, usuarios)
            print("🏆 Ranking semanal atualizado com bônus!")
        await asyncio.sleep(60)

# ================= RESPOSTAS =================
async def receber_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.poll_answer
    user_id = str(resposta.user.id)
    poll_id = resposta.poll_id
    usuarios = carregar_json(USUARIOS_FILE)
    quizzes_enviadas = context.bot_data

    if poll_id not in quizzes_enviadas:
        return

    q = quizzes_enviadas[poll_id]
    correta = q["correta"]

    if user_id not in usuarios:
        usuarios[user_id] = {"pontos": 50, "nivel": 1, "pontos_semana": 0}

    acertou = resposta.option_ids and resposta.option_ids[0] == correta
    if acertou:
        usuarios[user_id]["pontos"] += 35
        usuarios[user_id]["pontos_semana"] += 35

    usuarios[user_id]["nivel"] = calcular_nivel(usuarios[user_id]["pontos"])
    salvar_json(USUARIOS_FILE, usuarios)

# ================= INICIALIZAÇÃO =================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(PollAnswerHandler(receber_resposta))

# Tasks em background
asyncio.create_task(loop_quizzes(app))
asyncio.create_task(ranking_semanal(app))

print("🤖 Bot iniciado e rodando 24h!")
app.run_polling()
