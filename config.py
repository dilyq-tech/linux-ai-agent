# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# === Telegram ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8437247566:AAH0kFGk-9dpv7kQ4_euZIa0Ipe-Sq7UclM")
ADMIN_ID = int(os.getenv("ADMIN_ID", "2052437952"))

# === База данных ===
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitoring.db")

# === Интервалы ===
METRICS_INTERVAL = 60  # Секунды между замерами
ALERT_CHECK_INTERVAL = 300  # Проверка алертов каждые 5 минут
ALERT_SEND_INTERVAL = 30  # Отправка алертов каждые 30 сек

# === Пороги алертов ===
CPU_THRESHOLD = 90.0
RAM_THRESHOLD = 90.0
DISK_THRESHOLD = 85.0

# === Ollama AI ===
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:3b"

# === Имя сервера ===
SERVER_NAME = os.getenv("SERVER_NAME", "home-server")