#!/usr/bin/env python3
"""
AI-Sysadmin: полное управление Linux-сервером
"""

import subprocess
import os
import json
from typing import List, Dict, Optional
from datetime import datetime


class FullControl:
    """Класс для полного управления Linux-сервером"""
    
    # Опасные команды, которые требуют подтверждения
    DANGEROUS_COMMANDS = [
        'rm -rf', 'shutdown', 'reboot', 'halt', 'poweroff',
        'mkfs', 'dd if=', '> /dev/sd', 'chmod 777',
        'chown -R', 'userdel', 'groupdel'
    ]
    
    # Whitelist разрешённых команд
    ALLOWED_COMMANDS = [
        'ls', 'cat', 'grep', 'find', 'ps', 'top', 'htop',
        'df', 'du', 'free', 'uptime', 'who', 'w',
        'systemctl', 'journalctl', 'docker', 'crontab',
        'apt', 'dpkg', 'snap', 'flatpak',
        'ip', 'ss', 'ping', 'traceroute', 'nslookup',
        'useradd', 'usermod', 'passwd', 'groupadd',
        'ufw', 'iptables', 'chmod', 'chown',
        'tar', 'zip', 'unzip', 'gzip',
        'git', 'python3', 'pip', 'npm',
        'echo', 'printf', 'date', 'cal', 'history'
    ]
    
    @staticmethod
    def execute_command(command: str, timeout: int = 30) -> Dict:
        """Выполнить команду с проверкой безопасности"""
        # Проверка на опасные команды
        is_dangerous = any(cmd in command for cmd in FullControl.DANGEROUS_COMMANDS)
        
        # Проверка whitelist
        base_command = command.split()[0] if command.split() else ''
        is_allowed = any(cmd in base_command for cmd in FullControl.ALLOWED_COMMANDS)
        
        if not is_allowed and not is_dangerous:
            return {
                'success': False,
                'error': f'Команда не в whitelist: {base_command}',
                'dangerous': False
            }
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = result.stdout + result.stderr
            if len(output) > 2000:
                output = output[:2000] + "\n... (вывод обрезан)"
            
            return {
                'success': result.returncode == 0,
                'output': output,
                'dangerous': is_dangerous,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Команда выполнялась дольше {timeout} секунд',
                'dangerous': is_dangerous
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'dangerous': is_dangerous
            }
    
    @staticmethod
    def list_users() -> List[Dict]:
        """Получить список пользователей системы"""
        try:
            result = subprocess.run(
                ['cat', '/etc/passwd'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            users = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    parts = line.split(':')
                    if len(parts) >= 7 and int(parts[2]) >= 1000:  # Только обычные пользователи
                        users.append({
                            'username': parts[0],
                            'uid': parts[2],
                            'gid': parts[3],
                            'home': parts[5],
                            'shell': parts[6]
                        })
            return users
        except Exception as e:
            return [{'error': str(e)}]
    
    @staticmethod
    def create_user(username: str, password: str = None, sudo: bool = False) -> Dict:
        """Создать нового пользователя"""
        try:
            # Создаём пользователя
            cmd = ['sudo', 'useradd', '-m', '-s', '/bin/bash', username]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return {'success': False, 'error': result.stderr}
            
            # Устанавливаем пароль
            if password:
                cmd = ['sudo', 'chpasswd']
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                proc.communicate(input=f"{username}:{password}\n".encode())
            
            # Добавляем в sudo
            if sudo:
                cmd = ['sudo', 'usermod', '-aG', 'sudo', username]
                subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            return {
                'success': True,
                'username': username,
                'sudo': sudo,
                'message': f"Пользователь {username} создан" + (" с правами sudo" if sudo else "")
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def delete_user(username: str, delete_home: bool = False) -> Dict:
        """Удалить пользователя"""
        try:
            cmd = ['sudo', 'userdel']
            if delete_home:
                cmd.append('-r')
            cmd.append(username)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            return {
                'success': result.returncode == 0,
                'username': username,
                'delete_home': delete_home,
                'message': f"Пользователь {username} удалён" + (" вместе с домашней директорией" if delete_home else "")
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def list_cron_jobs(user: str = None) -> Dict:
        """Получить список cron-задач"""
        try:
            cmd = ['crontab', '-l']
            if user:
                cmd = ['sudo', 'crontab', '-l', '-u', user]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return {'success': False, 'error': 'Cron-задачи не найдены'}
            
            return {
                'success': True,
                'user': user or 'current',
                'jobs': result.stdout
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def add_cron_job(job: str, user: str = None) -> Dict:
        """Добавить cron-задачу"""
        try:
            # Получаем текущие задачи
            cmd = ['crontab', '-l']
            if user:
                cmd = ['sudo', 'crontab', '-l', '-u', user]
            
            current = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            current_jobs = current.stdout if current.returncode == 0 else ""
            
            # Добавляем новую задачу
            new_jobs = current_jobs + job + "\n"
            
            # Записываем обратно
            cmd = ['crontab', '-']
            if user:
                cmd = ['sudo', 'crontab', '-u', user, '-']
            
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.communicate(input=new_jobs.encode())
            
            return {
                'success': True,
                'job': job,
                'message': f"Cron-задача добавлена: {job}"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def remove_cron_job(line_number: int, user: str = None) -> Dict:
        """Удалить cron-задачу по номеру строки"""
        try:
            cmd = ['crontab', '-l']
            if user:
                cmd = ['sudo', 'crontab', '-l', '-u', user]
            
            current = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            lines = current.stdout.split('\n')
            
            if line_number < 1 or line_number > len(lines):
                return {'success': False, 'error': f'Неверный номер строки: {line_number}'}
            
            lines.pop(line_number - 1)
            new_jobs = '\n'.join(lines)
            
            cmd = ['crontab', '-']
            if user:
                cmd = ['sudo', 'crontab', '-u', user, '-']
            
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.communicate(input=new_jobs.encode())
            
            return {
                'success': True,
                'message': f"Cron-задача #{line_number} удалена"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def firewall_status() -> Dict:
        """Получить статус firewall"""
        try:
            # Проверяем UFW
            result = subprocess.run(['sudo', 'ufw', 'status', 'verbose'], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'type': 'ufw',
                    'status': result.stdout
                }
            
            # Если UFW не установлен, проверяем iptables
            result = subprocess.run(['sudo', 'iptables', '-L', '-n'], capture_output=True, text=True, timeout=10)
            
            return {
                'success': True,
                'type': 'iptables',
                'status': result.stdout[:2000]
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def firewall_add_rule(rule: str) -> Dict:
        """Добавить правило firewall"""
        try:
            result = subprocess.run(
                f"sudo ufw {rule}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return {
                'success': result.returncode == 0,
                'rule': rule,
                'output': result.stdout + result.stderr
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def check_updates() -> Dict:
        """Проверить доступные обновления"""
        try:
            result = subprocess.run(
                ['sudo', 'apt', 'list', '--upgradable'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            packages = [line for line in result.stdout.split('\n') if '/' in line]
            
            return {
                'success': True,
                'updates_available': len(packages),
                'packages': packages[:20]  # Первые 20 пакетов
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def install_updates() -> Dict:
        """Установить все обновления"""
        try:
            result = subprocess.run(
                ['sudo', 'apt', 'upgrade', '-y'],
                capture_output=True,
                text=True,
                timeout=300  # 5 минут на установку
            )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def list_docker_containers(all_containers: bool = False) -> List[Dict]:
        """Получить список Docker-контейнеров"""
        try:
            cmd = ['docker', 'ps']
            if all_containers:
                cmd.append('-a')
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            containers = []
            for line in result.stdout.split('\n')[1:]:
                if line.strip():
                    parts = line.split(None, 6)
                    if len(parts) >= 7:
                        containers.append({
                            'id': parts[0][:12],
                            'image': parts[1],
                            'command': parts[2][:30],
                            'created': parts[3] + ' ' + parts[4],
                            'status': parts[5],
                            'ports': parts[6] if len(parts) > 6 else '',
                            'name': parts[-1]
                        })
            return containers
        except Exception as e:
            return [{'error': str(e)}]
    
    @staticmethod
    def docker_action(container_id: str, action: str) -> Dict:
        """Выполнить действие над Docker-контейнером"""
        allowed_actions = ['start', 'stop', 'restart', 'pause', 'unpause', 'rm']
        
        if action not in allowed_actions:
            return {'success': False, 'error': f'Недопустимое действие: {action}'}
        
        try:
            result = subprocess.run(
                ['docker', action, container_id],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                'success': result.returncode == 0,
                'container': container_id,
                'action': action,
                'output': result.stdout + result.stderr
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    

    @staticmethod
    def network_info() -> Dict:
        """Получить сетевую информацию"""
        try:
            ip_result = subprocess.run(['ip', 'addr'], capture_output=True, text=True, timeout=10)
            ports_result = subprocess.run(['ss', '-tuln'], capture_output=True, text=True, timeout=10)
            conn_result = subprocess.run(['ss', '-tunp'], capture_output=True, text=True, timeout=10)
            return {
                'interfaces': ip_result.stdout[:1000],
                'listening_ports': ports_result.stdout[:1000],
                'active_connections': conn_result.stdout[:1000]
            }
        except Exception as e:
            return {'error': str(e)}


    @staticmethod
    def wifi_info() -> Dict:
        """Получить информацию о Wi-Fi"""
        try:
            # Проверяем есть ли Wi-Fi интерфейсы
            iw_result = subprocess.run(['iw', 'dev'], capture_output=True, text=True, timeout=10)
            
            if 'Interface' not in iw_result.stdout:
                return {'error': 'Wi-Fi интерфейс не найден'}
            
            # Находим Wi-Fi интерфейс
            wifi_interface = None
            for line in iw_result.stdout.split('\n'):
                if 'Interface' in line:
                    wifi_interface = line.split()[1]
                    break
            
            if not wifi_interface:
                return {'error': 'Wi-Fi интерфейс не найден'}
            
            # Получаем информацию о подключении
            link_result = subprocess.run(['iw', 'dev', wifi_interface, 'link'], capture_output=True, text=True, timeout=10)
            
            # Получаем список доступных сетей
            scan_result = subprocess.run(['iw', 'dev', wifi_interface, 'scan', 'ap-force'], capture_output=True, text=True, timeout=30)
            
            # Парсим сканирование
            networks = []
            current_ssid = None
            current_signal = None
            current_freq = None
            
            for line in scan_result.stdout.split('\n'):
                if line.startswith('BSS'):
                    if current_ssid:
                        networks.append({
                            'ssid': current_ssid,
                            'signal': current_signal,
                            'freq': current_freq
                        })
                    current_ssid = None
                    current_signal = None
                    current_freq = None
                elif 'SSID:' in line and 'SSID:' in line.split(':')[0]:
                    current_ssid = line.split(':', 1)[1].strip()
                elif 'signal:' in line:
                    current_signal = line.split(':')[1].strip().split()[0] + ' dBm'
                elif 'freq:' in line:
                    current_freq = line.split(':')[1].strip().split()[0] + ' MHz'
            
            if current_ssid:
                networks.append({
                    'ssid': current_ssid,
                    'signal': current_signal,
                    'freq': current_freq
                })
            
            # Сортируем по сигналу
            networks.sort(key=lambda x: x.get('signal', '-999 dBm'), reverse=True)
            
            return {
                'interface': wifi_interface,
                'link_info': link_result.stdout,
                'networks': networks[:10]  # Топ-10 сетей
            }
        except subprocess.TimeoutExpired:
            return {'error': 'Сканирование Wi-Fi заняло слишком много времени'}
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def disk_info() -> Dict:
        """Получить информацию о дисках"""
        try:
            result = subprocess.run(['lsblk', '-f'], capture_output=True, text=True, timeout=10)
            
            return {
                'success': True,
                'disks': result.stdout
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def create_backup(source: str, destination: str = '/tmp/backups') -> Dict:
        """Создать резервную копию"""
        try:
            # Создаём директорию для бэкапов
            os.makedirs(destination, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"backup_{os.path.basename(source)}_{timestamp}.tar.gz"
            backup_path = os.path.join(destination, backup_name)
            
            result = subprocess.run(
                ['tar', '-czf', backup_path, '-C', os.path.dirname(source), os.path.basename(source)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            return {
                'success': result.returncode == 0,
                'backup_path': backup_path,
                'size': os.path.getsize(backup_path) if os.path.exists(backup_path) else 0
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
