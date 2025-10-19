import os
import json
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PollAnswerHandler

# === CONFIGURAÇÕES ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
QUIZ_FILE = "quizzes.json"
USERS_FILE = "usuarios.json"

# === FUNÇÕES AUXILIARES ===
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

# === COMANDOS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    usuarios = carregar_usuarios()

    if str(user.id) not in usuarios:
        usuarios[str(user.id)] = {"nome": user.first_name, "pontos": 50}
        salvar_usuarios(usuarios)

    await update.message.reply_text(
        f"🎮 Olá {user.first_name}! Bem-vindo ao QuizBot!\n\n"
        "Use /quiz para começar e /ranking para ver os melhores jogadores!"
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quizzes = carregar_quizzes()
    q = random.choice(quizzes)

    # Envia o quiz oficial do Telegram
    msg = await update.message.reply_poll(
        question=q["pergunta"],
        options=q["opcoes"],
        type="quiz",
        correct_option_id=q["correta"],
        is_anonymous=False,
    )

    # Salva qual pergunta foi enviada e qual é a resposta certa
    payload = {
        msg.poll.id: {"quiz_id": quizzes.index(q), "mensagem_id": msg.message_id}
    }
    context.bot_data.update(payload)

async def receber_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.poll_answer
    user_id = resposta.user.id
    poll_id = resposta.poll_id
    usuarios = carregar_usuarios()
    quizzes = carregar_quizzes()

    if str(user_id) not in usuarios:
        return  # usuário ainda não fez /start

    if poll_id not in context.bot_data:
        return  # quiz não encontrado

    quiz_id = context.bot_data[poll_id]["quiz_id"]
    q = quizzes[quiz_id]
    correta = q["correta"]

    if resposta.option_ids and resposta.option_ids[0] == correta:
        usuarios[str(user_id)]["pontos"] += 35
        resultado = "✅ Você acertou! +35 pontos!"
    else:
        resultado = f"❌ Errou! A resposta certa era: {q['opcoes'][correta]}"

    salvar_usuarios(usuarios)
    pontos = usuarios[str(user_id)]["pontos"]
    nivel = calcular_nivel(pontos)

    # Envia mensagem com feedback
    await context.bot.send_message(
        chat_id=user_id,
        text=f"{resultado}\n⭐ Pontos: {pontos}\n🏅 Nível: {nivel}"
    )

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuarios = carregar_usuarios()
    ranking = sorted(usuarios.items(), key=lambda x: x[1]["pontos"], reverse=True)

    texto = "🏆 *Ranking Geral:*\n\n"
    for i, (uid, u) in enumerate(ranking[:10], 1):
        nivel = calcular_nivel(u["pontos"])
        texto += f"{i}. {u['nome']} — {u['pontos']} pts (Nível {nivel})\n"

    await update.message.reply_text(texto, parse_mode="Markdown")

# === EXECUÇÃO ===
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(CommandHandler("ranking", ranking))
app.add_handler(PollAnswerHandler(receber_resposta))

print("🤖 Bot de quiz rodando...")
app.run_polling()
