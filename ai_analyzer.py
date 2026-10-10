# ai_analyzer.py
import requests
import logging
from config import OLLAMA_URL, OLLAMA_MODEL

logging.basicConfig(level=logging.INFO, format="%(asctime)s | [ИИ] | %(message)s", datefmt="%H:%M:%S")


def analyze_metrics(metrics_history: list) -> str:
    """
    Отправляет историю метрик в локальный Ollama и получает AI-анализ.
    metrics_history: список словарей с ключами timestamp, cpu_percent, ram_percent, disk_percent
    """
    if not metrics_history:
        return "Нет данных для анализа."

    # Формируем читаемый текст для промпта
    metrics_text = "\n".join([
        f"  • {m['timestamp'][:19]} — CPU: {m['cpu_percent']}%, RAM: {m['ram_percent']}%, Disk: {m['disk_percent']}%"
        for m in metrics_history
    ])

    prompt = f"""Ты — AI-системный администратор. Проанализируй метрики сервера за последние часы:

{metrics_text}

Дай краткий анализ на русском языке (3-5 предложений):
1. Есть ли аномалии или тренды роста нагрузки?
2. Какие ресурсы под давлением?
3. Конкретные рекомендации по оптимизации.

Отвечай по делу, без воды."""

    try:
        # Проверка, что Ollama вообще жив
        ping = requests.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=10,
            proxies={"http": None, "https": None}  # локально, без прокси!
        )
        if ping.status_code != 200:
            return f"❌ Ollama недоступна (код {ping.status_code}). Запусти: ollama serve"

        # Сам запрос к модели
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120,  # qwen2.5:3b может думать до 60 сек
            proxies={"http": None, "https": None}  # локально, без прокси!
        )

        if response.status_code == 200:
            result = response.json()
            answer = result.get("response", "").strip()
            if answer:
                return answer
            return "⚠️ Ollama ответила, но без текста."

        # Логируем тело ошибки — там часто причина
        logging.error(f"Ollama вернула {response.status_code}: {response.text[:300]}")
        return f"❌ Ошибка Ollama: код {response.status_code}\n{response.text[:200]}"

    except requests.exceptions.ConnectionError:
        return "❌ Ollama не запущена. Выполни: ollama serve"
    except requests.exceptions.Timeout:
        return "⏱ Ollama думает слишком долго (>120 сек). Попробуй ещё раз или используй модель поменьше."
    except Exception as e:
        logging.error(f"Ошибка AI-анализа: {e}")
        return f"❌ Неожиданная ошибка: {e}"