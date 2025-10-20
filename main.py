# main.py
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

# === CONFIGURAÇÕES ===
TOKEN = os.getenv("TELEGRAM_TOKEN")  # obrigatória
QUIZ_FILE = "quizzes.json"
USERS_FILE = "usuarios.json"

INTERVALO_MINUTOS = 45  # intervalo entre quizzes
HORA_INICIO = time(7, 0)
HORA_FIM = time(23, 0)

# Cria bot (usado para envios diretos)
bot = Bot(token=TOKEN)


# ---------------- utilitárias ----------------
def carregar_quizzes():
    """Carrega uma lista de quizzes. Suporta lista ([]) ou dict ({})."""
    with open(QUIZ_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Normaliza para lista
    if isinstance(data, dict):
        # se for dict com chaves numéricas -> retorna lista de valores
        return list(data.values())
    return data


def carregar_usuarios():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_usuarios(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def calcular_nivel(pontos: int) -> int:
    if pontos < 50:
        return 1
    return (pontos - 50) // 50 + 2


def hora_valida() -> bool:
    agora = datetime.now().time()
    return HORA_INICIO <= agora <= HORA_FIM


def embaralhar_opcoes(pergunta: dict) -> dict:
    """Retorna uma cópia da pergunta com opções embaralhadas e índice correto atualizado."""
    opcoes = pergunta["opcoes"].copy()
    correta = pergunta["correta"]
    combinacoes = list(enumerate(opcoes))
    random.shuffle(combinacoes)
    novas_opcoes = [o for orig_i, o in combinacoes]
    nova_correta = [new_i for new_i, (orig_i, _) in enumerate(combinacoes) if orig_i == correta][0]
    nova = {
        "pergunta": pergunta["pergunta"],
        "opcoes": novas_opcoes,
        "correta": nova_correta,
    }
    return nova


# ---------------- handlers e lógica do bot ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registra usuário quando executa /start e mostra mensagem de boas-vindas."""
    user = update.effective_user
    usuarios = carregar_usuarios()
    uid = str(user.id)
    if uid not in usuarios:
        usuarios[uid] = {"nome": user.first_name or user.username or "Usuário", "pontos": 50, "pontos_semana": 0}
        salvar_usuarios(usuarios)
    await update.message.reply_text(
        "🎯 Bem-vindo ao Quiz Bot!\n"
        "Você foi registrado e receberá quizzes automaticamente (quando estiver no horário).\n"
        "Use /quiz para receber uma pergunta agora."
    )


async def enviar_quiz_para_usuarios(q: dict, app):
    """
    Envia a mesma pergunta (com opções embaralhadas) para todos os usuários registrados.
    Atualiza app.bot_data com todos os poll.id -> pergunta.
    """
    usuarios = carregar_usuarios()
    if not usuarios:
        print("⚠️ Nenhum usuário registrado — não enviando quizzes.")
        return {}

    mapping = {}
    for uid in list(usuarios.keys()):
        try:
            message = await app.bot.send_poll(
                chat_id=int(uid),
                question=q["pergunta"],
                options=q["opcoes"],
                type=Poll.QUIZ,
                correct_option_id=q["correta"],
                is_anonymous=False,
            )
            mapping[message.poll.id] = q
        except Exception as e:
            print(f"Erro ao enviar quiz para {uid}: {e}")
            # não remover usuário automaticamente; apenas log
    return mapping


async def quiz_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /quiz para enviar uma pergunta imediata ao usuário (privado)."""
    quizzes = carregar_quizzes()
    if not quizzes:
        await update.message.reply_text("Nenhum quiz configurado.")
        return

    q = random.choice(quizzes)
    q_shuffled = embaralhar_opcoes(q)
    # envia apenas para quem chamou
    message = await update.message.reply_poll(
        question=q_shuffled["pergunta"],
        options=q_shuffled["opcoes"],
        type=Poll.QUIZ,
        correct_option_id=q_shuffled["correta"],
        is_anonymous=False,
    )
    # registra poll no bot_data para processar resposta
    context.bot_data[message.poll.id] = q_shuffled


async def receber_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa poll answer e atualiza pontos do usuário."""
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
        usuarios[user_id] = {"nome": resposta.user.first_name or "Usuário", "pontos": 50, "pontos_semana": 0}

    acertou = resposta.option_ids and resposta.option_ids[0] == correta
    if acertou:
        usuarios[user_id]["pontos"] += 35
        usuarios[user_id]["pontos_semana"] += 35
        resultado = "✅ Acertou! +35 pontos"
    else:
        # mostrar texto da opção correta (se disponível)
        correta_text = q["opcoes"][correta] if 0 <= correta < len(q["opcoes"]) else " (opção correta)"
        resultado = f"❌ Errou! Resposta correta: {correta_text}"

    usuarios[user_id]["nivel"] = calcular_nivel(usuarios[user_id]["pontos"])
    salvar_usuarios(usuarios)

    try:
        await bot.send_message(chat_id=int(user_id), text=f"{resultado}\n⭐ Pontos: {usuarios[user_id]['pontos']}\n🏅 Nível: {usuarios[user_id]['nivel']}")
    except Exception as e:
        print(f"Erro ao notificar usuário {user_id}: {e}")


# ---------------- tarefas periódicas ----------------
async def ranking_semanal():
    """Aplica bônus semanal e reseta pontos_semana (rodar na 00:00 de segunda)."""
    while True:
        agora = datetime.now()
        if agora.weekday() == 0 and agora.hour == 0 and agora.minute < 1:
            usuarios = carregar_usuarios()
            ranking = sorted(usuarios.items(), key=lambda x: x[1].get("pontos_semana", 0), reverse=True)
            bonus = [730, 500, 250]
            mensagem = "🏆 Ranking semanal concluído!\n\n"
            for i, (uid, data) in enumerate(ranking[:3]):
                data["pontos"] += bonus[i]
                mensagem += f"{i+1}º {data['nome']}: +{bonus[i]} pontos!\n"
                data["pontos_semana"] = 0
            for uid, data in ranking[3:]:
                data["pontos_semana"] = 0
            salvar_usuarios(usuarios)
            # envia mensagem para cada top3 individualmente (se necessário)
            for i, (uid, _) in enumerate(ranking[:3]):
                try:
                    await bot.send_message(chat_id=int(uid), text=f"🏆 Parabéns! Você ficou em {i+1}º lugar na semana e recebeu bônus!")
                except Exception:
                    pass
            print("🏆 Bônus semanal aplicado.")
            await asyncio.sleep(61)
        else:
            await asyncio.sleep(30)


async def loop_quizzes(app):
    """Loop principal que envia quizzes para todos os usuários registrados entre HORA_INICIO e HORA_FIM."""
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
            q_shuffled = embaralhar_opcoes(q)
            print(f"⏰ Enviando quiz (a todos os usuários): {q_shuffled['pergunta']}")
            mapping = await enviar_quiz_para_usuarios(q_shuffled, app)
            # atualiza bot_data com todos poll.id -> pergunta
            app.bot_data.update(mapping)
            await asyncio.sleep(INTERVALO_MINUTOS * 60)
        else:
            # calcula segundos até próximo início
            proximo_inicio = datetime.combine(agora.date(), HORA_INICIO)
            if agora.time() > HORA_FIM:
                proximo_inicio += timedelta(days=1)
            segundos_ate_inicio = (proximo_inicio - agora).total_seconds()
            if segundos_ate_inicio <= 0:
                segundos_ate_inicio = 60  # fallback
            print(f"🛌 Fora do horário. Dormindo {int(segundos_ate_inicio/60)} minutos...")
            await asyncio.sleep(segundos_ate_inicio)


# ---------------- inicialização ----------------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz_now))
    app.add_handler(PollAnswerHandler(receber_resposta))

    # cria tarefas de background usando event loop já ativo
    asyncio.create_task(loop_quizzes(app))
    asyncio.create_task(ranking_semanal())

    print("🤖 Bot iniciado — enviando quizzes apenas para usuários que deram /start.")
    # run_polling fica dentro do await para manter compatibilidade
    await app.run_polling()


# ---------------- execução compatível com Render/Replit ----------------
if __name__ == "__main__":
    # permite reentrância do loop em alguns hosts
    nest_asyncio.apply()
    # roda main() no loop atual (compatível com Render)
    asyncio.get_event_loop().run_until_complete(main())
