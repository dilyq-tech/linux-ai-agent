#!/usr/bin/env python3
"""
AI-Sysadmin: объединенный агент
Режимы: ЧАТ (диалог), КОМАНДА (диагностика), ТРЕНД (анализ истории из БД)
"""

import subprocess
import sqlite3
import os
import requests

DB_NAME = "monitoring.db"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:3b"

ALLOWED = ["df", "free", "ss", "systemctl", "tail", "uptime", "top", "ps", "ls", "cat", "who", "date", "hostname"]

def ask_ollama(messages):
    payload = {"model": MODEL, "messages": messages, "stream": False}
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    return r.json()["message"]["content"]

def run_command(cmd):
    cmd = cmd.strip().strip("'\"`")
    parts = cmd.split()
    if not parts or parts[0] not in ALLOWED:
        return "Команда '" + cmd + "' не разрешена"
    try:
        res = subprocess.run(parts, capture_output=True, text=True, timeout=10)
        out = res.stdout or res.stderr
        return out if out else "Команда выполнена, вывод пустой"
    except FileNotFoundError:
        return "Команда '" + cmd + "' не найдена"
    except Exception as e:
        return "Ошибка выполнения: " + str(e)

def get_history_metrics(limit=10):
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

def extract_commands(text):
    cmds = []
    for line in text.split("\n"):
        if "КОМАНДА:" in line:
            c = line.split("КОМАНДА:")[1].strip().strip("'\"`").rstrip(".")
            if c:
                cmds.append(c)
    return cmds

def route(user_msg, history):
    router_msgs = history + [{"role": "user", "content":
        "Ответь ровно одним словом: КОМАНДА, ТРЕНД или ЧАТ.\n"
        "КОМАНДА - если нужно выполнить Linux-команду прямо сейчас (диск, память, сервисы, логи, сеть).\n"
        "ТРЕНД - если спрашивают про историю, тренды, изменения со временем, общее состояние сервера по собранным данным.\n"
        "ЧАТ - приветствие или разговор не по теме.\n"
        "Вопрос: " + user_msg}]
    return ask_ollama(router_msgs).strip().upper()

def agent_loop(user_msg, history):
    history.append({"role": "user", "content": user_msg})
    decision = route(user_msg, history)
    print("Решение роутера: " + decision)

    if "ТРЕНД" in decision:
        data = get_history_metrics(10)
        if not data:
            text = "База данных пока пуста. Запусти collector.py и подожди несколько минут."
        else:
            sys_msg = {"role": "system", "content": "Ты AI-аналитик мониторинга сервера. Анализируй тренды метрик, отвечай на русском, кратко."}
            msgs = [sys_msg] + history + [{"role": "user", "content": "Вот история метрик:\n" + data + "\n\nОпиши тренды и общее состояние сервера."}]
            text = ask_ollama(msgs)

    elif "КОМАНДА" in decision:
        sys_msg = {"role": "system", "content": "Ты AI-помощник для диагностики Linux. Доступные команды: df -h, free -h, ss -tulnp, systemctl is-active <имя>, tail -n 50 <файл>, uptime. Ответь строго в формате: КОМАНДА: <команда без кавычек> (каждая с новой строки) затем АНАЛИЗ: ..."}
        msgs = [sys_msg] + history
        text = ask_ollama(msgs)
        cmds = extract_commands(text)
        if cmds:
            results = []
            for c in cmds:
                print("Выполняю: " + c)
                res = run_command(c)
                results.append(c + " => " + res[:300])
                print("Результат: " + res[:100])
            history.append({"role": "assistant", "content": text})
            history.append({"role": "user", "content": "Результаты выполнения:\n" + "\n".join(results) + "\n\nДай финальный анализ на русском, кратко, опирайся только на реальные данные."})
            text = ask_ollama(history)

    else:
        sys_msg = {"role": "system", "content": "Ты дружелюбный AI-помощник. Отвечай на русском, кратко."}
        msgs = [sys_msg] + history
        text = ask_ollama(msgs)

    history.append({"role": "assistant", "content": text})
    if len(history) > 10:
        history = history[-10:]
    print("\nОтвет агента:\n" + text)
    return history

if __name__ == "__main__":
    print("AI-Sysadmin (объединенный агент): чат + команды + тренды.")
    print("Выход: exit / quit / выход\n")
    history = []
    while True:
        u = input("Ты: ").strip()
        if u.lower() in ["exit", "quit", "выход"]:
            break
        if u:
            try:
                history = agent_loop(u, history)
            except Exception as e:
                print("Ошибка: " + str(e))
