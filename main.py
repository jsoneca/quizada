import os
import json
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# === CONFIG ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
QUIZ_FILE = "quizzes.json"
USERS_FILE = "usuarios.json"

if TOKEN is None:
    raise RuntimeError("Variável de ambiente TELEGRAM_TOKEN não encontrada.")

# === Helpers ===
def carregar_quizzes():
    if not os.path.exists(QUIZ_FILE):
        return []
    with open(QUIZ_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def carregar_usuarios():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_usuarios(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# === Commands ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    usuarios = carregar_usuarios()
    if str(user.id) not in usuarios:
        usuarios[str(user.id)] = {"nome": user.first_name or user.username or "Usuário", "pontos": 0}
        salvar_usuarios(usuarios)
    await update.message.reply_text(
        f"🎮 Olá {user.first_name or user.username or 'jogador'}! Bem-vindo ao QuizBot!\nUse /quiz para começar e /ranking para ver o top 10."
    )

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quizzes = carregar_quizzes()
    if not quizzes:
        await update.message.reply_text("Nenhum quiz disponível. Peça ao admin para adicionar perguntas.")
        return

    q = random.choice(quizzes)
    # Guarda o índice real (para poder buscar no arquivo)
    idx = quizzes.index(q)
    buttons = [[InlineKeyboardButton(text=o, callback_data=f"{idx}:{i}")] for i, o in enumerate(q["opcoes"])]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(q["pergunta"], reply_markup=markup)

async def resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    usuarios = carregar_usuarios()
    quizzes = carregar_quizzes()
    user = query.from_user

    try:
        q_id, r_id = map(int, query.data.split(":"))
    except Exception:
        await query.edit_message_text("Erro ao processar resposta.")
        return

    if q_id < 0 or q_id >= len(quizzes):
        await query.edit_message_text("Pergunta inválida.")
        return

    q = quizzes[q_id]
    if str(user.id) not in usuarios:
        usuarios[str(user.id)] = {"nome": user.first_name or user.username or "Usuário", "pontos": 0}

    if r_id == q["correta"]:
        usuarios[str(user.id)]["pontos"] += 10
        texto = "✅ Correto! +10 pontos!"
    else:
        usuarios[str(user.id)]["pontos"] = max(0, usuarios[str(user.id)]["pontos"] - 2)
        texto = f"❌ Errado! Resposta certa: {q['opcoes'][q['correta']]}"

    salvar_usuarios(usuarios)
    pontos = usuarios[str(user.id)]["pontos"]
    nivel = pontos // 100

    await query.edit_message_text(f"{texto}\n\n⭐ Pontos: {pontos}\n🏅 Nível: {nivel}")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuarios = carregar_usuarios()
    ranking = sorted(usuarios.items(), key=lambda x: x[1]["pontos"], reverse=True)
    if not ranking:
        await update.message.reply_text("Ainda não há jogadores.")
        return

    texto = "🏆 *Ranking Geral:*\n\n"
    for i, (uid, u) in enumerate(ranking[:10], 1):
        texto += f"{i}. {u.get('nome','Usuário')} — {u.get('pontos',0)} pts\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

# === Setup bot ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CallbackQueryHandler(resposta))
    print("🤖 Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
