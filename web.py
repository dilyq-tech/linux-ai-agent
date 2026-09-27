#!/usr/bin/env python3
"""
AI-Sysadmin: веб-дашборд с метриками всех серверов
"""

import sqlite3
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from datetime import datetime

DB_NAME = "monitoring.db"
LOG_FILE = "/tmp/log_analysis.txt"
app = FastAPI(title="AI-Sysadmin Dashboard")


@app.get("/api/metrics")
def get_metrics(server: str = None, limit: int = 100):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    if server:
        cur.execute("""
            SELECT timestamp, cpu_percent, memory_percent, disk_percent, server_name 
            FROM metrics 
            WHERE server_name = ?
            ORDER BY id DESC LIMIT ?
        """, (server, limit))
    else:
        cur.execute("""
            SELECT timestamp, cpu_percent, memory_percent, disk_percent, server_name 
            FROM metrics 
            ORDER BY id DESC LIMIT ?
        """, (limit,))
    
    rows = cur.fetchall()
    conn.close()
    rows.reverse()
    
    return [{
        "time": r[0][11:16],
        "cpu": r[1],
        "ram": r[2],
        "disk": r[3],
        "server": r[4]
    } for r in rows]


@app.get("/api/servers")
def get_servers():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT server_name FROM metrics ORDER BY server_name")
    servers = [row[0] for row in cur.fetchall()]
    conn.close()
    return servers


@app.get("/api/latest")
def get_latest(server: str = None):
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
    
    if row:
        return {
            "time": row[0][11:16],
            "cpu": row[1],
            "ram": row[2],
            "disk": row[3],
            "server": row[4]
        }
    return None


@app.get("/api/alerts")
def get_alerts(limit: int = 20):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT created_at, text, sent FROM alert_queue ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{"time": r[0][11:16], "text": r[1], "sent": bool(r[2])} for r in rows]


@app.get("/api/logs")
def get_logs():
    try:
        with open(LOG_FILE, "r") as f:
            return {"content": f.read()[:2000]}
    except:
        return {"content": "Анализ логов недоступен"}


HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-Sysadmin Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
    background: #0d1117; 
    color: #e6edf3; 
    padding: 20px;
  }
  .container { max-width: 1400px; margin: 0 auto; }
  h1 { 
    font-size: 28px; 
    margin-bottom: 24px;
    background: linear-gradient(135deg, #58a6ff, #3fb950);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .server-selector {
    margin-bottom: 24px;
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  .server-btn {
    background: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
    padding: 10px 20px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .server-btn:hover { background: #21262d; }
  .server-btn.active { 
    background: #238636; 
    border-color: #2ea043;
  }
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  .metric-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
    transition: transform 0.2s;
  }
  .metric-card:hover { transform: translateY(-2px); }
  .metric-title {
    font-size: 14px;
    color: #8b949e;
    margin-bottom: 8px;
  }
  .metric-value {
    font-size: 32px;
    font-weight: bold;
    margin-bottom: 12px;
  }
  .metric-bar {
    height: 8px;
    background: #21262d;
    border-radius: 4px;
    overflow: hidden;
  }
  .metric-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s;
  }
  .status-good { color: #3fb950; }
  .status-warning { color: #f0883e; }
  .status-critical { color: #f85149; }
  .bar-good { background: linear-gradient(90deg, #3fb950, #2ea043); }
  .bar-warning { background: linear-gradient(90deg, #f0883e, #d29922); }
  .bar-critical { background: linear-gradient(90deg, #f85149, #da3633); }
  .chart-container {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
  }
  .alerts-container {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
  }
  .alert-item {
    padding: 12px;
    border-left: 3px solid #30363d;
    margin-bottom: 8px;
    background: #0d1117;
    border-radius: 4px;
  }
  .alert-sent { border-left-color: #3fb950; }
  .alert-pending { border-left-color: #f0883e; }
  .alert-time {
    font-size: 12px;
    color: #8b949e;
    margin-bottom: 4px;
  }
  .alert-text { font-size: 14px; }
  .logs-container {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
    margin-top: 24px;
    max-height: 400px;
    overflow-y: auto;
  }
  .logs-content {
    font-family: 'Courier New', monospace;
    font-size: 12px;
    white-space: pre-wrap;
    color: #8b949e;
  }
  .section-title {
    font-size: 20px;
    margin-bottom: 16px;
    color: #e6edf3;
  }
  .update-time {
    text-align: right;
    font-size: 12px;
    color: #8b949e;
    margin-top: 8px;
  }
</style>
</head>
<body>
<div class="container">
  <h1>🤖 AI-Sysadmin Dashboard</h1>
  
  <div class="server-selector" id="server-selector">
    <button class="server-btn active" data-server="">Все серверы</button>
  </div>
  
  <div class="metrics-grid" id="metrics">
    <div class="metric-card">
      <div class="metric-title">CPU</div>
      <div class="metric-value" id="cpu-value">--</div>
      <div class="metric-bar"><div class="metric-bar-fill" id="cpu-bar"></div></div>
    </div>
    <div class="metric-card">
      <div class="metric-title">RAM</div>
      <div class="metric-value" id="ram-value">--</div>
      <div class="metric-bar"><div class="metric-bar-fill" id="ram-bar"></div></div>
    </div>
    <div class="metric-card">
      <div class="metric-title">Disk</div>
      <div class="metric-value" id="disk-value">--</div>
      <div class="metric-bar"><div class="metric-bar-fill" id="disk-bar"></div></div>
    </div>
  </div>

  <div class="chart-container">
    <h2 class="section-title">📈 История метрик</h2>
    <canvas id="chart" height="100"></canvas>
    <div class="update-time" id="update-time">Обновлено: --</div>
  </div>

  <div class="alerts-container">
    <h2 class="section-title">🚨 Последние алерты</h2>
    <div id="alerts">Загрузка...</div>
  </div>

  <div class="logs-container">
    <h2 class="section-title">🔍 AI-анализ логов</h2>
    <div class="logs-content" id="logs">Загрузка...</div>
  </div>
</div>

<script>
let chart;
let currentServer = '';
const CPU_THRESHOLD = 95;
const RAM_THRESHOLD = 90;
const DISK_THRESHOLD = 85;

function getStatus(value, threshold) {
  if (value >= threshold) return 'critical';
  if (value >= threshold * 0.8) return 'warning';
  return 'good';
}

function updateMetrics(latest) {
  if (!latest) return;
  
  ['cpu', 'ram', 'disk'].forEach(metric => {
    const value = latest[metric];
    const threshold = metric === 'cpu' ? CPU_THRESHOLD : metric === 'ram' ? RAM_THRESHOLD : DISK_THRESHOLD;
    const status = getStatus(value, threshold);
    
    document.getElementById(`${metric}-value`).textContent = value.toFixed(1) + '%';
    document.getElementById(`${metric}-value`).className = `metric-value status-${status}`;
    
    const bar = document.getElementById(`${metric}-bar`);
    bar.style.width = value + '%';
    bar.className = `metric-bar-fill bar-${status}`;
  });
  
  document.getElementById('update-time').textContent = 'Обновлено: ' + latest.time + ' (' + (latest.server || 'все серверы') + ')';
}

async function loadServers() {
  const servers = await (await fetch('/api/servers')).json();
  const selector = document.getElementById('server-selector');
  
  servers.forEach(server => {
    const btn = document.createElement('button');
    btn.className = 'server-btn';
    btn.textContent = server;
    btn.dataset.server = server;
    btn.onclick = () => selectServer(server);
    selector.appendChild(btn);
  });
}

function selectServer(server) {
  currentServer = server;
  document.querySelectorAll('.server-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.server === server);
  });
  refresh();
}

async function refresh() {
  const latest = await (await fetch(`/api/latest${currentServer ? '?server=' + currentServer : ''}`)).json();
  updateMetrics(latest);
  
  const m = await (await fetch(`/api/metrics?limit=100${currentServer ? '&server=' + currentServer : ''}`)).json();
  const data = {
    labels: m.map(x => x.time),
    datasets: [
      { 
        label: 'CPU %', 
        data: m.map(x => x.cpu), 
        borderColor: '#58a6ff', 
        backgroundColor: 'rgba(88,166,255,.1)', 
        fill: true, 
        tension: .4,
        borderWidth: 2
      },
      { 
        label: 'RAM %', 
        data: m.map(x => x.ram), 
        borderColor: '#3fb950', 
        backgroundColor: 'rgba(63,185,80,.1)', 
        fill: true, 
        tension: .4,
        borderWidth: 2
      },
      { 
        label: 'Disk %', 
        data: m.map(x => x.disk), 
        borderColor: '#f0883e', 
        backgroundColor: 'rgba(240,136,62,.1)', 
        fill: true, 
        tension: .4,
        borderWidth: 2
      }
    ]
  };
  
  if (chart) { 
    chart.data = data; 
    chart.update(); 
  } else { 
    chart = new Chart(document.getElementById('chart'), { 
      type: 'line', 
      data,
      options: {
        responsive: true,
        plugins: {
          legend: { labels: { color: '#e6edf3' } }
        },
        scales: {
          x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
          y: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' }, max: 100 }
        }
      }
    }); 
  }
  
  const a = await (await fetch('/api/alerts')).json();
  document.getElementById('alerts').innerHTML = a.length
    ? a.map(x => `<div class="alert-item alert-${x.sent ? 'sent' : 'pending'}">
        <div class="alert-time">${x.time}</div>
        <div class="alert-text">${x.sent ? '✅' : ''} ${x.text}</div>
      </div>`).join('')
    : '<div style="color: #8b949e;">Алертов нет — серверы здоровы</div>';
  
  const logs = await (await fetch('/api/logs')).json();
  document.getElementById('logs').textContent = logs.content || 'Анализ недоступен';
}

loadServers();
refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML
