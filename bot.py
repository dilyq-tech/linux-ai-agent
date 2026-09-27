#!/usr/bin/env python3
"""
AI-Sysadmin: Telegram-бот для мульти-серверного мониторинга + управление Linux
"""

import sqlite3
import os
import time
import threading
import requests
import telebot
from telebot import apihelper
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
from config import BOT_TOKEN, ADMIN_ID
import manager
import full_control
from control_handlers import register_all_handlers
import log_analyzer

apihelper.proxy = {"https": "http://127.0.0.1:12334"}

DB_NAME = "monitoring.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"
LOG_FILE = "/tmp/log_analysis.txt"

DISK_THRESHOLD = 85
RAM_THRESHOLD = 90
CPU_THRESHOLD = 95
CHECK_INTERVAL = 300
SENDER_INTERVAL = 30

# Эмодзи как переменные
E_BOT = "\U0001F916"
E_CHART = "\U0001F4CA"
E_SEARCH = "\U0001F50D"
E_CLIP = "\U0001F4CB"
E_WARN = "\u26A0\uFE0F"
E_HELP = "\u2753"
E_CROSS = "\u274C"
E_GREEN = "\U0001F7E2"
E_YELLOW = "\U0001F7E1"
E_RED = "\U0001F534"
E_INBOX = "\U0001F4E5"
E_OUTBOX = "\U0001F4E4"
E_HOURGLASS = "\u23F3"
E_CHECK = "\u2705"
E_ROCKET = "\U0001F680"
E_GEAR = "\u2699\uFE0F"
E_PACKAGE = "\U0001F4E6"
E_GLOBE = "\U0001F310"
E_FOLDER = "\U0001F4C1"
E_FILE = "\U0001F4C4"
E_KILL = "\U0001F4A5"
E_WRENCH = "\U0001F527"

bot = telebot.TeleBot(BOT_TOKEN)
alert_state = {}


def get_status_emoji(value, threshold):
    if value >= threshold:
        return E_RED
    elif value >= threshold * 0.8:
        return E_YELLOW
    else:
        return E_GREEN


def init_queue():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            sent INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def queue_alert(text):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO alert_queue (text, created_at, sent) VALUES (?, ?, 0)",
                 (text, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"{E_INBOX} Алерт в очереди:", text)


def sender_loop():
    while True:
        try:
            conn = sqlite3.connect(DB_NAME)
            rows = conn.execute("SELECT id, text FROM alert_queue WHERE sent=0 ORDER BY id LIMIT 10").fetchall()
            conn.close()
            for rid, text in rows:
                bot.send_message(ADMIN_ID, text, parse_mode="HTML")
                conn = sqlite3.connect(DB_NAME)
                conn.execute("UPDATE alert_queue SET sent=1 WHERE id=?", (rid,))
                conn.commit()
                conn.close()
                print(f"{E_OUTBOX} Алерт доставлен:", text)
        except Exception:
            pass
        time.sleep(SENDER_INTERVAL)


def get_servers():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT server_name FROM metrics ORDER BY server_name")
    servers = [row[0] for row in cur.fetchall()]
    conn.close()
    return servers


def get_latest_metrics(server=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    if server:
        cur.execute("""
            SELECT timestamp, cpu_percent, memory_percent, disk_percent, server_name
            FROM metrics 
            WHERE server_name = ?
            ORDER BY id DESC LIMIT 1
        """, (server,))
    else:
        cur.execute("""
            SELECT timestamp, cpu_percent, memory_percent, disk_percent, server_name
            FROM metrics 
            ORDER BY id DESC LIMIT 1
        """)
    
    row = cur.fetchone()
    conn.close()
    return row


def create_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(f"{E_CHART} Статус"),
        KeyboardButton(f"{E_BOT} AI-анализ")
    )
    keyboard.add(
        KeyboardButton(f"{E_SEARCH} Логи"),
        KeyboardButton(f"{E_CLIP} Очередь")
    )
    keyboard.add(
        KeyboardButton(f"{E_WRENCH} Сервисы"),
        KeyboardButton(f"{E_GEAR} Процессы")
    )
    keyboard.add(
        KeyboardButton("🖥 Терминал"),
        KeyboardButton("👥 Пользователи")
    )
    keyboard.add(
        KeyboardButton("🐳 Docker"),
        KeyboardButton("🛡 Firewall")
    )
    keyboard.add(
        KeyboardButton("🌐 Сеть"),
        KeyboardButton("📶 Wi-Fi")
    )
    keyboard.add(
        KeyboardButton(f"{E_WARN} Тест алерта")
    )
    keyboard.add(
        KeyboardButton(f"{E_HELP} Справка")
    )
    return keyboard


@bot.message_handler(commands=["start"])
def cmd_start(message):
    welcome_text = (
        f"{E_BOT} <b>AI-Sysadmin — Центр управления Linux</b>\n\n"
        f"Я слежу за <b>несколькими серверами</b> и позволяю ими управлять.\n\n"
        f"<b>Мониторинг:</b>\n"
        f"{E_CHART} Метрики в реальном времени\n"
        f"{E_BOT} AI-анализ трендов и логов\n"
        f"{E_WARN} Автоматические алерты\n"
        f"{E_INBOX} Офлайн-очередь\n\n"
        f"<b>Управление:</b>\n"
        f"{E_WRENCH} Сервисы systemd\n"
        f"{E_GEAR} Процессы\n"
        f"{E_PACKAGE} Пакеты\n"
        f"{E_GLOBE} Сеть\n"
        f"{E_FOLDER} Файлы\n\n"
        f"<b>Используй кнопки или команды:</b>"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML", reply_markup=create_main_keyboard())


@bot.message_handler(commands=["status"])
@bot.message_handler(func=lambda message: message.text == f"{E_CHART} Статус")
def cmd_status(message):
    servers = get_servers()
    
    if not servers:
        bot.reply_to(message, f"{E_CROSS} База пуста. Проверь сервисы collector")
        return
    
    status_text = f"{E_CHART} <b>Статус серверов</b>\n\n"
    
    for server in servers:
        row = get_latest_metrics(server)
        if row:
            ts, cpu, ram, disk, srv_name = row
            
            cpu_emoji = get_status_emoji(cpu, CPU_THRESHOLD)
            ram_emoji = get_status_emoji(ram, RAM_THRESHOLD)
            disk_emoji = get_status_emoji(disk, DISK_THRESHOLD)
            
            status_text += f"<b>{srv_name}</b> ({ts[11:16]}):\n"
            status_text += f"  {cpu_emoji} CPU: {cpu:.1f}%\n"
            status_text += f"  {ram_emoji} RAM: {ram:.1f}%\n"
            status_text += f"  {disk_emoji} Disk: {disk:.1f}%\n\n"
    
    bot.send_message(message.chat.id, status_text, parse_mode="HTML")


@bot.message_handler(commands=["trend"])
@bot.message_handler(func=lambda message: message.text == f"{E_BOT} AI-анализ")
def cmd_trend(message):
    bot.reply_to(message, f"{E_BOT} Анализирую тренды через AI... (10-20 сек)")
    
    servers = get_servers()
    if not servers:
        bot.reply_to(message, f"{E_INBOX} База пуста. Проверь сервисы collector")
        return
    
    all_history = []
    for server in servers:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp, cpu_percent, memory_percent, disk_percent, server_name
            FROM metrics 
            WHERE server_name = ?
            ORDER BY id DESC LIMIT 10
        """, (server,))
        rows = cur.fetchall()
        conn.close()
        
        if rows:
            rows.reverse()
            for ts, cpu, ram, disk, srv in rows:
                all_history.append(f"{srv} | {ts[11:16]} | CPU: {cpu}% | RAM: {ram}% | Disk: {disk}%")
    
    if not all_history:
        bot.reply_to(message, f"{E_INBOX} База пуста. Проверь сервисы collector")
        return
    
    history = "\n".join(all_history[-20:])
    
    prompt = ("Ты AI-аналитик мониторинга серверов. Кратко проанализируй метрики нескольких серверов:\n\n"
              + history +
              "\n\nОтветь ОЧЕНЬ кратко на русском (3-4 предложения): есть ли проблемы, общее состояние, рекомендации.")
    
    try:
        print(f"🤖 Отправляю запрос к Ollama...")
        payload = {"model": MODEL, "prompt": prompt, "stream": False}
        r = requests.post(OLLAMA_URL, json=payload, timeout=120, proxies={"http": None, "https": None})
        print(f"📥 Ответ от Ollama: status={r.status_code}")
        if r.status_code != 200:
            analysis = f" Ollama вернул ошибку: {r.status_code}"
        else:
            try:
                data = r.json()
                analysis = data.get("response", "")
                print(f"✅ AI ответил: {len(analysis)} символов")
                if not analysis:
                    analysis = "AI не вернул ответ"
            except ValueError as e:
                print(f"❌ JSON parse error: {e}")
                print(f"Response text: {r.text[:200]}")
                analysis = f"❌ Ollama вернул некорректный JSON: {str(e)}"
    except requests.exceptions.ConnectionError as e:
        print(f"❌ ConnectionError: {e}")
        analysis = "🔴 Ollama не запущен. Выполни: ollama serve"
    except requests.exceptions.Timeout as e:
        print(f"⏳ Timeout: {e}")
        analysis = "⏳ AI думает слишком долго. Попробуй позже."
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {e}")
        analysis = f"❌ Ошибка AI: {str(e)}"
    
    trend_text = f"{E_BOT} <b>AI-анализ трендов</b>\n\n{analysis}"
    bot.send_message(message.chat.id, trend_text, parse_mode="HTML")


@bot.message_handler(commands=["logs"])
@bot.message_handler(func=lambda message: message.text == f"{E_SEARCH} Логи")
def cmd_logs(message):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            content = f.read()
        if content.strip():
            log_text = f"{E_SEARCH} <b>Анализ системных логов</b>\n\n{content[:1500]}"
            bot.send_message(message.chat.id, log_text, parse_mode="HTML")
        else:
            bot.reply_to(message, f"{E_HOURGLASS} Файл анализа пуст. Подожди 10 минут.")
    else:
        bot.reply_to(message, f"{E_SEARCH} Анализ логов ещё не запускался. Подожди 10 минут.")


@bot.message_handler(commands=["services"])
@bot.message_handler(func=lambda message: message.text == f"{E_WRENCH} Сервисы")
def cmd_services(message):
    bot.reply_to(message, f"{E_WRENCH} Загружаю список сервисов...")
    
    services = manager.LinuxManager.list_services(15)
    
    if 'error' in services[0]:
        bot.send_message(message.chat.id, f"{E_CROSS} Ошибка: {services[0]['error']}")
        return
    
    text = f"{E_WRENCH} <b>Системные сервисы</b>\n\n"
    for s in services[:10]:
        status_emoji = E_GREEN if s['active'] == 'active' else E_RED
        text += f"{status_emoji} <b>{s['name']}</b>\n"
        text += f"   Статус: {s['active']} ({s['sub']})\n"
        text += f"   {s['description'][:50]}\n\n"
    
    text += "\n<i>Используй /service_status &lt;имя&gt; для деталей</i>"
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["service_status"])
def cmd_service_status(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, f"{E_CROSS} Использование: /service_status &lt;имя_сервиса&gt;\n\nПример: /service_status ssh")
        return
    
    service_name = args[1]
    bot.reply_to(message, f"⏳ Проверяю статус {service_name}...")
    
    status = manager.LinuxManager.service_status(service_name)
    
    if 'error' in status:
        bot.send_message(message.chat.id, f"{E_CROSS} {status['error']}")
        return
    
    text = f"🔧 <b>Статус сервиса: {status['name']}</b>\n\n"
    text += f"Статус: {'🟢 Активен' if status['status'] == 'active' else '🔴 Неактивен'}\n\n"
    text += f"<pre>{status['output'][:500]}</pre>"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["processes"])
@bot.message_handler(func=lambda message: message.text == f"{E_GEAR} Процессы")
def cmd_processes(message):
    bot.reply_to(message, f"{E_GEAR} Загружаю список процессов...")
    
    processes = manager.LinuxManager.top_processes(15)
    
    if 'error' in processes[0]:
        bot.send_message(message.chat.id, f"{E_CROSS} Ошибка: {processes[0]['error']}")
        return
    
    text = f"{E_GEAR} <b>Топ процессов по CPU</b>\n\n"
    for p in processes[:10]:
        text += f"🔹 PID <b>{p['pid']}</b>\n"
        text += f"   CPU: {p['cpu']}% | RAM: {p['mem']}%\n"
        text += f"   {p['command'][:60]}\n\n"
    
    text += "\n<i>Используй /kill &lt;PID&gt; для завершения процесса</i>"
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["kill"])
def cmd_kill(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, f"{E_CROSS} Использование: /kill &lt;PID&gt;\n\nПример: /kill 1234")
        return
    
    try:
        pid = int(args[1])
    except ValueError:
        bot.reply_to(message, f"{E_CROSS} PID должен быть числом")
        return
    
    bot.reply_to(message, f"⏳ Завершаю процесс {pid}...")
    
    result = manager.LinuxManager.kill_process(pid)
    
    if 'error' in result:
        bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
        return
    
    emoji = E_CHECK if result['success'] else E_CROSS
    text = f"{emoji} <b>Процесс {pid}</b>\n\n"
    text += f"Сигнал: {result['signal']}\n"
    text += f"Успешно: {result['success']}"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["packages"])
def cmd_packages(message):
    args = message.text.split()
    search = args[1] if len(args) > 1 else None
    
    bot.reply_to(message, f"{E_PACKAGE} Загружаю список пакетов...")
    
    packages = manager.LinuxManager.list_packages(search, 20)
    
    if 'error' in packages[0]:
        bot.send_message(message.chat.id, f"{E_CROSS} Ошибка: {packages[0]['error']}")
        return
    
    text = f"{E_PACKAGE} <b>Установленные пакеты</b>"
    if search:
        text += f" (поиск: {search})"
    text += "\n\n"
    
    for pkg in packages[:15]:
        status_emoji = E_CHECK if pkg['status'] == 'ii' else ""
        text += f"{status_emoji} <b>{pkg['name']}</b>\n"
        text += f"   Версия: {pkg['version']}\n"
        text += f"   {pkg['description'][:50]}\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["network"])
def cmd_network(message):
    bot.reply_to(message, f"{E_GLOBE} Загружаю сетевую информацию...")
    
    net_info = manager.LinuxManager.network_info()
    
    if 'error' in net_info:
        bot.send_message(message.chat.id, f"{E_CROSS} {net_info['error']}")
        return
    
    text = f"{E_GLOBE} <b>Сетевая информация</b>\n\n"
    text += "<b>Интерфейсы:</b>\n"
    text += f"<pre>{net_info['interfaces'][:500]}</pre>\n\n"
    text += "<b>Открытые порты:</b>\n"
    text += f"<pre>{net_info['listening_ports'][:500]}</pre>"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["dir"])
def cmd_dir(message):
    args = message.text.split()
    path = args[1] if len(args) > 1 else '/home'
    
    bot.reply_to(message, f"⏳ Загружаю содержимое {path}...")
    
    result = manager.LinuxManager.list_directory(path)
    
    if 'error' in result:
        bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
        return
    
    text = f"{E_FOLDER} <b>Содержимое {path}</b>\n\n"
    text += f"<pre>{result['content'][:1000]}</pre>"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["read"])
def cmd_read(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, f"{E_CROSS} Использование: /read &lt;путь_к_файлу&gt;\n\nПример: /read /var/log/syslog")
        return
    
    path = args[1]
    bot.reply_to(message, f"⏳ Читаю {path}...")
    
    result = manager.LinuxManager.read_file(path, 50)
    
    if 'error' in result:
        bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
        return
    
    text = f"{E_FILE} <b>Файл: {path}</b>\n\n"
    text += f"<pre>{result['content'][:1500]}</pre>"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["test_alert"])
@bot.message_handler(func=lambda message: message.text == f"{E_WARN} Тест алерта")
def cmd_test_alert(message):
    queue_alert(f"{E_WARN} <b>ТЕСТОВЫЙ АЛЕРТ:</b> диск заполнен на 93%! (проверка очереди)")
    bot.reply_to(message, f"{E_CHECK} Алерт положен в очередь. Доставка в течение 30 сек.")


@bot.message_handler(commands=["queue"])
@bot.message_handler(func=lambda message: message.text == f"{E_CLIP} Очередь")
def cmd_queue(message):
    conn = sqlite3.connect(DB_NAME)
    total = conn.execute("SELECT COUNT(*) FROM alert_queue").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM alert_queue WHERE sent=0").fetchone()[0]
    conn.close()
    
    queue_text = (
        f"{E_CLIP} <b>Очередь алертов</b>\n\n"
        f"{E_CHART} Всего за всё время: <b>{total}</b>\n"
        f"{E_HOURGLASS} Ожидают отправки: <b>{pending}</b>\n"
        f"{E_CHECK} Доставлено: <b>{total - pending}</b>"
    )
    bot.send_message(message.chat.id, queue_text, parse_mode="HTML")


@bot.message_handler(commands=["help"])
@bot.message_handler(func=lambda message: message.text == f"{E_HELP} Справка")
def cmd_help(message):
    help_text = (
        f"{E_HELP} <b>Справка по боту</b>\n\n"
        f"<b>Мониторинг:</b>\n"
        f"{E_CHART} /status — статус всех серверов\n"
        f"{E_BOT} /trend — AI-анализ трендов\n"
        f"{E_SEARCH} /logs — анализ системных логов\n\n"
        f"<b>Управление:</b>\n"
        f"{E_WRENCH} /services — список сервисов\n"
        f"/service_status &lt;имя&gt; — статус сервиса\n"
        f"{E_GEAR} /processes — топ процессов\n"
        f"{E_KILL} /kill &lt;PID&gt; — завершить процесс\n"
        f"{E_PACKAGE} /packages — установленные пакеты\n"
        f"{E_GLOBE} /network — сетевая информация\n"
        f"{E_FOLDER} /dir &lt;путь&gt; — содержимое директории\n"
        f"{E_FILE} /read &lt;путь&gt; — прочитать файл\n\n"
        f"<b>Полное управление:</b>\n"
        f"🖥 /cmd &lt;команда&gt; — выполнить команду\n"
        f"👥 /users — список пользователей\n"
        f"🐳 /docker — управление контейнерами\n"
        f"🛡 /firewall — управление фаерволом\n"
        f"🔄 /updates — проверка и установка обновлений\n"
        f"💾 /backup &lt;путь&gt; — создать резервную копию\n\n"
        f"<b>Алерты:</b>\n"
        f"{E_WARN} /test_alert — тестовый алерт\n"
        f"{E_CLIP} /queue — состояние очереди\n\n"
        f"<b>Алерты срабатывают когда:</b>\n"
        f"{E_RED} Диск > 85%\n"
        f"{E_RED} RAM > 90%\n"
        f"{E_RED} CPU > 95%\n"
        f"{E_WARN} Collector молчит > 15 минут\n\n"
        f"<b>Особенности:</b>\n"
        f"{E_INBOX} Без сети алерты НЕ теряются — они ждут в очереди\n"
        f"{E_BOT} AI анализирует тренды и логи на аномалии"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="HTML")


def alert_checker():
    while True:
        time.sleep(CHECK_INTERVAL)
        
        servers = get_servers()
        for server in servers:
            row = get_latest_metrics(server)
            if not row:
                continue
            
            ts, cpu, ram, disk, srv_name = row
            
            try:
                last_time = datetime.fromisoformat(ts)
                age_min = (datetime.now() - last_time).total_seconds() / 60
            except Exception:
                age_min = 0
            
            key = f"{srv_name}_collector"
            if age_min > 15 and not alert_state.get(key, False):
                queue_alert(f"{E_WARN} <b>{srv_name}:</b> нет свежих метрик {int(age_min)} мин")
                alert_state[key] = True
            elif age_min <= 15:
                alert_state[key] = False
            
            key = f"{srv_name}_disk"
            if disk >= DISK_THRESHOLD and not alert_state.get(key, False):
                queue_alert(f"{E_RED} <b>{srv_name}:</b> ДИСК заполнен на {disk:.1f}%!")
                alert_state[key] = True
            elif disk < DISK_THRESHOLD:
                alert_state[key] = False
            
            key = f"{srv_name}_ram"
            if ram >= RAM_THRESHOLD and not alert_state.get(key, False):
                queue_alert(f"{E_RED} <b>{srv_name}:</b> RAM загружена на {ram:.1f}%!")
                alert_state[key] = True
            elif ram < RAM_THRESHOLD:
                alert_state[key] = False
            
            key = f"{srv_name}_cpu"
            if cpu >= CPU_THRESHOLD and not alert_state.get(key, False):
                queue_alert(f"{E_RED} <b>{srv_name}:</b> CPU загружен на {cpu:.1f}%!")
                alert_state[key] = True
            elif cpu < CPU_THRESHOLD:
                alert_state[key] = False



# Регистрируем команды полного управления
E_SHIELD = "\U0001F6E1\uFE0F"
E_DOCKER = "\U0001F433"
E_DISK = "\U0001F4BF"

register_all_handlers(
    bot,
    E_CROSS, E_CHECK, E_WARN, E_GEAR, E_FOLDER,
    E_GLOBE, E_PACKAGE, E_SHIELD, E_DOCKER, E_DISK
)









if __name__ == "__main__":
    print(f"{E_ROCKET} Telegram-бот для мульти-серверного мониторинга запущен!")
    init_queue()
    threading.Thread(target=alert_checker, daemon=True).start()
    threading.Thread(target=sender_loop, daemon=True).start()
    bot.infinity_polling()
