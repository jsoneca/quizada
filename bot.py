import os
import random
import asyncio
import logging
import json
from datetime import datetime, timedelta, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from collections import defaultdict

# === Configurações do bot ===
TOKEN = os.getenv("BOT_TOKEN")
QUIZ_INTERVALO = 45 * 60  # 45 minutos (em segundos)
HORARIO_INICIO = 7
HORARIO_FIM = 23
PONTOS_POR_ACERTO = 35
PONTOS_INICIAIS = 50

# === Configuração de logs (visível no Render) ===
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Carregar quizzes ===
def load_quizzes():
    try:
        with open("quizzes.json", "r", encoding="utf-8") as f:
            quizzes = json.load(f)
            if not isinstance(quizzes, list):
                raise ValueError("O arquivo quizzes.json deve conter uma lista de quizzes.")
            logger.info(f"✅ {len(quizzes)} quizzes carregados com sucesso.")
            return quizzes
    except FileNotFoundError:
        logger.warning("⚠️ Arquivo quizzes.json não encontrado. Usando lista padrão.")
        return [
            {"q": "Qual a capital da França?", "opts": ["Paris", "Londres", "Roma", "Berlim"], "ans": "Paris"}
        ]
    except Exception as e:
        logger.error(f"Erro ao
