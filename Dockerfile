FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY collector.py collector_agent.py bot.py agent.py analyzer.py web.py hub.py ./

CMD ["python", "bot.py"]
