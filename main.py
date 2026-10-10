# main.py
import logging
import threading
from database import init_db
from collector_agent import start_collector
from bot import start_bot, check_alerts, send_alerts_loop
from web import start_web

from telebot import apihelper

# === ПРОКСИ ДЛЯ TELEGRAM ===
# Раскомментируй ОДИН из вариантов:

# Вариант A: Если у тебя есть SOCKS5 прокси (например, от VPN-клиента)
# apihelper.proxy = {
#     'https': 'socks5://127.0.0.1:1080'
# }

# Вариант B: HTTP прокси (укажи свой)
# apihelper.proxy = {
#     'https': 'http://login:password@proxy-address:port'
# }

# Вариант C: Использовать системные прокси (если VPN системный)
import os
apihelper.proxy = {
    'https': os.environ.get('HTTPS_PROXY', '')
}
# =================================

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s | [ГЛАВНАЯ] | %(message)s",
    datefmt="%H:%M:%S"
)

def main():
    logging.info("🚀 Запуск AI-Sysadmin проекта...")
    
    # 1. Инициализируем базу данных
    init_db()
    logging.info("✅ База данных проверена и готова.")
    
    # 2. Запускаем сборщик метрик в фоне
    collector_thread = threading.Thread(target=start_collector, daemon=True)
    collector_thread.start()
    logging.info("🟢 Сборщик метрик работает в фоне.")
    
    # 3. Запускаем проверку алертов в фоне
    alert_checker_thread = threading.Thread(target=check_alerts, daemon=True)
    alert_checker_thread.start()
    logging.info("🔔 Проверка алертов запущена.")
    
    # 4. Запускаем отправку алертов в фоне
    alert_sender_thread = threading.Thread(target=send_alerts_loop, daemon=True)
    alert_sender_thread.start()
    logging.info(" Отправка алертов запущена.")
    
    # 5. Запускаем веб-дашборд в фоне
    web_thread = threading.Thread(target=start_web, daemon=True)
    web_thread.start()
    logging.info("🌐 Веб-дашборд запущен на http://localhost:8000")
    
    # 6. Запускаем Telegram-бота (в главном потоке)
    logging.info("🤖 Запуск Telegram-бота...")
    start_bot()

if __name__ == "__main__":
    main()