import logging
import os
import json
import random
import asyncio
import pytz
from datetime import datetime, time
from flask import Flask
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler
)

# ==============================================================
# 🔧 CONFIGURAÇÕES
# ==============================================================

os.environ["TZ"] = "America/Sao_Paulo"
timezone = pytz.timezone("America/Sao_Paulo")

TOKEN = "8197621920:AAF63zyswckSBILJ9M0WpHPVlNJDe0YRi4M"  # substitua pelo token do BotFather
OWNER_ID = 8126443922  # seu ID do Telegram (sem vírgula!)

QUIZZES_FILE = "quizzes.json"
USERS_FILE = "usuarios.json"
TEMPORADA_FILE = "temporada.json"
HISTORICO_FILE = "historico.json"

# ==============================================================
# 📜 LOGGING
# ==============================================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==============================================================
# 🧩 FUNÇÕES DE SUPORTE
# ==============================================================

def carregar_json(arquivo, padrao):
    if not os.path.exists(arquivo):
        with open(arquivo, "w") as f:
            json.dump(padrao, f)
    with open(arquivo, "r") as f:
        return json.load(f)

def salvar_json(arquivo, dados):
    with open(arquivo, "w") as f:
        json.dump(dados, f, indent=4)

def carregar_quizzes():
    return carregar_json(QUIZZES_FILE, [])

def carregar_usuarios():
    return carregar_json(USERS_FILE, {})

def salvar_usuarios(users):
    salvar_json(USERS_FILE, users)

def carregar_temporada():
    return carregar_json(TEMPORADA_FILE, {"estacao_atual": estacao_atual(), "inicio": str(datetime.now(timezone))})

def salvar_temporada(temp):
    salvar_json(TEMPORADA_FILE, temp)

def carregar_historico():
    return carregar_json(HISTORICO_FILE, [])

def salvar_historico(hist):
    salvar_json(HISTORICO_FILE, hist)

def estacao_atual():
    mes = datetime.now(timezone).month
    if mes in [12, 1, 2]:
        return "☀️ Verão"
    elif mes in [3, 4, 5]:
        return "🍂 Outono"
    elif mes in [6, 7, 8]:
        return "❄️ Inverno"
    else:
        return "🌸 Primavera"

def pontos_para_proximo_nivel(level):
    return 50 + (level - 1) * 50

def classificacao_por_level(level):
    if level <= 5:
        return "🪶 Iniciante"
    elif level <= 10:
        return "⚔️ Competidor"
    elif level <= 17:
        return "🏅 Veterano"
    else:
        return "👑 Lendário"

# ==============================================================
# ⚙️ COMANDOS
# ==============================================================

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        f"👋 Olá, {update.effective_user.first_name}!\n"
        f"Bem-vindo ao *QuizBot*! Estamos em {estacao_atual()} 🌎\n\n"
        "🎯 Use /entrar para começar a jogar!\n"
        "💰 Use /bonus para pegar seu bônus semanal.\n"
        "📊 Use /ranking para ver o placar!\n"
        "❓ Use /ajuda para saber mais.",
        parse_mode="Markdown"
    )
    await asyncio.sleep(2400)
    await msg.delete()
    await update.message.delete()

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        "🎮 *Como jogar o QuizBot:*\n\n"
        "1️⃣ Use /entrar para participar.\n"
        "2️⃣ A cada 45 minutos (07h–23h), um quiz é enviado.\n"
        "3️⃣ Ganhe pontos, suba de level e receba bônus!\n"
        "4️⃣ Todo fim de temporada, os Top 3 ganham destaque! 🏆",
        parse_mode="Markdown"
    )
    await asyncio.sleep(2400)
    await msg.delete()
    await update.message.delete()

async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = carregar_usuarios()

    if user_id in users:
        msg = await update.message.reply_text("✅ Você já está participando!")
    else:
        users[user_id] = {"pontos": 0, "streak": 0, "level": 1, "semana": 0}
        salvar_usuarios(users)
        msg = await update.message.reply_text("🎉 Bem-vindo! Você entrou no QuizBot!\nUse /quiz para jogar!")
    await asyncio.sleep(2400)
    await msg.delete()
    await update.message.delete()

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = carregar_usuarios()
    if not users:
        msg = await update.message.reply_text("📭 Nenhum jogador registrado ainda.")
        await asyncio.sleep(2400)
        await msg.delete()
        await update.message.delete()
        return

    ranking = sorted(users.items(), key=lambda x: x[1]["pontos"], reverse=True)
    texto = "🏆 *Ranking Atual do QuizBot*\n\n"
    medalhas = ["🥇", "🥈", "🥉"] + ["🎖️"] * 7

    for i, (uid, data) in enumerate(ranking[:10]):
        classificacao = classificacao_por_level(data["level"])
        texto += f"{medalhas[i]} [{uid}](tg://user?id={uid}) — {data['pontos']} pts | Nível {data['level']} {classificacao}\n"

    msg = await update.message.reply_text(texto, parse_mode="Markdown")
    await asyncio.sleep(2400)
    await msg.delete()
    await update.message.delete()

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quizzes = carregar_quizzes()
    if not quizzes:
        msg = await update.message.reply_text("📭 Nenhum quiz disponível.")
        await asyncio.sleep(2400)
        await msg.delete()
        await update.message.delete()
        return

    q = random.choice(quizzes)
    poll_msg = await update.message.reply_poll(
        question=f"{estacao_atual()} 🌎 | {q['pergunta']}",
        options=q["opcoes"],
        type="quiz",
        correct_option_id=q["correta"],
        is_anonymous=False
    )
    await asyncio.sleep(2400)
    try:
        await poll_msg.delete()
        await update.message.delete()
    except:
        pass

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = carregar_usuarios()
    agora = datetime.now(timezone)
    semana = agora.isocalendar()[1]

    if user_id in users and users[user_id].get("semana") == semana:
        msg = await update.message.reply_text("🎁 Você já pegou seu bônus semanal!")
    else:
        users[user_id] = users.get(user_id, {"pontos": 0, "streak": 0, "level": 1})
        users[user_id]["semana"] = semana
        users[user_id]["pontos"] += 10
        salvar_usuarios(users)
        msg = await update.message.reply_text("💰 Você recebeu +10 pontos de bônus semanal!")
    await asyncio.sleep(2400)
    await msg.delete()
    await update.message.delete()

# ==============================================================
# 🧠 QUIZ AUTOMÁTICO + PROGRESSO
# ==============================================================

async def quiz_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.poll_answer is None:
        return

    user_id = str(update.poll_answer.user.id)
    users = carregar_usuarios()
    user_data = users.get(user_id, {"pontos": 0, "streak": 0, "level": 1})

    user_data["pontos"] += 35
    user_data["streak"] += 1

    pontos_necessarios = pontos_para_proximo_nivel(user_data["level"])
    if user_data["pontos"] >= pontos_necessarios:
        user_data["level"] += 1
        classificacao = classificacao_por_level(user_data["level"])
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 *Parabéns!* Você subiu para o nível {user_data['level']} — {classificacao}!",
            parse_mode="Markdown"
        )

    if user_data["streak"] >= 5:
        user_data["streak"] = 0
        user_data["pontos"] += 25
        await context.bot.send_message(
            chat_id=user_id,
            text="🏅 *Incrível!* Você participou de 5 quizzes seguidos e ganhou +25 pontos! 🎉",
            parse_mode="Markdown"
        )

    users[user_id] = user_data
    salvar_usuarios(users)

# ==============================================================
# 🌸 SISTEMA DE TEMPORADA + HISTÓRICO
# ==============================================================

async def verificar_temporada(bot):
    temp = carregar_temporada()
    hist = carregar_historico()
    estacao_atual_hoje = estacao_atual()

    if temp["estacao_atual"] != estacao_atual_hoje:
        users = carregar_usuarios()
        ranking = sorted(users.items(), key=lambda x: x[1]["pontos"], reverse=True)
        top3 = ranking[:3]

        temporada_encerrada = {
            "estacao": temp["estacao_atual"],
            "inicio": temp["inicio"],
            "fim": str(datetime.now(timezone)),
            "vencedores": [
                {"id": uid, "pontos": data["pontos"], "level": data["level"]}
                for uid, data in top3
            ]
        }

        hist.append(temporada_encerrada)
        salvar_historico(hist)

        msg_fim = "🏁 *Fim de temporada!* Veja os Top 3 vencedores:\n\n"
        for i, (uid, data) in enumerate(top3, start=1):
            msg_fim += f"{i}️⃣ [{uid}](tg://user?id={uid}) — {data['pontos']} pts, Nível {data['level']}\n"

        msg_fim += f"\n🌸 *Nova temporada iniciada!* Bem-vindos ao {estacao_atual_hoje} 🌎"

        for uid in users:
            users[uid]["pontos"] = 0
            users[uid]["level"] = 1
            users[uid]["streak"] = 0
            try:
                await bot.send_message(chat_id=uid, text=msg_fim, parse_mode="Markdown")
            except:
                continue

        salvar_usuarios(users)
        temp["estacao_atual"] = estacao_atual_hoje
        temp["inicio"] = str(datetime.now(timezone))
        salvar_temporada(temp)

# ==============================================================
# ⏰ ENVIOS AUTOMÁTICOS
# ==============================================================

async def enviar_quiz_automatico(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(timezone).time()
    if not (time(7, 0) <= agora <= time(23, 0)):
        return

    await verificar_temporada(context.bot)
    quizzes = carregar_quizzes()
    if not quizzes:
        return

    q = random.choice(quizzes)
    estacao = estacao_atual()

    for user_id in carregar_usuarios().keys():
        try:
            msg = await context.bot.send_poll(
                chat_id=user_id,
                question=f"{estacao} 🌎 | {q['pergunta']}",
                options=q["opcoes"],
                type="quiz",
                correct_option_id=q["correta"],
                is_anonymous=False
            )
            await asyncio.sleep(2400)
            await msg.delete()
        except:
            continue

# ==============================================================
# 🔌 COMANDO /PARAR
# ==============================================================

async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 Apenas o dono do bot pode usar este comando.")
        return
    await update.message.reply_text("🛑 Bot encerrado manualmente.")
    os._exit(0)

# ==============================================================
# 🚀 EXECUÇÃO
# ==============================================================

import nest_asyncio
nest_asyncio.apply()

def main():
    async def run_bot():
        application = Application.builder().token(TOKEN).build()

        application.add_handler(CommandHandler("iniciar", iniciar))
        application.add_handler(CommandHandler("entrar", entrar))
        application.add_handler(CommandHandler("ajuda", ajuda))
        application.add_handler(CommandHandler("ranking", ranking))
        application.add_handler(CommandHandler("quiz", quiz))
        application.add_handler(CommandHandler("bonus", bonus))
        application.add_handler(CommandHandler("parar", parar))
        application.add_handler(PollAnswerHandler(quiz_resposta))

        scheduler = AsyncIOScheduler(timezone=timezone)
        scheduler.add_job(
            lambda: asyncio.create_task(enviar_quiz_automatico(application)),
            "interval",
            minutes=45
        )
        scheduler.start()

        logger.info("🤖 Bot ativo! Enviando quizzes a cada 45min (07h–23h).")
        await application.run_polling(drop_pending_updates=True)

    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
