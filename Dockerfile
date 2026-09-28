FROM python:3.12-alpine AS builder

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-alpine AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY collector.py collector_agent.py bot.py agent.py analyzer.py web.py hub.py manager.py log_analyzer.py full_control.py control_handlers.py ./

CMD ["python", "bot.py"]

FROM runtime AS bot
RUN apk add --no-cache docker-cli iproute2 procps sudo
