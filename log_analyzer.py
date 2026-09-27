#!/usr/bin/env python3
"""
AI-Sysadmin: анализатор системных логов на аномалии
"""

import subprocess
import requests
import os

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"
MAX_LINES = 500


def get_recent_logs():
    try:
        result = subprocess.run(
            ["journalctl", "-n", str(MAX_LINES), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    
    # Fallback: читаем /var/log/syslog напрямую
    syslog = "/var/log/syslog"
    if os.path.exists(syslog):
        try:
            with open(syslog, "r") as f:
                lines = f.readlines()
            return "".join(lines[-MAX_LINES:])
        except Exception:
            pass
    
    return "Логи недоступны (нет прав или journalctl не работает)"


def get_auth_logs():
    try:
        result = subprocess.run(
            ["journalctl", "-n", "200", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            auth_lines = [l for l in lines if any(k in l.lower() for k in ['ssh', 'sudo', 'auth', 'login', 'password'])]
            return "\n".join(auth_lines[-100:])
    except Exception:
        pass
    
    auth_log = "/var/log/auth.log"
    if os.path.exists(auth_log):
        try:
            with open(auth_log, "r") as f:
                lines = f.readlines()
            return "".join(lines[-200:])
        except Exception:
            pass
    
    return ""


def analyze_logs_with_ai(logs):
    prompt = f"""Ты AI-аналитик безопасности Linux-сервера. Проанализируй эти системные логи и найди аномалии:

{logs[:3000]}

Ответь ОЧЕНЬ кратко на русском (3-5 предложений):
1. Есть ли подозрительная активность?
2. Какие события требуют внимания?
3. Общая оценка: безопасно / требует внимания / критично

Если всё нормально, напиши: "Логи чистые, аномалий не обнаружено."
"""
    
    try:
        payload = {"model": MODEL, "prompt": prompt, "stream": False}
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        return r.json()["response"]
    except Exception as e:
        return f"Ошибка связи с AI: {e}"


def check_for_critical_events(logs):
    critical_keywords = [
        "failed password", "invalid user", "authentication failure",
        "oom killer", "out of memory", "segfault", "kernel panic",
        "critical", "emergency", "error", "fatal"
    ]
    
    found = []
    for line in logs.split('\n'):
        line_lower = line.lower()
        for keyword in critical_keywords:
            if keyword in line_lower:
                found.append(line.strip())
                break
    
    return found[:10]


if __name__ == "__main__":
    print(" Анализ системных логов...\n")
    
    logs = get_recent_logs()
    auth_logs = get_auth_logs()
    full_logs = logs + "\n\n=== AUTH LOGS ===\n" + auth_logs
    
    print(f" Прочитано {len(logs.split(chr(10)))} строк\n")
    
    critical = check_for_critical_events(full_logs)
    if critical:
        print(f"⚠️ Найдено {len(critical)} критичных событий:\n")
        for event in critical[:5]:
            print(f"  • {event[:100]}")
        print()
    
    print(" AI-анализ (10-20 сек)...")
    analysis = analyze_logs_with_ai(full_logs)
    print("\n" + analysis)
