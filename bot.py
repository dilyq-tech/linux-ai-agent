#!/usr/bin/env python3
"""
AI-Sysadmin: Telegram-бот с авто-алертами и офлайн-очередью
Без сети алерты копятся в SQLite, при появлении сети (VPN) доставляются сами
"""

import sqlite3
import os
import time
import threading
import requests
import telebot
from telebot import apihelper
from datetime import datetime
from config import BOT_TOKEN, ADMIN_ID

apihelper.proxy = {"https": "http://127.0.0.1:12334"}

DB_NAME = "monitoring.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

DISK_THRESHOLD = 85
RAM_THRESHOLD = 90
CPU_THRESHOLD = 95
CHECK_INTERVAL = 300     # проверка метрик: 5 минут
SENDER_INTERVAL = 30    # попытка отправить очередь: 30 секунд

bot = telebot.TeleBot(BOT_TOKEN)
alert_state = {"disk": False, "ram": False, "cpu": False, "collector": False}


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
    """Положить алерт в очередь (работает без сети)"""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO alert_queue (text, created_at, sent) VALUES (?, ?, 0)",
                 (text, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print("📥 Алерт в очереди:", text)


def sender_loop():
    """Фоновый поток: пытается отправить очередь каждые 30 сек"""
    while True:
        try:
            conn = sqlite3.connect(DB_NAME)
            rows = conn.execute("SELECT id, text FROM alert_queue WHERE sent=0 ORDER BY id LIMIT 10").fetchall()
            conn.close()
            for rid, text in rows:
                bot.send_message(ADMIN_ID, text)
                conn = sqlite3.connect(DB_NAME)
                conn.execute("UPDATE alert_queue SET sent=1 WHERE id=?", (rid,))
                conn.commit()
                conn.close()
                print("📤 Алерт доставлен:", text)
        except Exception:
            pass  # сети нет — попробуем через 30 сек
        time.sleep(SENDER_INTERVAL)


def get_latest_metrics():
    if not os.path.exists(DB_NAME):
        return None
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT timestamp, cpu_percent, memory_percent, disk_percent FROM metrics ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row


def get_recent_history(limit=10):
    if not os.path.exists(DB_NAME):
        return None
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT timestamp, cpu_percent, memory_percent, disk_percent FROM metrics ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    rows.reverse()
    lines = []
    for ts, cpu, ram, disk in rows:
        lines.append(ts[11:16] + " | CPU: " + str(cpu) + "% | RAM: " + str(ram) + "% | Disk: " + str(disk) + "%")
    return "\n".join(lines)


def ask_ollama(prompt):
    try:
        payload = {"model": MODEL, "prompt": prompt, "stream": False}
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        return r.json()["response"]
    except Exception as e:
        return "Ошибка связи с AI: " + str(e)


@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.reply_to(message,
        "AI-Sysadmin бот запущен!\n\n"
        "Я слежу за сервером даже офлайн: алерты копятся в очереди "
        "и приходят, как только появляется сеть.\n\n"
        "Команды:\n"
        "/status - текущие метрики\n"
        "/trend - AI-анализ трендов\n"
        "/test_alert - тестовый алерт\n"
        "/queue - состояние очереди алертов\n"
        "/help - справка")


@bot.message_handler(commands=["status"])
def cmd_status(message):
    row = get_latest_metrics()
    if not row:
        bot.reply_to(message, "База пуста. Проверь сервис collector")
        return
    ts, cpu, ram, disk = row
    bot.reply_to(message,
        "Статус сервера (данные от " + ts[11:16] + "):\n\n"
        "CPU: " + str(cpu) + "%\n"
        "RAM: " + str(ram) + "%\n"
        "Disk: " + str(disk) + "%\n\n"
        "Для AI-анализа трендов напиши /trend")


@bot.message_handler(commands=["trend"])
def cmd_trend(message):
    bot.reply_to(message, "Анализирую тренды через AI... (10-20 сек)")
    history = get_recent_history(10)
    if not history:
        bot.reply_to(message, "База пуста. Проверь сервис collector")
        return
    prompt = ("Ты AI-аналитик мониторинга сервера. Кратко проанализируй метрики:\n\n"
              + history +
              "\n\nОтветь ОЧЕНЬ кратко на русском (3-4 предложения): опасные тренды, общее состояние, одна рекомендация.")
    analysis = ask_ollama(prompt)
    bot.send_message(message.chat.id, "AI-анализ трендов:\n\n" + analysis)


@bot.message_handler(commands=["test_alert"])
def cmd_test_alert(message):
    queue_alert("⚠️ ТЕСТОВЫЙ АЛЕРТ: диск заполнен на 93%! (проверка очереди)")
    bot.reply_to(message, "Алерт положен в очередь. Доставка в течение 30 сек, если есть сеть.")


@bot.message_handler(commands=["queue"])
def cmd_queue(message):
    conn = sqlite3.connect(DB_NAME)
    total = conn.execute("SELECT COUNT(*) FROM alert_queue").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM alert_queue WHERE sent=0").fetchone()[0]
    conn.close()
    bot.reply_to(message,
        "Очередь алертов:\n"
        "Всего за всё время: " + str(total) + "\n"
        "Ожидают отправки: " + str(pending))


@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.reply_to(message,
        "Справка:\n"
        "/status - текущие метрики\n"
        "/trend - AI-анализ трендов\n"
        "/test_alert - тестовый алерт\n"
        "/queue - состояние очереди\n\n"
        "Алерты срабатывают когда:\n"
        "диск > 85%, RAM > 90%, CPU > 95%\n"
        "или collector молчит > 15 минут\n\n"
        "Без сети алерты НЕ теряются — они ждут в очереди.")


def alert_checker():
    """Фоновый поток: проверяет метрики и кладет алерты в очередь"""
    while True:
        time.sleep(CHECK_INTERVAL)
        row = get_latest_metrics()
        if not row:
            continue
        ts, cpu, ram, disk = row

        try:
            last_time = datetime.fromisoformat(ts)
            age_min = (datetime.now() - last_time).total_seconds() / 60
        except Exception:
            age_min = 0

        if age_min > 15 and not alert_state["collector"]:
            queue_alert("⚠️ Collector не работает: нет свежих метрик " + str(int(age_min)) + " мин")
            alert_state["collector"] = True
        elif age_min <= 15:
            alert_state["collector"] = False

        if disk >= DISK_THRESHOLD and not alert_state["disk"]:
            queue_alert("⚠️ ДИСК заполнен на " + str(disk) + "%! Порог: " + str(DISK_THRESHOLD) + "%")
            alert_state["disk"] = True
        elif disk < DISK_THRESHOLD:
            alert_state["disk"] = False

        if ram >= RAM_THRESHOLD and not alert_state["ram"]:
            queue_alert("⚠️ RAM загружена на " + str(ram) + "%! Порог: " + str(RAM_THRESHOLD) + "%")
            alert_state["ram"] = True
        elif ram < RAM_THRESHOLD:
            alert_state["ram"] = False

        if cpu >= CPU_THRESHOLD and not alert_state["cpu"]:
            queue_alert("⚠️ CPU загружен на " + str(cpu) + "%! Порог: " + str(CPU_THRESHOLD) + "%")
            alert_state["cpu"] = True
        elif cpu < CPU_THRESHOLD:
            alert_state["cpu"] = False


if __name__ == "__main__":
    print("🚀 Telegram-бот с офлайн-очередью запущен!")
    init_queue()
    threading.Thread(target=alert_checker, daemon=True).start()
    threading.Thread(target=sender_loop, daemon=True).start()
    bot.infinity_polling()
