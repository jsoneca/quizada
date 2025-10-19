import os
import json
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# === CONFIGURAÇÕES ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
QUIZ_FILE = "quizzes.json"
USERS_FILE = "usuarios.json"

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
        return (pontos - 50) // 50 + 2  # cresce progressivamente

# === Comandos do bot ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    usuarios = carregar_usuarios()

    if str(user.id) not in usuarios:
        usuarios[str(user.id)] = {"nome": user.first_name, "pontos": 0}
        salvar_usuarios(usuarios)

    await update.message.reply_text(
        f"🎮 Olá {user.first_name}! Bem-vindo ao QuizBot!\nUse /quiz para começar e /ranking para ver os melhores!"
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quizzes = carregar_quizzes()
    q = random.choice(quizzes)
    botoes = [
        [InlineKeyboardButton(text=o, callback_data=f"{quizzes.index(q)}:{i}")]
        for i, o in enumerate(q["opcoes"])
    ]
    markup = InlineKeyboardMarkup(botoes)
    await update.message.reply_text(q["pergunta"], reply_markup=markup)

async def resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    usuarios = carregar_usuarios()
    quizzes = carregar_quizzes()
    user = query.from_user
    q_id, r_id = map(int, query.data.split(":"))
    q = quizzes[q_id]

    if str(user.id) not in usuarios:
        usuarios[str(user.id)] = {"nome": user.first_name, "pontos": 0}

    pontos_atuais = usuarios[str(user.id)]["pontos"]

    # Sistema de pontuação
    if r_id == q["correta"]:
        usuarios[str(user.id)]["pontos"] += 35
        texto = f"✅ Correto! +35 pontos!"
    else:
        texto = f"❌ Errado! Resposta certa: {q['opcoes'][q['correta']]}"

    salvar_usuarios(usuarios)

    novos_pontos = usuarios[str(user.id)]["pontos"]
    nivel = calcular_nivel(novos_pontos)

    await query.edit_message_text(
        f"{texto}\n\n⭐ Pontos: {novos_pontos}\n🏅 Nível: {nivel}"
    )

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuarios = carregar_usuarios()
    ranking = sorted(usuarios.items(), key=lambda x: x[1]["pontos"], reverse=True)

    texto = "🏆 *Ranking Geral:*\n\n"
    for i, (uid, u) in enumerate(ranking[:10], 1):
        nivel = calcular_nivel(u["pontos"])
        texto += f"{i}. {u['nome']} — {u['pontos']} pts (Nível {nivel})\n"

    await update.message.reply_text(texto, parse_mode="Markdown")

# === Inicialização ===
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(CommandHandler("ranking", ranking))
app.add_handler(CallbackQueryHandler(resposta))

print("🤖 Bot rodando...")
app.run_polling()
