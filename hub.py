#!/usr/bin/env python3
"""
AI-Sysadmin: центральный хаб для приёма метрик от нескольких серверов
"""

import sqlite3
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

DB_NAME = "monitoring.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            cpu_percent REAL,
            memory_percent REAL,
            disk_percent REAL,
            network_sent INTEGER,
            network_recv INTEGER
        )
    """)
    conn.commit()
    conn.close()


class MetricsHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/metrics':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                server_name = data.get('server_name', 'unknown')
                timestamp = datetime.now().isoformat()
                
                conn = sqlite3.connect(DB_NAME)
                conn.execute("""
                    INSERT INTO metrics (server_name, timestamp, cpu_percent, memory_percent, disk_percent, network_sent, network_recv)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    server_name,
                    timestamp,
                    data.get('cpu', 0),
                    data.get('memory', 0),
                    data.get('disk', 0),
                    data.get('network_sent', 0),
                    data.get('network_recv', 0)
                ))
                conn.commit()
                conn.close()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode())
                
                print(f"✅ Получены метрики от {server_name}: CPU={data.get('cpu')}%, RAM={data.get('memory')}%, Disk={data.get('disk')}%")
                
            except Exception as e:
                print(f"❌ Ошибка обработки метрик: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Отключаем стандартные логи


if __name__ == "__main__":
    init_db()
    print("🚀 Центральный хаб запущен на порту 9000")
    server = HTTPServer(('0.0.0.0', 9000), MetricsHandler)
    server.serve_forever()
