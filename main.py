import os
import json
import random
import asyncio
from datetime import datetime, time, timedelta
from telegram import Bot, Update, Poll
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    PollAnswerHandler,
    ContextTypes,
)
import nest_asyncio

TOKEN = os.getenv("TELEGRAM_TOKEN")
QUIZ_FILE = "quizzes.json"
USERS_FILE = "usuarios.json"
INTERVALO_MINUTOS = 45
HORA_INICIO = time(7, 0)
HORA_FIM = time(23, 0)

bot = Bot(token=TOKEN)

def carregar_quizzes():
    with open(QUIZ_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.values()) if isinstance(data, dict) else data

def carregar_usuarios():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_usuarios(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def calcular_nivel(pontos):
    return 1 if pontos < 50 else (pontos - 50) // 50 + 2

def hora_valida():
    agora = datetime.now().time()
    return HORA_INICIO <= agora <= HORA_FIM

def embaralhar_opcoes(pergunta):
    opcoes = pergunta["opcoes"].copy()
    correta = pergunta["correta"]
    combinacoes = list(enumerate(opcoes))
    random.shuffle(combinacoes)
    novas_opcoes = [o for _, o in combinacoes]
    nova_correta = [i for i, (orig_i, _) in enumerate(combinacoes) if orig_i == correta][0]
    return {"pergunta": pergunta["pergunta"], "opcoes": novas_opcoes, "correta": nova_correta}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    usuarios = carregar_usuarios()
    uid = str(user.id)
    if uid not in usuarios:
        usuarios[uid] = {"nome": user.first_name, "pontos": 50, "pontos_semana": 0}
        salvar_usuarios(usuarios)
    await update.message.reply_text(
        "🎯 Bem-vindo ao Quiz Bot!\nVocê foi registrado e receberá quizzes automaticamente!\nUse /quiz para receber uma pergunta agora."
    )

async def quiz_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quizzes = carregar_quizzes()
    q = embaralhar_opcoes(random.choice(quizzes))
    msg = await update.message.reply_poll(
        question=q["pergunta"],
        options=q["opcoes"],
        type=Poll.QUIZ,
        correct_option_id=q["correta"],
        is_anonymous=False,
    )
    context.bot_data[msg.poll.id] = q

async def receber_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.poll_answer
    uid = str(resposta.user.id)
    pid = resposta.poll_id
    usuarios = carregar_usuarios()
    if pid not in context.bot_data:
        return
    q = context.bot_data[pid]
    correta = q["correta"]
    if uid not in usuarios:
        usuarios[uid] = {"nome": resposta.user.first_name, "pontos": 50, "pontos_semana": 0}
    if resposta.option_ids and resposta.option_ids[0] == correta:
        usuarios[uid]["pontos"] += 35
        usuarios[uid]["pontos_semana"] += 35
        texto = "✅ Acertou! +35 pontos"
    else:
        texto = f"❌ Errou! Resposta correta: {q['opcoes'][correta]}"
    usuarios[uid]["nivel"] = calcular_nivel(usuarios[uid]["pontos"])
    salvar_usuarios(usuarios)
    try:
        await bot.send_message(
            chat_id=int(uid),
            text=f"{texto}\n⭐ Pontos: {usuarios[uid]['pontos']}\n🏅 Nível: {usuarios[uid]['nivel']}",
        )
    except Exception as e:
        print(f"Erro ao enviar mensagem para {uid}: {e}")

async def ranking_semanal():
    while True:
        agora = datetime.now()
        if agora.weekday() == 0 and agora.hour == 0 and agora.minute < 1:
            usuarios = carregar_usuarios()
            ranking = sorted(usuarios.items(), key=lambda x: x[1].get("pontos_semana", 0), reverse=True)
            bonus = [730, 500, 250]
            for i, (uid, data) in enumerate(ranking[:3]):
                data["pontos"] += bonus[i]
                data["pontos_semana"] = 0
                try:
                    await bot.send_message(chat_id=int(uid), text=f"🏆 Parabéns! Você ficou no top {i+1} da semana!")
                except Exception:
                    pass
            for uid, data in ranking[3:]:
                data["pontos_semana"] = 0
            salvar_usuarios(usuarios)
            print("🏅 Ranking semanal atualizado.")
            await asyncio.sleep(61)
        else:
            await asyncio.sleep(30)

async def loop_quizzes(app):
    quizzes = carregar_quizzes()
    ultimo_dia = None
    perguntas = []
    while True:
        agora = datetime.now()
        dia = agora.date()
        if dia != ultimo_dia:
            perguntas = quizzes.copy()
            random.shuffle(perguntas)
            ultimo_dia = dia
            print("🔀 Novo embaralhamento diário.")
        if hora_valida():
            if not perguntas:
                perguntas = quizzes.copy()
                random.shuffle(perguntas)
            q = embaralhar_opcoes(perguntas.pop(0))
            usuarios = carregar_usuarios()
            if usuarios:
                for uid in list(usuarios.keys()):
                    try:
                        msg = await bot.send_poll(
                            chat_id=int(uid),
                            question=q["pergunta"],
                            options=q["opcoes"],
                            type=Poll.QUIZ,
                            correct_option_id=q["correta"],
                            is_anonymous=False,
                        )
                        app.bot_data[msg.poll.id] = q
                    except Exception as e:
                        print(f"Erro ao enviar para {uid}: {e}")
            await asyncio.sleep(INTERVALO_MINUTOS * 60)
        else:
            prox = datetime.combine(agora.date(), HORA_INICIO)
            if agora.time() > HORA_FIM:
                prox += timedelta(days=1)
            sleep = max((prox - agora).total_seconds(), 60)
            print(f"🛌 Fora do horário. Dormindo {int(sleep/60)} min.")
            await asyncio.sleep(sleep)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz_now))
    app.add_handler(PollAnswerHandler(receber_resposta))
    asyncio.create_task(loop_quizzes(app))
    asyncio.create_task(ranking_semanal())
    print("🤖 Bot iniciado e rodando no Render (versão compatível)!")
    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
