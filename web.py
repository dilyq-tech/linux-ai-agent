# web.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from database import get_latest_metrics, get_all_servers, get_metrics_history, get_unsent_alerts
import uvicorn
import threading

app = FastAPI()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-Sysadmin Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
        }
        h1 { margin-bottom: 20px; color: #4fc3f7; }
        .server-buttons { margin-bottom: 20px; }
        .server-btn {
            background: #2d2d44;
            color: #eee;
            border: none;
            padding: 10px 20px;
            margin-right: 10px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        .server-btn.active { background: #4caf50; }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: #2d2d44;
            padding: 20px;
            border-radius: 10px;
        }
        .metric-card h3 { color: #aaa; margin-bottom: 10px; font-size: 14px; }
        .metric-value { font-size: 32px; font-weight: bold; color: #4fc3f7; }
        .section {
            background: #2d2d44;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .section h2 { margin-bottom: 15px; color: #4fc3f7; }
        .alert-item { 
            padding: 10px; 
            background: #3d3d5c; 
            margin-bottom: 10px; 
            border-radius: 5px;
            border-left: 4px solid #ff5252;
        }
        #chart-container { height: 300px; }
        .loading { color: #aaa; font-style: italic; }
    </style>
</head>
<body>
    <h1>🤖 AI-Sysadmin Dashboard</h1>
    
    <div class="server-buttons" id="server-buttons">
        <button class="server-btn active" onclick="selectServer('all')">Все серверы</button>
    </div>

    <div class="metrics-grid">
        <div class="metric-card">
            <h3>CPU</h3>
            <div class="metric-value" id="cpu-value">--</div>
        </div>
        <div class="metric-card">
            <h3>RAM</h3>
            <div class="metric-value" id="ram-value">--</div>
        </div>
        <div class="metric-card">
            <h3>Disk</h3>
            <div class="metric-value" id="disk-value">--</div>
        </div>
    </div>

    <div class="section">
        <h2>📈 История метрик</h2>
        <div id="chart-container">
            <canvas id="metricsChart"></canvas>
        </div>
        <p style="margin-top: 10px; color: #aaa;">Обновлено: <span id="last-update">--</span></p>
    </div>

    <div class="section">
        <h2>🚨 Последние алерты</h2>
        <div id="alerts-list">
            <p class="loading">Загрузка...</p>
        </div>
    </div>

    <div class="section">
        <h2>🧠 AI-анализ логов</h2>
        <div id="ai-analysis">
            <p class="loading">Загрузка...</p>
        </div>
    </div>

    <script>
        let currentServer = 'all';
        let chart;

        async function loadServers() {
            const response = await fetch('/api/servers');
            const servers = await response.json();
            const container = document.getElementById('server-buttons');
            servers.forEach(server => {
                const btn = document.createElement('button');
                btn.className = 'server-btn';
                btn.textContent = server;
                btn.onclick = () => selectServer(server);
                container.appendChild(btn);
            });
        }

        async function updateMetrics() {
            const url = currentServer === 'all' ? '/api/latest' : `/api/latest/${currentServer}`;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data) {
                document.getElementById('cpu-value').textContent = data.cpu_percent.toFixed(1) + '%';
                document.getElementById('ram-value').textContent = data.ram_percent.toFixed(1) + '%';
                document.getElementById('disk-value').textContent = data.disk_percent.toFixed(1) + '%';
                document.getElementById('last-update').textContent = data.timestamp;
            }
        }

        async function updateChart() {
            const url = currentServer === 'all' ? '/api/history' : `/api/history/${currentServer}`;
            const response = await fetch(url);
            const history = await response.json();
            
            const labels = history.map(m => {
                const date = new Date(m.timestamp);
                return date.toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});
            });
            const cpuData = history.map(m => m.cpu_percent);
            const ramData = history.map(m => m.ram_percent);
            const diskData = history.map(m => m.disk_percent);

            if (chart) chart.destroy();
            
            const ctx = document.getElementById('metricsChart').getContext('2d');
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        { label: 'CPU %', data: cpuData, borderColor: '#4fc3f7', fill: false },
                        { label: 'RAM %', data: ramData, borderColor: '#81c784', fill: false },
                        { label: 'Disk %', data: diskData, borderColor: '#ffb74d', fill: false }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, max: 100, grid: { color: '#3d3d5c' } },
                        x: { grid: { color: '#3d3d5c' } }
                    }
                }
            });
        }

        async function updateAlerts() {
            const response = await fetch('/api/alerts');
            const alerts = await response.json();
            const container = document.getElementById('alerts-list');
            
            if (alerts.length === 0) {
                container.innerHTML = '<p style="color: #81c784;">✅ Нет активных алертов</p>';
            } else {
                container.innerHTML = alerts.map(a => 
                    `<div class="alert-item">${a.text}</div>`
                ).join('');
            }
        }

        async function updateAI() {
            const response = await fetch('/api/ai-analysis');
            const data = await response.json();
            document.getElementById('ai-analysis').innerHTML = 
                `<p>${data.analysis || 'Анализ недоступен'}</p>`;
        }

        function selectServer(server) {
            currentServer = server;
            document.querySelectorAll('.server-btn').forEach(btn => {
                btn.classList.toggle('active', btn.textContent === server || (server === 'all' && btn.textContent === 'Все серверы'));
            });
            updateMetrics();
            updateChart();
        }

        // Загрузка при старте
        loadServers();
        updateMetrics();
        updateChart();
        updateAlerts();
        updateAI();

        // Автообновление каждые 30 секунд
        setInterval(() => {
            updateMetrics();
            updateChart();
            updateAlerts();
        }, 30000);
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTML_TEMPLATE

@app.get("/api/servers")
async def api_servers():
    return get_all_servers()

@app.get("/api/latest")
@app.get("/api/latest/{server_name}")
async def api_latest(server_name: str = None):
    metrics = get_latest_metrics(server_name)
    if metrics:
        return dict(metrics)
    return None

@app.get("/api/history")
@app.get("/api/history/{server_name}")
async def api_history(server_name: str = None, limit: int = 20):
    if server_name:
        history = get_metrics_history(server_name, limit)
    else:
        # Берём историю первого сервера
        servers = get_all_servers()
        if servers:
            history = get_metrics_history(servers[0], limit)
        else:
            history = []
    return [dict(m) for m in history]

@app.get("/api/alerts")
async def api_alerts():
    alerts = get_unsent_alerts(limit=10)
    return [dict(a) for a in alerts]

@app.get("/api/ai-analysis")
async def api_ai_analysis():
    from ai_analyzer import analyze_metrics
    servers = get_all_servers()
    if servers:
        history = get_metrics_history(servers[0], limit=10)
        analysis = analyze_metrics(history)
        return {"analysis": analysis}
    return {"analysis": "Нет данных"}

def start_web():
    """Запускает веб-сервер"""
    uvicorn.run(app, host="0.0.0.0", port=8001)

if __name__ == "__main__":
    start_web()