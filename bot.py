# bot.py
import os
import time
import html
import logging
import subprocess
from datetime import datetime

import psutil
import telebot
from telebot import apihelper, types

from config import (BOT_TOKEN, ADMIN_ID, CPU_THRESHOLD, RAM_THRESHOLD,
                    DISK_THRESHOLD, ALERT_CHECK_INTERVAL, ALERT_SEND_INTERVAL)
from database import (get_latest_metrics, get_metrics_history, get_all_servers,
                      queue_alert, get_unsent_alerts, mark_alert_sent,
                      purge_stale_servers)
from ai_analyzer import analyze_metrics
from log_searcher import find_errors_in_logs, get_auth_summary

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | [БОТ] | %(message)s",
                    datefmt="%H:%M:%S")

# === ПРОКСИ (Тройная страховка для твоего VPN) ===
PROXY = "http://127.0.0.1:12334"
os.environ["http_proxy"] = PROXY
os.environ["https_proxy"] = PROXY
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)
apihelper.proxy = {"https": PROXY, "http": PROXY}
try:
    _sess = apihelper._get_req_session()
    _sess.trust_env = False
    _sess.proxies.update({"https": PROXY, "http": PROXY})
except Exception as _e:
    logging.warning(f"Не удалось настроить сессию: {_e}")
logging.info(f"Прокси для Telegram: {PROXY}")

bot = telebot.TeleBot(BOT_TOKEN)
alert_state = {}
_net_prev = {"sent": 0, "recv": 0, "time": 0.0}


# === ФОНОВЫЕ ПОТОКИ ===

def check_alerts():
    while True:
        try:
            for server in get_all_servers():
                m = get_latest_metrics(server)
                if not m:
                    continue
                checks = [
                    (f"{server}_cpu", m['cpu_percent'] >= CPU_THRESHOLD,
                     f"⚠️ <b>{server}:</b> CPU {m['cpu_percent']}%"),
                    (f"{server}_ram", m['ram_percent'] >= RAM_THRESHOLD,
                     f"⚠️ <b>{server}:</b> RAM {m['ram_percent']}%"),
                    (f"{server}_disk", m['disk_percent'] >= DISK_THRESHOLD,
                     f"🔴 <b>{server}:</b> Disk {m['disk_percent']}%"),
                ]
                for key, triggered, text in checks:
                    if triggered and not alert_state.get(key, False):
                        queue_alert(text)
                        alert_state[key] = True
                    elif not triggered:
                        alert_state[key] = False
        except Exception as e:
            logging.error(f"Ошибка проверки алертов: {e}")
        time.sleep(ALERT_CHECK_INTERVAL)


def send_alerts_loop():
    while True:
        try:
            for alert in get_unsent_alerts(limit=10):
                bot.send_message(ADMIN_ID, alert['text'], parse_mode="HTML")
                mark_alert_sent(alert['id'])
        except Exception as e:
            logging.error(f"Ошибка отправки алертов: {e}")
        time.sleep(ALERT_SEND_INTERVAL)


# === СБОР ДАННЫХ ===

def _procs_text():
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_percent']):
        try:
            procs.append((p.info['memory_percent'] or 0.0,
                          p.info['pid'], p.info['name'] or '?'))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(reverse=True)
    lines = [f"{i+1}. {name} (PID {pid}) — RAM {ram:.1f}%"
             for i, (ram, pid, name) in enumerate(procs[:8])]
    return "⚙️ <b>Топ процессов по RAM:</b>\n<pre>" + \
        html.escape("\n".join(lines)) + "</pre>"


def _net_text():
    now = time.time()
    net = psutil.net_io_counters()
    global _net_prev
    if _net_prev["time"]:
        dt = max(now - _net_prev["time"], 1e-6)
        up = (net.bytes_sent - _net_prev["sent"]) / dt / 1024
        down = (net.bytes_recv - _net_prev["recv"]) / dt / 1024
        speed = f"⬆️ {up:.1f} KB/s | ⬇️ {down:.1f} KB/s"
    else:
        speed = "⏳ Нажми кнопку ещё раз через пару секунд"
    _net_prev = {"sent": net.bytes_sent, "recv": net.bytes_recv, "time": now}
    return (f"🌐 <b>Сеть:</b>\n{speed}\n"
            f"Всего отправлено: {net.bytes_sent // 1048576} MB\n"
            f"Всего получено: {net.bytes_recv // 1048576} MB")


def _sysinfo_text():
    load = os.getloadavg()
    with open('/proc/uptime') as f:
        up = float(f.read().split()[0])
    days, rem = int(up // 86400), int(up % 86400)
    hours, mins = rem // 3600, rem % 3600 // 60
    boot = datetime.fromtimestamp(psutil.boot_time()).strftime('%d.%m.%Y %H:%M')
    return (f"⏱ <b>Система:</b>\n"
            f"Аптайм: {days}д {hours}ч {mins}м\n"
            f"Load Average: {load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}\n"
            f"Загружена: {boot}\n"
            f"Ядер CPU: {psutil.cpu_count()}")


# === ВСПОМОГАТЕЛЬНЫЕ ===

def _is_admin(message):
    return message.chat.id == ADMIN_ID


def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("📊 Статус"),
        types.KeyboardButton("🧠 AI-анализ"),
        types.KeyboardButton("🖥 Серверы"),
        types.KeyboardButton("⚙️ Процессы"),
        types.KeyboardButton("🌐 Сеть"),
        types.KeyboardButton("⏱ Система"),
        types.KeyboardButton("🔍 Ошибки"),
        types.KeyboardButton("🛡️ Авторизация"),
        types.KeyboardButton("📜 Логи"),
        types.KeyboardButton("🔧 Сервисы"),
        types.KeyboardButton("🧹 Чистка БД"),
    )
    return kb


# === КОМАНДЫ ===

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    if not _is_admin(message):
        return
    bot.send_message(
        message.chat.id,
        "🤖 <b>AI-Sysadmin Bot</b>\n\n"
        "📊 Статус — метрики серверов\n"
        "🧠 AI-анализ — анализ трендов через Qwen\n"
        "🖥 Серверы — список серверов\n"
        "⚙️ Процессы — топ по RAM\n"
        "🌐 Сеть — трафик и скорость\n"
        "⏱ Система — аптайм и нагрузка\n"
        "🔍 Ошибки — поиск в системных логах\n"
        "🛡️ Авторизация — попытки входа\n"
        "📜 Логи — последние логи сервиса\n"
        "🔧 Сервисы — активные службы Linux\n"
        "🧹 Чистка БД — удалить старые серверы",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=['status'])
def cmd_status(message):
    if not _is_admin(message):
        return
    try:
        servers = get_all_servers()
        if not servers:
            bot.send_message(message.chat.id, "Нет данных о серверах.")
            return
        text = "📊 <b>Статус серверов:</b>\n\n"
        for server in servers:
            m = get_latest_metrics(server)
            if m:
                ts = m['timestamp'][:19].replace('T', ' ').split('.')[0]
                text += (f"🖥 <b>{server}</b>\n"
                         f"   CPU: {m['cpu_percent']}%\n"
                         f"   RAM: {m['ram_percent']}%\n"
                         f"   Disk: {m['disk_percent']}%\n"
                         f"   Обновлено: {ts}\n\n")
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка статуса: {e}")


@bot.message_handler(commands=['ai'])
def cmd_ai(message):
    if not _is_admin(message):
        return
    try:
        servers = get_all_servers()
        if not servers:
            bot.send_message(message.chat.id, "Нет данных для анализа.")
            return
        bot.send_message(message.chat.id, "🧠 Анализирую тренды (10-20 сек)...")
        history = get_metrics_history(servers[0], limit=10)
        analysis = analyze_metrics(history)
        bot.send_message(message.chat.id,
                         f"🧠 <b>AI-анализ ({servers[0]}):</b>\n\n{analysis}",
                         parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка AI: {e}")


@bot.message_handler(commands=['servers'])
def cmd_servers(message):
    if not _is_admin(message):
        return
    servers = get_all_servers()
    text = "🖥 <b>Серверы:</b>\n\n" + "\n".join(f"• {s}" for s in servers) \
        if servers else "Нет серверов в базе."
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=['procs'])
def cmd_procs(message):
    if _is_admin(message):
        bot.send_message(message.chat.id, _procs_text(), parse_mode="HTML")


@bot.message_handler(commands=['net'])
def cmd_net(message):
    if _is_admin(message):
        bot.send_message(message.chat.id, _net_text(), parse_mode="HTML")


@bot.message_handler(commands=['sysinfo'])
def cmd_sysinfo(message):
    if _is_admin(message):
        bot.send_message(message.chat.id, _sysinfo_text(), parse_mode="HTML")


@bot.message_handler(commands=['errors'])
def cmd_errors(message):
    if not _is_admin(message):
        return
    try:
        errors = find_errors_in_logs()
        text = "🔍 <b>Последние ошибки в системе:</b>\n\n"
        text += "\n".join(errors[:15])
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['auth'])
def cmd_auth(message):
    if not _is_admin(message):
        return
    try:
        summary = get_auth_summary()
        bot.send_message(message.chat.id, summary, parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['purge'])
def cmd_purge(message):
    if not _is_admin(message):
        return
    deleted = purge_stale_servers(hours=24)
    bot.send_message(message.chat.id, f"🧹 Удалено старых записей: {deleted}")


@bot.message_handler(commands=['logs'])
def cmd_logs(message):
    if not _is_admin(message):
        return
    try:
        out = subprocess.run(
            ["journalctl", "-u", "ai-sysadmin", "-n", "15", "--no-pager"],
            capture_output=True, text=True, timeout=10)
        logs = out.stdout or out.stderr or "Логи пусты"
        bot.send_message(message.chat.id,
                         f"📜 <b>Последние логи:</b>\n<pre>{html.escape(logs[-3000:])}</pre>",
                         parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка логов: {e}")


@bot.message_handler(commands=['services'])
def cmd_services(message):
    if not _is_admin(message):
        return
    try:
        out = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=running",
             "--no-pager", "--no-legend"],
            capture_output=True, text=True, timeout=10)
        lines = out.stdout.strip().splitlines()[:15]
        text = "\n".join(line[:60] for line in lines)
        bot.send_message(message.chat.id,
                         f"🔧 <b>Активные сервисы:</b>\n<pre>{html.escape(text)}</pre>",
                         parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка сервисов: {e}")


# === ОБРАБОТЧИК НИЖНИХ КНОПОК ===

@bot.message_handler(func=lambda message: message.text in [
    "📊 Статус", "🧠 AI-анализ", "🖥 Серверы", "⚙️ Процессы",
    "🌐 Сеть", "⏱ Система", "🔍 Ошибки", "🛡️ Авторизация",
    "📜 Логи", "🔧 Сервисы", "🧹 Чистка БД"
])
def handle_reply_button(message):
    """Обработчик кнопок reply-клавиатуры (снизу экрана)"""
    text = message.text
    if text == "📊 Статус":
        cmd_status(message)
    elif text == "🧠 AI-анализ":
        cmd_ai(message)
    elif text == "🖥 Серверы":
        cmd_servers(message)
    elif text == "⚙️ Процессы":
        bot.send_message(message.chat.id, _procs_text(), parse_mode="HTML")
    elif text == "🌐 Сеть":
        bot.send_message(message.chat.id, _net_text(), parse_mode="HTML")
    elif text == "⏱ Система":
        bot.send_message(message.chat.id, _sysinfo_text(), parse_mode="HTML")
    elif text == "🔍 Ошибки":
        cmd_errors(message)
    elif text == "🛡️ Авторизация":
        cmd_auth(message)
    elif text == "📜 Логи":
        cmd_logs(message)
    elif text == "🔧 Сервисы":
        cmd_services(message)
    elif text == "🧹 Чистка БД":
        cmd_purge(message)


# === ЗАПУСК ===

def start_bot():
    logging.info("Запуск Telegram-бота...")
    bot.infinity_polling()