#!/usr/bin/env python3
"""
AI-Sysadmin: Telegram-бот для мульти-серверного мониторинга
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

bot = telebot.TeleBot(BOT_TOKEN)
alert_state = {}


def get_status_emoji(value, threshold):
    if value >= threshold:
        return chr(0x1F534)
    elif value >= threshold * 0.8:
        return chr(0x1F7E1)
    else:
        return chr(0x1F7E2)


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
    print(chr(0x1F4E5) + " Алерт в очереди:", text)


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
                print(chr(0x1F4E4) + " Алерт доставлен:", text)
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
        KeyboardButton(chr(0x1F4CA) + " Статус"),
        KeyboardButton(chr(0x1F916) + " AI-анализ")
    )
    keyboard.add(
        KeyboardButton(chr(0x1F50D) + " Логи"),
        KeyboardButton(chr(0x1F4CB) + " Очередь")
    )
    keyboard.add(
        KeyboardButton(chr(0x26A0) + chr(0xFE0F) + " Тест алерта"),
        KeyboardButton(chr(0x2753) + " Справка")
    )
    return keyboard


@bot.message_handler(commands=["start"])
def cmd_start(message):
    welcome_text = (
        chr(0x1F916) + " <b>AI-Sysadmin бот запущен!</b>\n\n"
        "Я слежу за <b>несколькими серверами</b> и сам пишу, если что-то сломалось.\n\n"
        "<b>Возможности:</b>\n"
        chr(0x1F4CA) + " Мониторинг метрик в реальном времени\n"
        chr(0x1F916) + " AI-анализ трендов и логов\n"
        chr(0x26A0) + chr(0xFE0F) + " Автоматические алерты при проблемах\n"
        chr(0x1F4E6) + " Офлайн-очередь (алерты не теряются)\n\n"
        "<b>Используй кнопки ниже или команды:</b>"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML", reply_markup=create_main_keyboard())


@bot.message_handler(commands=["status"])
@bot.message_handler(func=lambda message: message.text == chr(0x1F4CA) + " Статус")
def cmd_status(message):
    servers = get_servers()
    
    if not servers:
        bot.reply_to(message, chr(0x274C) + " База пуста. Проверь сервисы collector")
        return
    
    status_text = chr(0x1F4CA) + " <b>Статус серверов</b>\n\n"
    
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
@bot.message_handler(func=lambda message: message.text == chr(0x1F916) + " AI-анализ")
def cmd_trend(message):
    bot.reply_to(message, chr(0x1F916) + " Анализирую тренды через AI... (10-20 сек)")
    
    servers = get_servers()
    if not servers:
        bot.reply_to(message, chr(0x1F4E6) + " База пуста. Проверь сервисы collector")
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
        bot.reply_to(message, chr(0x1F4E6) + " База пуста. Проверь сервисы collector")
        return
    
    history = "\n".join(all_history[-20:])
    
    prompt = ("Ты AI-аналитик мониторинга серверов. Кратко проанализируй метрики нескольких серверов:\n\n"
              + history +
              "\n\nОтветь ОЧЕНЬ кратко на русском (3-4 предложения): есть ли проблемы, общее состояние, рекомендации.")
    
    try:
        payload = {"model": MODEL, "prompt": prompt, "stream": False}
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        analysis = r.json()["response"]
    except Exception as e:
        analysis = "Ошибка связи с AI: " + str(e)
    
    trend_text = chr(0x1F916) + " <b>AI-анализ трендов</b>\n\n" + analysis
    bot.send_message(message.chat.id, trend_text, parse_mode="HTML")


@bot.message_handler(commands=["logs"])
@bot.message_handler(func=lambda message: message.text == chr(0x1F50D) + " Логи")
def cmd_logs(message):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            content = f.read()
        if content.strip():
            log_text = chr(0x1F50D) + " <b>Анализ системных логов</b>\n\n" + content[:1500]
            bot.send_message(message.chat.id, log_text, parse_mode="HTML")
        else:
            bot.reply_to(message, chr(0x23F3) + " Файл анализа пуст. Подожди 10 минут.")
    else:
        bot.reply_to(message, chr(0x1F50D) + " Анализ логов ещё не запускался. Подожди 10 минут.")


@bot.message_handler(commands=["test_alert"])
@bot.message_handler(func=lambda message: message.text == chr(0x26A0) + chr(0xFE0F) + " Тест алерта")
def cmd_test_alert(message):
    queue_alert(chr(0x26A0) + chr(0xFE0F) + " <b>ТЕСТОВЫЙ АЛЕРТ:</b> диск заполнен на 93%! (проверка очереди)")
    bot.reply_to(message, chr(0x2705) + " Алерт положен в очередь. Доставка в течение 30 сек.")


@bot.message_handler(commands=["queue"])
@bot.message_handler(func=lambda message: message.text == chr(0x1F4CB) + " Очередь")
def cmd_queue(message):
    conn = sqlite3.connect(DB_NAME)
    total = conn.execute("SELECT COUNT(*) FROM alert_queue").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM alert_queue WHERE sent=0").fetchone()[0]
    conn.close()
    
    queue_text = (
        f"{chr(0x1F4CB)} <b>Очередь алертов</b>\n\n"
        f"{chr(0x1F4CA)} Всего за всё время: <b>{total}</b>\n"
        f"{chr(0x23F3)} Ожидают отправки: <b>{pending}</b>\n"
        f"{chr(0x2705)} Доставлено: <b>{total - pending}</b>"
    )
    bot.send_message(message.chat.id, queue_text, parse_mode="HTML")


@bot.message_handler(commands=["help"])
@bot.message_handler(func=lambda message: message.text == chr(0x2753) + " Справка")
def cmd_help(message):
    help_text = (
        f"{chr(0x2753)} <b>Справка по боту</b>\n\n"
        "<b>Команды:</b>\n"
        f"{chr(0x1F4CA)} /status — статус всех серверов\n"
        f"{chr(0x1F916)} /trend — AI-анализ трендов\n"
        f"{chr(0x1F50D)} /logs — анализ системных логов\n"
        f"{chr(0x26A0)}{chr(0xFE0F)} /test_alert — тестовый алерт\n"
        f"{chr(0x1F4CB)} /queue — состояние очереди\n\n"
        "<b>Алерты срабатывают когда:</b>\n"
        f"{chr(0x1F534)} Диск > 85%\n"
        f"{chr(0x1F534)} RAM > 90%\n"
        f"{chr(0x1F534)} CPU > 95%\n\n"
        "<b>Особенности:</b>\n"
        f"{chr(0x1F4E6)} Без сети алерты НЕ теряются — они ждут в очереди\n"
        f"{chr(0x1F916)} AI анализирует тренды и логи на аномалии"
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
                queue_alert(f"{chr(0x26A0)}{chr(0xFE0F)} <b>{srv_name}:</b> нет свежих метрик {int(age_min)} мин")
                alert_state[key] = True
            elif age_min <= 15:
                alert_state[key] = False
            
            key = f"{srv_name}_disk"
            if disk >= DISK_THRESHOLD and not alert_state.get(key, False):
                queue_alert(f"{chr(0x1F534)} <b>{srv_name}:</b> ДИСК заполнен на {disk:.1f}%!")
                alert_state[key] = True
            elif disk < DISK_THRESHOLD:
                alert_state[key] = False
            
            key = f"{srv_name}_ram"
            if ram >= RAM_THRESHOLD and not alert_state.get(key, False):
                queue_alert(f"{chr(0x1F534)} <b>{srv_name}:</b> RAM загружена на {ram:.1f}%!")
                alert_state[key] = True
            elif ram < RAM_THRESHOLD:
                alert_state[key] = False
            
            key = f"{srv_name}_cpu"
            if cpu >= CPU_THRESHOLD and not alert_state.get(key, False):
                queue_alert(f"{chr(0x1F534)} <b>{srv_name}:</b> CPU загружен на {cpu:.1f}%!")
                alert_state[key] = True
            elif cpu < CPU_THRESHOLD:
                alert_state[key] = False


if __name__ == "__main__":
    print(chr(0x1F680) + " Telegram-бот для мульти-серверного мониторинга запущен!")
    init_queue()
    threading.Thread(target=alert_checker, daemon=True).start()
    threading.Thread(target=sender_loop, daemon=True).start()
    bot.infinity_polling()
