#!/usr/bin/env python3
"""
AI-Sysadmin: веб-дашборд с графиками метрик
Открой: http://localhost:8000 (или http://IP-сервера:8000 с телефона)
"""

import sqlite3
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

DB_NAME = "monitoring.db"
app = FastAPI(title="AI-Sysadmin Dashboard")


@app.get("/api/metrics")
def get_metrics(limit: int = 100):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT timestamp, cpu_percent, memory_percent, disk_percent FROM metrics ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    rows.reverse()
    return [{"time": r[0][11:16], "cpu": r[1], "ram": r[2], "disk": r[3]} for r in rows]


@app.get("/api/alerts")
def get_alerts(limit: int = 20):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT created_at, text, sent FROM alert_queue ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{"time": r[0][11:16], "text": r[1], "sent": bool(r[2])} for r in rows]


HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-Sysadmin Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body { font-family: sans-serif; background:#0d1117; color:#e6edf3; margin:0; padding:20px; }
  h1 { font-size:22px; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:10px; padding:16px; margin-bottom:16px; }
</style>
</head>
<body>
<h1>🤖 AI-Sysadmin — дашборд мониторинга</h1>
<div class="card"><canvas id="chart" height="80"></canvas></div>
<div class="card"><h2>🚨 Алерты</h2><ul id="alerts"></ul></div>
<script>
let chart;
async function refresh() {
  const m = await (await fetch('/api/metrics?limit=100')).json();
  const data = {
    labels: m.map(x => x.time),
    datasets: [
      { label:'CPU %', data:m.map(x=>x.cpu), borderColor:'#58a6ff', backgroundColor:'rgba(88,166,255,.15)', fill:true, tension:.3 },
      { label:'RAM %', data:m.map(x=>x.ram), borderColor:'#3fb950', backgroundColor:'rgba(63,185,80,.15)', fill:true, tension:.3 },
      { label:'Disk %', data:m.map(x=>x.disk), borderColor:'#f0883e', backgroundColor:'rgba(240,136,62,.15)', fill:true, tension:.3 }
    ]
  };
  if (chart) { chart.data = data; chart.update(); }
  else { chart = new Chart(document.getElementById('chart'), { type:'line', data }); }
  const a = await (await fetch('/api/alerts')).json();
  document.getElementById('alerts').innerHTML = a.length
    ? a.map(x => '<li>' + (x.sent ? '✅' : '⏳') + ' ' + x.time + ' — ' + x.text + '</li>').join('')
    : '<li>Алертов нет — сервер здоров</li>';
}
refresh();
setInterval(refresh, 60000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML
