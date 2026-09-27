#!/usr/bin/env python3
"""
AI-Sysadmin: обработчики команд полного управления Linux
Все обработчики на верхнем уровне — никаких scope-проблем
"""

import full_control
import html


def register_all_handlers(bot, E_CROSS, E_CHECK, E_WARN, E_GEAR, E_FOLDER,
                          E_GLOBE, E_PACKAGE, E_SHIELD, E_DOCKER, E_DISK):
    """Регистрирует ВСЕ обработчики: и команды, и кнопки"""
    
    # ===== КОМАНДЫ =====
    
    @bot.message_handler(commands=["cmd"])
    def cmd_execute(message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /cmd &lt;команда&gt;\nПример: /cmd ls -la /home")
            return
        command = args[1]
        bot.reply_to(message, f"⏳ Выполняю: {command}")
        result = full_control.FullControl.execute_command(command)
        if 'error' in result:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        emoji = E_WARN if result.get('dangerous') else ""
        bot.send_message(message.chat.id, f"{emoji}<pre>{html.escape(result['output'])}</pre>", parse_mode="HTML")
    
    @bot.message_handler(commands=["users"])
    def cmd_users(message):
        bot.reply_to(message, f"{E_GEAR} Загружаю список пользователей...")
        users = full_control.FullControl.list_users()
        if 'error' in users[0]:
            bot.send_message(message.chat.id, f"{E_CROSS} {users[0]['error']}")
            return
        text = f"{E_GEAR} <b>Пользователи системы</b>\n\n"
        for user in users[:15]:
            text += f"👤 <b>{user['username']}</b>\n"
            text += f"   UID: {user['uid']} | GID: {user['gid']}\n"
            text += f"   Дом: {user['home']}\n"
            text += f"   Shell: {user['shell']}\n\n"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["create_user"])
    def cmd_create_user(message):
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /create_user &lt;имя&gt; [пароль] [sudo]")
            return
        username = args[1]
        password = args[2] if len(args) > 2 else None
        sudo = 'sudo' in args
        bot.reply_to(message, f"⏳ Создаю пользователя {username}...")
        result = full_control.FullControl.create_user(username, password, sudo)
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        bot.send_message(message.chat.id, f"{E_CHECK} {result['message']}")
    
    @bot.message_handler(commands=["cron"])
    def cmd_cron(message):
        bot.reply_to(message, f"{E_GEAR} Загружаю cron-задачи...")
        result = full_control.FullControl.list_cron_jobs()
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        text = f"{E_GEAR} <b>Cron-задачи ({result['user']})</b>\n\n<pre>{result['jobs']}</pre>"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["add_cron"])
    def cmd_add_cron(message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /add_cron &lt;расписание и команда&gt;")
            return
        bot.reply_to(message, f"⏳ Добавляю cron-задачу...")
        result = full_control.FullControl.add_cron_job(args[1])
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        bot.send_message(message.chat.id, f"{E_CHECK} {result['message']}")
    
    @bot.message_handler(commands=["firewall"])
    def cmd_firewall(message):
        bot.reply_to(message, f"{E_SHIELD} Загружаю статус firewall...")
        result = full_control.FullControl.firewall_status()
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        text = f"{E_SHIELD} <b>Firewall ({result['type']})</b>\n\n<pre>{result['status']}</pre>"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["add_firewall_rule"])
    def cmd_add_firewall_rule(message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /add_firewall_rule &lt;правило&gt;")
            return
        bot.reply_to(message, f" Добавляю правило firewall...")
        result = full_control.FullControl.firewall_add_rule(args[1])
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        bot.send_message(message.chat.id, f"{E_CHECK} Правило добавлено\n<pre>{result['output']}</pre>", parse_mode="HTML")
    
    @bot.message_handler(commands=["updates"])
    def cmd_updates(message):
        bot.reply_to(message, f"{E_PACKAGE} Проверяю обновления...")
        result = full_control.FullControl.check_updates()
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        text = f"{E_PACKAGE} <b>Доступные обновления</b>\n\nНайдено: <b>{result['updates_available']}</b> пакетов\n\n"
        if result['packages']:
            text += "<b>Пакеты:</b>\n"
            for pkg in result['packages'][:10]:
                text += f"• {pkg}\n"
        text += "\n<i>Используй /install_updates для установки</i>"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["install_updates"])
    def cmd_install_updates(message):
        bot.reply_to(message, f"{E_PACKAGE} Устанавливаю обновления... (может занять несколько минут)")
        result = full_control.FullControl.install_updates()
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        bot.send_message(message.chat.id, f"{E_CHECK} Обновления установлены!\n<pre>{result['output']}</pre>", parse_mode="HTML")
    
    @bot.message_handler(commands=["docker"])
    def cmd_docker(message):
        bot.reply_to(message, f"{E_DOCKER} Загружаю Docker-контейнеры...")
        containers = full_control.FullControl.list_docker_containers(True)
        if 'error' in containers[0]:
            bot.send_message(message.chat.id, f"{E_CROSS} {containers[0]['error']}")
            return
        text = f"{E_DOCKER} <b>Docker-контейнеры</b>\n\n"
        for c in containers[:10]:
            status_emoji = "🟢" if "Up" in c['status'] else "🔴"
            text += f"{status_emoji} <b>{c['name']}</b>\n"
            text += f"   ID: {c['id']}\n"
            text += f"   Image: {c['image']}\n"
            text += f"   Status: {c['status']}\n"
            text += f"   Ports: {c['ports']}\n\n"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["docker_action"])
    def cmd_docker_action(message):
        args = message.text.split()
        if len(args) < 3:
            bot.reply_to(message, f"{E_CROSS} Использование: /docker_action &lt;id&gt; &lt;действие&gt;\nДействия: start, stop, restart, rm")
            return
        bot.reply_to(message, f"⏳ Выполняю {args[2]} для {args[1]}...")
        result = full_control.FullControl.docker_action(args[1], args[2])
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        bot.send_message(message.chat.id, f"{E_CHECK} {args[2]} выполнен для {args[1]}\n<pre>{result['output']}</pre>", parse_mode="HTML")
    
    @bot.message_handler(commands=["disks"])
    def cmd_disks(message):
        bot.reply_to(message, f"{E_DISK} Загружаю информацию о дисках...")
        result = full_control.FullControl.disk_info()
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        text = f"{E_DISK} <b>Диски и разделы</b>\n\n<pre>{result['disks']}</pre>"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["backup"])
    def cmd_backup(message):
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /backup &lt;путь&gt;")
            return
        bot.reply_to(message, f"⏳ Создаю резервную копию {args[1]}...")
        result = full_control.FullControl.create_backup(args[1])
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        size_mb = result['size'] / (1024 * 1024)
        bot.send_message(message.chat.id, f"{E_CHECK} Бэкап создан!\n\n📁 Путь: {result['backup_path']}\n📊 Размер: {size_mb:.2f} MB")
    
    @bot.message_handler(commands=["wifi"])
    def cmd_wifi(message):
        """Показать информацию о Wi-Fi"""
        bot.reply_to(message, f"{E_GLOBE} Сканирую Wi-Fi сети... (может занять 10-20 сек)")
        result = full_control.FullControl.wifi_info()
        if 'error' in result:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        text = f"📶 <b>Wi-Fi информация</b>\n\n"
        text += f"<b>Интерфейс:</b> {result['interface']}\n\n"
        
        if result['link_info']:
            text += f"<b>Подключение:</b>\n<pre>{html.escape(result['link_info'][:500])}</pre>\n\n"
        
        if result['networks']:
            text += f"<b>Доступные сети (топ-10):</b>\n"
            for i, net in enumerate(result['networks'], 1):
                signal_emoji = "🟢" if int(net.get('signal', '-999').replace(' dBm', '')) > -70 else "🟡" if int(net.get('signal', '-999').replace(' dBm', '')) > -80 else "🔴"
                text += f"{signal_emoji} <b>{i}. {net['ssid']}</b>\n"
                text += f"   Сигнал: {net.get('signal', 'N/A')}\n"
                text += f"   Частота: {net.get('freq', 'N/A')}\n\n"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    # ===== КНОПКИ КЛАВИАТУРЫ =====
    
    @bot.message_handler(func=lambda message: message.text == "🖥 Терминал")
    def btn_terminal(message):
        bot.reply_to(message, "🖥 <b>Терминал</b>\n\nИспользуй команду:\n/cmd &lt;команда&gt;\n\nПример: /cmd ls -la /home\n\n⚠️ Опасные команды блокируются whitelist'ом.", parse_mode="HTML")
    
    @bot.message_handler(func=lambda message: message.text == "👥 Пользователи")
    def btn_users(message):
        cmd_users(message)
    
    @bot.message_handler(func=lambda message: message.text == "🐳 Docker")
    def btn_docker(message):
        cmd_docker(message)
    
    @bot.message_handler(func=lambda message: message.text == "🛡 Firewall")
    def btn_firewall(message):
        cmd_firewall(message)
    

    @bot.message_handler(func=lambda message: message.text == "🌐 Сеть")
    @bot.message_handler(func=lambda message: message.text == "🌐 Сеть")
    def btn_network(message):
        bot.reply_to(message, f"{E_GLOBE} Загружаю сетевую информацию...")
        result = full_control.FullControl.network_info()
        if 'error' in result:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        text = f"{E_GLOBE} <b>Сетевая информация</b>\n\n"
        text += f"<b>Интерфейсы:</b>\n<pre>{html.escape(result.get('interfaces', 'нет данных'))}</pre>\n\n"
        text += f"<b>Открытые порты:</b>\n<pre>{html.escape(result.get('listening_ports', 'нет данных'))}</pre>"
        bot.send_message(message.chat.id, text, parse_mode="HTML")


    @bot.message_handler(func=lambda message: message.text == "📶 Wi-Fi")
    def btn_wifi(message):
        cmd_wifi(message)
    
    print("✅ Все обработчики (команды + кнопки) зарегистрированы!")
