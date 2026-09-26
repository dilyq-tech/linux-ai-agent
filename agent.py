import subprocess
import requests
import re

def run_command(cmd):
    # Очищаем команду от лишних символов
    cmd = cmd.strip().strip("'").strip('"').strip("`")
    
    # Проверяем что команда безопасная
    allowed_commands = ["df", "free", "ss", "systemctl", "tail", "uptime", "top", "ps", "cat", "ls", "who", "date", "hostname"]
    cmd_parts = cmd.split()
    if not cmd_parts or cmd_parts[0] not in allowed_commands:
        return f"Команда '{cmd}' не разрешена"
    
    try:
        result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=10)
        output = result.stdout or result.stderr
        return output if output else "Команда выполнена, вывод пустой"
    except FileNotFoundError:
        return f"Команда '{cmd}' не найдена"
    except Exception as e:
        return f"Ошибка выполнения: {str(e)}"

def ask_ollama(messages):
    try:
        url = "http://localhost:11434/api/chat"
        payload = {"model": "llama3.2", "messages": messages, "stream": False}
        response = requests.post(url, json=payload, timeout=120)
        data = response.json()
        return data["message"]["content"]
    except Exception as e:
        return f"Ошибка связи с AI: {str(e)}"

def extract_commands(text):
    # Извлекаем команды после "КОМАНДА:"
    commands = []
    lines = text.split("\n")
    for line in lines:
        if "КОМАНДА:" in line:
            cmd = line.split("КОМАНДА:")[1].strip()
            # Убираем лишние символы
            cmd = cmd.strip().strip("'").strip('"').strip("`").rstrip(".")
            if cmd:
                commands.append(cmd)
    return commands

def agent_loop(user_message, history):
    history.append({"role": "user", "content": user_message})
    
    # Роутер
    router_messages = history + [{"role": "user", "content": "Ответь только ДА или НЕТ: нужно ли выполнять Linux-команду для ответа на последний вопрос?"}]
    decision = ask_ollama(router_messages).strip().upper()
    print("Решение роутера: " + decision)
    
    if "ДА" in decision:
        system_msg = {"role": "system", "content": "Ты AI-помощник для диагностики Linux. Доступные команды: df -h, free -h, ss -tulnp, systemctl is-active <имя>, tail -n 50 <файл>, uptime. Ответь СТРОГО в формате: КОМАНДА: <точная команда без кавычек> АНАЛИЗ: <твой анализ после выполнения>."}
        diag_messages = [system_msg] + history
        text = ask_ollama(diag_messages)
        
        commands = extract_commands(text)
        
        if commands:
            results = []
            for cmd in commands:
                print("Выполняю: " + cmd)
                res = run_command(cmd)
                results.append(f"{cmd} => {res[:300]}")
                print("Результат: " + res[:100])
            
            history.append({"role": "assistant", "content": text})
            history.append({"role": "user", "content": f"Результаты выполнения команд:\n{chr(10).join(results)}\n\nДай финальный анализ на русском, кратко. Опирайся только на реальные данные."})
            text = ask_ollama(history)
        else:
            text = "Не удалось извлечь команды из ответа AI."
    else:
        system_msg = {"role": "system", "content": "Ты дружелюбный AI-помощник. Отвечай кратко на русском."}
        chat_messages = [system_msg] + history
        text = ask_ollama(chat_messages)
    
    history.append({"role": "assistant", "content": text})
    
    if len(history) > 10:
        history = history[-10:]
    
    print("\nОтвет агента:\n" + text)
    return history

if __name__ == "__main__":
    print("AI-Sysadmin с валидацией команд готов! Введи exit для выхода.\n")
    history = []
    while True:
        user_input = input("Ты: ").strip()
        if user_input.lower() in ["exit", "quit", "выход"]: break
        if user_input:
            try: history = agent_loop(user_input, history)
            except Exception as e: print("Ошибка: " + str(e))
