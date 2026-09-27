#!/usr/bin/env python3
"""
AI-Sysadmin: агент-сборщик метрик для отправки на центральный хаб
Имитирует отдельный сервер
"""

import psutil
import requests
import time
import json
import os
import random
from datetime import datetime

HUB_URL = "http://localhost:9000/metrics"
SERVER_NAME = os.environ.get('SERVER_NAME', 'server-unknown')
CHECK_INTERVAL = 60  # каждые 60 секунд


def get_metrics():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    
    # Добавляем небольшую случайность для имитации разных серверов
    cpu = max(0, min(100, cpu + random.uniform(-5, 5)))
    memory = max(0, min(100, memory + random.uniform(-3, 3)))
    disk = max(0, min(100, disk + random.uniform(-1, 1)))
    
    net = psutil.net_io_counters()
    
    return {
        'server_name': SERVER_NAME,
        'cpu': round(cpu, 1),
        'memory': round(memory, 1),
        'disk': round(disk, 1),
        'network_sent': net.bytes_sent,
        'network_recv': net.bytes_recv
    }


def send_metrics():
    metrics = get_metrics()
    
    try:
        r = requests.post(HUB_URL, json=metrics, timeout=10)
        if r.status_code == 200:
            print(f"📤 [{SERVER_NAME}] Метрики отправлены: CPU={metrics['cpu']}%, RAM={metrics['memory']}%, Disk={metrics['disk']}%")
        else:
            print(f"❌ [{SERVER_NAME}] Ошибка отправки: {r.status_code}")
    except Exception as e:
        print(f" [{SERVER_NAME}] Не удалось отправить метрики: {e}")


if __name__ == "__main__":
    print(f"🚀 Агент {SERVER_NAME} запущен. Отправка метрик каждые {CHECK_INTERVAL} сек.")
    
    while True:
        send_metrics()
        time.sleep(CHECK_INTERVAL)
