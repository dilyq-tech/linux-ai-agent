#!/usr/bin/env python3
"""
AI-Sysadmin: Сборщик метрик системы
Собирает CPU, RAM, Disk, Network каждые 5 минут и сохраняет в SQLite
"""

import psutil
import sqlite3
import time
import os
from datetime import datetime

# Конфигурация
DB_NAME = "monitoring.db"
CHECK_INTERVAL = 300  # 5 минут в секундах

def init_database():
    """Создает таблицу для хранения метрик"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            cpu_percent REAL,
            memory_percent REAL,
            memory_used_gb REAL,
            memory_total_gb REAL,
            disk_percent REAL,
            disk_used_gb REAL,
            disk_total_gb REAL,
            network_sent_mb REAL,
            network_recv_mb REAL
        )
    """)
    conn.commit()
    conn.close()
    print(f"✅ База данных {DB_NAME} готова")

def collect_metrics():
    """Собирает все метрики системы"""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # RAM
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    memory_used_gb = memory.used / (1024**3)
    memory_total_gb = memory.total / (1024**3)
    
    # Disk
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent
    disk_used_gb = disk.used / (1024**3)
    disk_total_gb = disk.total / (1024**3)
    
    # Network
    network = psutil.net_io_counters()
    network_sent_mb = network.bytes_sent / (1024**2)
    network_recv_mb = network.bytes_recv / (1024**2)
    
    return {
        'cpu_percent': cpu_percent,
        'memory_percent': memory_percent,
        'memory_used_gb': memory_used_gb,
        'memory_total_gb': memory_total_gb,
        'disk_percent': disk_percent,
        'disk_used_gb': disk_used_gb,
        'disk_total_gb': disk_total_gb,
        'network_sent_mb': network_sent_mb,
        'network_recv_mb': network_recv_mb
    }

def save_metrics(metrics):
    """Сохраняет метрики в базу данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO metrics (
            timestamp, cpu_percent, memory_percent, memory_used_gb, memory_total_gb,
            disk_percent, disk_used_gb, disk_total_gb, network_sent_mb, network_recv_mb
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        metrics['cpu_percent'],
        metrics['memory_percent'],
        metrics['memory_used_gb'],
        metrics['memory_total_gb'],
        metrics['disk_percent'],
        metrics['disk_used_gb'],
        metrics['disk_total_gb'],
        metrics['network_sent_mb'],
        metrics['network_recv_mb']
    ))
    conn.commit()
    conn.close()

def print_metrics(metrics):
    """Красиво выводит метрики"""
    print(f"\n Метрики системы ({datetime.now().strftime('%H:%M:%S')}):")
    print(f"  CPU: {metrics['cpu_percent']:.1f}%")
    print(f"  RAM: {metrics['memory_percent']:.1f}% ({metrics['memory_used_gb']:.2f}/{metrics['memory_total_gb']:.2f} GB)")
    print(f"  Disk: {metrics['disk_percent']:.1f}% ({metrics['disk_used_gb']:.2f}/{metrics['disk_total_gb']:.2f} GB)")
    print(f"  Network: ↑{metrics['network_sent_mb']:.1f} MB ↓{metrics['network_recv_mb']:.1f} MB")

def main():
    """Главный цикл сборщика"""
    print("🚀 AI-Sysadmin Collector запущен")
    print(f" База данных: {os.path.abspath(DB_NAME)}")
    print(f"⏱️ Интервал сбора: {CHECK_INTERVAL // 60} минут")
    print("Нажми Ctrl+C для остановки\n")
    
    init_database()
    
    try:
        while True:
            metrics = collect_metrics()
            save_metrics(metrics)
            print_metrics(metrics)
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n⏹️ Сборщик остановлен")

if __name__ == "__main__":
    main()
