#!/usr/bin/env python3
"""
AI-Sysadmin: Анализатор трендов
Читает метрики из БД и отправляет в Ollama для анализа
"""

import sqlite3
import requests
from datetime import datetime

DB_NAME = "monitoring.db"

def get_recent_metrics(limit=10):
    """Получает последние N записей из БД"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, cpu_percent, memory_percent, disk_percent, 
               network_sent_mb, network_recv_mb
        FROM metrics 
        ORDER BY id DESC 
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return "Нет данных в базе. Запусти collector.py сначала."
    
    # Переворачиваем чтобы было от старых к новым
    rows.reverse()
    
    text = "История метрик (от старых к новым):\n\n"
    for row in rows:
        text += f"Время: {row[0]}\n"
        text += f"  CPU: {row[1]}% | RAM: {row[2]}% | Disk: {row[3]}%\n"
        text += f"  Network: ↑{row[4]:.1f} MB ↓{row[5]:.1f} MB\n\n"
    
    return text

def analyze_with_ai(metrics_text):
    """Отправляет метрики в Ollama для анализа"""
    prompt = f"""Ты AI-аналитик мониторинга сервера. Проанализируй историю метрик и найди тренды.

{metrics_text}

Ответь на русском языке в формате:
1. ОБЩАЯ ОЦЕНКА: (здоровье сервера)
2. ТРЕНДЫ: (что растет, что падает, что стабильно)
3. ПРОБЛЕМЫ: (если есть аномалии)
4. РЕКОМЕНДАЦИИ: (что делать)

Если всё нормально — напиши кратко что сервер здоров."""
    
    try:
        url = "http://localhost:11434/api/generate"
        payload = {"model": "qwen2.5:3b", "prompt": prompt, "stream": False}
        response = requests.post(url, json=payload, timeout=120)
        return response.json()["response"]
    except Exception as e:
        return f"Ошибка связи с AI: {str(e)}"

def main():
    print(" AI-Sysadmin Analyzer")
    print("=" * 50)
    
    print("\n Читаю метрики из базы...")
    metrics_text = get_recent_metrics(10)
    print(metrics_text)
    
    print("🤖 Анализирую тренды через AI...")
    analysis = analyze_with_ai(metrics_text)
    
    print("\n" + "=" * 50)
    print(" AI-АНАЛИЗ:")
    print("=" * 50)
    print(analysis)

if __name__ == "__main__":
    main()
