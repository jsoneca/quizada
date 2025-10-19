import os
import json
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import openai

# === CONFIGURAÇÕES ===
openai.api_key = os.getenv("OPENAI_API_KEY")
TOKEN = os.getenv("TELEGRAM_TOKEN")
DATA_FILE = "usuarios.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def carregar_dados():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def salvar_dados(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# === IA: GERA NOVO QUIZ ===
def gerar_quiz_ia():
    prompt = """Crie uma pergunta de múltipla escolha com 4 opções, sobre cultura geral.
    Responda no formato JSON:
    {
      "pergunta": "texto",
      "opcoes": ["A", "B", "C", "D"],
      "correta": número da opção (0-3)
    }"""
    resposta = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    conteudo = resposta["choices"][0]["message"]["content"]
    try:
        quiz = json.loads(conteudo)
    except:
        quiz = {"pergunta": "Erro ao gerar quiz.", "opcoes": ["Erro"], "correta": 0}
    return quiz

# === COMANDOS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = carregar_dados()
    if str(user.id) not in data:
        data[str(user.id)] = {"nome": user.first_name, "pontos": 0}
        salvar_dados(data)
    await update.message.reply_text(f"🎮 Olá {user.first_name}! Bem-vindo ao QuizBot!\nUse /quiz para começar!")

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = gerar_quiz_ia()
    opcoes = [[InlineKeyboardButton(o, callback_data=f"{json.dumps(q)}|{i}")] for i, o in enumerate(q["opcoes"])]
    markup = InlineKeyboardMarkup(opcoes)
    await update.message.reply_text(q["pergunta"], reply_markup=markup)

async def resposta_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = carregar_dados()
    user = query.from_user

    q_str, r_id = query.data.split("|")
    q = json.loads(q_str)
    r_id = int(r_id)
    correta = q["correta"]

    if str(user.id) not in data:
        data[str(user.id)] = {"nome": user.first_name, "pontos": 0}

    if r_id == correta:
        data[str(user.id)]["pontos"] += 10
        texto = "✅ Correto! +10 pontos!"
    else:
        data[str(user.id)]["pontos"] -= 2
        texto = f"❌ Errado! Resposta certa: {q['opcoes'][correta]}"

    salvar_dados(data)
    pontos = data[str(user.id)]["pontos"]
    nivel = pontos // 100
    await query.edit_message_text(f"{texto}\n⭐ Pontos: {pontos}\n🏅 Nível: {nivel}")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = carregar_dados()
    ranking = sorted(data.items(), key=lambda x: x[1]["pontos"], reverse=True)
    texto = "🏆 *Ranking Geral:*\n\n"
    for i, (uid, u) in enumerate(ranking[:10], 1):
        texto += f"{i}. {u['nome']} — {u['pontos']} pts\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

# === INICIALIZAÇÃO ===
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz_command))
app.add_handler(CommandHandler("ranking", ranking))
app.add_handler(CallbackQueryHandler(resposta_callback))

print("🤖 Bot rodando...")
app.run_polling()
