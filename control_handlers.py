#!/usr/bin/env python3
"""
AI-Sysadmin: обработчики команд полного управления
"""

import full_control


def register_control_commands(bot, E_CROSS, E_CHECK, E_WARN, E_GEAR, E_FOLDER, E_GLOBE, E_PACKAGE, E_SHIELD, E_DOCKER, E_DISK):
    
    @bot.message_handler(commands=["cmd"])
    def cmd_execute(message):
        """Выполнить команду"""
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /cmd &lt;команда&gt;\n\nПример: /cmd ls -la /home")
            return
        
        command = args[1]
        bot.reply_to(message, f"⏳ Выполняю: {command}")
        
        result = full_control.FullControl.execute_command(command)
        
        if 'error' in result:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        if result['dangerous']:
            bot.send_message(message.chat.id, f"{E_WARN} <b>Внимание!</b> Это опасная команда.\n\n<pre>{result['output']}</pre>", parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, f"<pre>{result['output']}</pre>", parse_mode="HTML")
    
    @bot.message_handler(commands=["users"])
    def cmd_users(message):
        """Показать список пользователей"""
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
        
        text += "\n<i>Используй /create_user &lt;имя&gt; для создания</i>"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["create_user"])
    def cmd_create_user(message):
        """Создать пользователя"""
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /create_user &lt;имя&gt; [пароль] [sudo]\n\nПример: /create_user testuser testpass sudo")
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
        """Показать cron-задачи"""
        bot.reply_to(message, f"{E_GEAR} Загружаю cron-задачи...")
        
        result = full_control.FullControl.list_cron_jobs()
        
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        text = f"{E_GEAR} <b>Cron-задачи ({result['user']})</b>\n\n"
        text += f"<pre>{result['jobs']}</pre>"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["add_cron"])
    def cmd_add_cron(message):
        """Добавить cron-задачу"""
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /add_cron &lt;расписание и команда&gt;\n\nПример: /add_cron 0 2 * * * /usr/bin/backup.sh")
            return
        
        job = args[1]
        bot.reply_to(message, f"⏳ Добавляю cron-задачу...")
        
        result = full_control.FullControl.add_cron_job(job)
        
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        bot.send_message(message.chat.id, f"{E_CHECK} {result['message']}")
    
    @bot.message_handler(commands=["firewall"])
    def cmd_firewall(message):
        """Показать статус firewall"""
        bot.reply_to(message, f"{E_SHIELD} Загружаю статус firewall...")
        
        result = full_control.FullControl.firewall_status()
        
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        text = f"{E_SHIELD} <b>Firewall ({result['type']})</b>\n\n"
        text += f"<pre>{result['status']}</pre>"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["add_firewall_rule"])
    def cmd_add_firewall_rule(message):
        """Добавить правило firewall"""
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /add_firewall_rule &lt;правило&gt;\n\nПример: /add_firewall_rule allow 22/tcp")
            return
        
        rule = args[1]
        bot.reply_to(message, f"⏳ Добавляю правило firewall...")
        
        result = full_control.FullControl.firewall_add_rule(rule)
        
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        bot.send_message(message.chat.id, f"{E_CHECK} Правило добавлено: {rule}\n\n<pre>{result['output']}</pre>", parse_mode="HTML")
    
    @bot.message_handler(commands=["updates"])
    def cmd_updates(message):
        """Проверить обновления"""
        bot.reply_to(message, f"{E_PACKAGE} Проверяю обновления...")
        
        result = full_control.FullControl.check_updates()
        
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        text = f"{E_PACKAGE} <b>Доступные обновления</b>\n\n"
        text += f"Найдено: <b>{result['updates_available']}</b> пакетов\n\n"
        
        if result['packages']:
            text += "<b>Пакеты:</b>\n"
            for pkg in result['packages'][:10]:
                text += f"• {pkg}\n"
        
        text += "\n<i>Используй /install_updates для установки</i>"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["install_updates"])
    def cmd_install_updates(message):
        """Установить обновления"""
        bot.reply_to(message, f"{E_PACKAGE} Устанавливаю обновления... (это может занять несколько минут)")
        
        result = full_control.FullControl.install_updates()
        
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        bot.send_message(message.chat.id, f"{E_CHECK} Обновления установлены!\n\n<pre>{result['output']}</pre>", parse_mode="HTML")
    
    @bot.message_handler(commands=["docker"])
    def cmd_docker(message):
        """Показать Docker-контейнеры"""
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
        
        text += "\n<i>Используй /docker_action &lt;id&gt; &lt;действие&gt;</i>"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["docker_action"])
    def cmd_docker_action(message):
        """Выполнить действие над Docker-контейнером"""
        args = message.text.split()
        if len(args) < 3:
            bot.reply_to(message, f"{E_CROSS} Использование: /docker_action &lt;id&gt; &lt;действие&gt;\n\nДействия: start, stop, restart, rm")
            return
        
        container_id = args[1]
        action = args[2]
        
        bot.reply_to(message, f"⏳ Выполняю {action} для {container_id}...")
        
        result = full_control.FullControl.docker_action(container_id, action)
        
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        bot.send_message(message.chat.id, f"{E_CHECK} {action} выполнен для {container_id}\n\n<pre>{result['output']}</pre>", parse_mode="HTML")
    
    @bot.message_handler(commands=["disks"])
    def cmd_disks(message):
        """Показать информацию о дисках"""
        bot.reply_to(message, f"{E_DISK} Загружаю информацию о дисках...")
        
        result = full_control.FullControl.disk_info()
        
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        text = f"{E_DISK} <b>Диски и разделы</b>\n\n"
        text += f"<pre>{result['disks']}</pre>"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    @bot.message_handler(commands=["backup"])
    def cmd_backup(message):
        """Создать резервную копию"""
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, f"{E_CROSS} Использование: /backup &lt;путь&gt;\n\nПример: /backup /home/flippant/ai-sysadmin")
            return
        
        source = args[1]
        bot.reply_to(message, f"⏳ Создаю резервную копию {source}...")
        
        result = full_control.FullControl.create_backup(source)
        
        if not result['success']:
            bot.send_message(message.chat.id, f"{E_CROSS} {result['error']}")
            return
        
        size_mb = result['size'] / (1024 * 1024)
        bot.send_message(message.chat.id, f"{E_CHECK} Бэкап создан!\n\n Путь: {result['backup_path']}\n📊 Размер: {size_mb:.2f} MB")
