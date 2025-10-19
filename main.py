import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# Ative logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Carregue suas perguntas do JSON
with open("quiz.json", "r", encoding="utf-8") as f:
    quiz = json.load(f)

# Função inicial /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_q"] = 0
    await send_question(update, context)

# Envia a pergunta atual
async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    index = context.user_data.get("current_q", 0)
    if index >= len(quiz):
        await update.message.reply_text("Parabéns! Você terminou o quiz.")
        return

    question = quiz[index]
    buttons = [
        [InlineKeyboardButton(opt, callback_data=str(i))]
        for i, opt in enumerate(question["opcoes"])
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    if update.message:
        await update.message.reply_text(question["pergunta"], reply_markup=reply_markup)
    else:  # resposta via callback
        await update.callback_query.message.reply_text(
            question["pergunta"], reply_markup=reply_markup
        )

# Função chamada quando usuário clica em uma resposta
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    index = context.user_data.get("current_q", 0)
    question = quiz[index]
    selected = int(query.data)

    if selected == question["correta"]:
        await query.edit_message_text(text=f"✅ Correto! {question['opcoes'][selected]}")
    else:
        correta = question["opcoes"][question["correta"]]
        await query.edit_message_text(
            text=f"❌ Errado! A resposta correta é: {correta}"
        )

    # Avança para a próxima pergunta
    context.user_data["current_q"] = index + 1
    if context.user_data["current_q"] < len(quiz):
        await send_question(update, context)

# Configurações do bot
async def main():
    TOKEN = "TELEGRAM_TOKEN"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    # Inicia o bot
    await app.initialize()
    await app.start()
    print("Bot rodando...")
    await app.updater.start_polling()
    await app.idle()  # Mantém o bot ativo

import asyncio
asyncio.run(main())
