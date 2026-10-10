# log_searcher.py
import subprocess
import re
from datetime import datetime

def find_errors_in_logs(max_lines=500, max_errors=20):
    """
    Ищет ошибки в системных логах.
    
    max_lines: сколько строк логов проверить (по умолчанию 500)
    max_errors: сколько ошибок показать (по умолчанию 20)
    
    Возвращает: список строк с ошибками
    """
    # Шаблоны ошибок (регистронезависимо)
    error_patterns = re.compile(r'error|failed|critical|fatal|exception', re.IGNORECASE)
    
    try:
        # Получаем последние max_lines строк логов
        result = subprocess.run(
            ["journalctl", "-n", str(max_lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return ["journalctl недоступен"]
        
        # Разбиваем на строки
        lines = result.stdout.split('\n')
        
        # Фильтруем только ошибки
        errors = [line for line in lines if error_patterns.search(line)]
        
        # Берём последние max_errors ошибок
        return errors[-max_errors:] if errors else ["Ошибок не найдено ✅"]
        
    except subprocess.TimeoutExpired:
        return ["Превышено время ожидания (10 сек)"]
    except Exception as e:
        return [f"Ошибка: {e}"]


def get_auth_summary(max_lines=200):
    """
    Показывает сводку попыток входа в систему.
    
    Возвращает: текст с последними попытками входа
    """
    try:
        result = subprocess.run(
            ["journalctl", "-u", "ssh", "-n", str(max_lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return "SSH логи недоступны"
        
        lines = result.stdout.split('\n')
        
        # Считаем успешные и неудачные входы
        success = sum(1 for line in lines if 'Accepted' in line)
        failed = sum(1 for line in lines if 'Failed' in line or 'Invalid' in line)
        
        summary = f"🛡️ <b>Попытки входа (последние {max_lines} строк):</b>\n"
        summary += f"✅ Успешных: {success}\n"
        summary += f"❌ Неудачных: {failed}\n\n"
        
        # Показываем последние 10 попыток
        recent = [line for line in lines if 'Accepted' in line or 'Failed' in line][-10:]
        if recent:
            summary += "<b>Последние попытки:</b>\n"
            summary += "\n".join(recent)
        
        return summary
        
    except Exception as e:
        return f"Ошибка: {e}"
