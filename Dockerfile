FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY collector.py bot.py agent.py analyzer.py ./

CMD ["python", "bot.py"]
