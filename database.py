# database.py
import sqlite3
from datetime import datetime
from config import DB_PATH

def init_db():
    """Создаёт таблицы, если их нет"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_name TEXT DEFAULT 'localhost',
                timestamp TEXT NOT NULL,
                cpu_percent REAL,
                ram_percent REAL,
                disk_percent REAL,
                network_sent INTEGER DEFAULT 0,
                network_recv INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sent INTEGER DEFAULT 0
            )
        """)
        conn.commit()

def save_metrics(server_name: str, cpu: float, ram: float, disk: float, 
                 net_sent: int = 0, net_recv: int = 0):
    """Сохраняет метрики в базу"""
    timestamp = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO metrics (server_name, timestamp, cpu_percent, ram_percent, 
                               disk_percent, network_sent, network_recv)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (server_name, timestamp, cpu, ram, disk, net_sent, net_recv))
        conn.commit()

def get_latest_metrics(server_name: str = None):
    """Получает последние метрики"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if server_name:
            cursor = conn.execute("""
                SELECT * FROM metrics 
                WHERE server_name = ?
                ORDER BY id DESC LIMIT 1
            """, (server_name,))
        else:
            cursor = conn.execute("""
                SELECT * FROM metrics 
                ORDER BY id DESC LIMIT 1
            """)
        return cursor.fetchone()

def get_all_servers():
    """Получает список всех серверов"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("""
            SELECT DISTINCT server_name FROM metrics 
            ORDER BY server_name
        """)
        return [row[0] for row in cursor.fetchall()]

def get_metrics_history(server_name: str, limit: int = 20):
    """Получает историю метрик для ИИ-анализа"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT timestamp, cpu_percent, ram_percent, disk_percent 
            FROM metrics 
            WHERE server_name = ?
            ORDER BY id DESC LIMIT ?
        """, (server_name, limit))
        return list(reversed(cursor.fetchall()))

# === Функции для очереди алертов ===

def queue_alert(text: str):
    """Добавляет алерт в очередь"""
    timestamp = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO alert_queue (text, created_at, sent)
            VALUES (?, ?, 0)
        """, (text, timestamp))
        conn.commit()

def get_unsent_alerts(limit: int = 10):
    """Получает неотправленные алерты"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT id, text FROM alert_queue 
            WHERE sent = 0 
            ORDER BY id ASC 
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()

def mark_alert_sent(alert_id: int):
    """Помечает алерт как отправленный"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE alert_queue SET sent = 1 WHERE id = ?", (alert_id,))
        conn.commit()
        # Самовосстановление: создаём таблицы при импорте модуля
init_db()
def purge_stale_servers(hours=24):
    """Удаляет метрики серверов, которые молчали дольше hours часов"""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted
