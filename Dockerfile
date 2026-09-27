FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    sudo \
    procps \
    iproute2 \
    ufw \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY collector.py collector_agent.py bot.py agent.py analyzer.py web.py hub.py manager.py log_analyzer.py full_control.py control_handlers.py ./

CMD ["python", "bot.py"]
