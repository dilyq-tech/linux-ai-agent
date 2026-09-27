#!/usr/bin/env python3
"""
AI-Sysadmin: модуль управления Linux-сервером
"""

import subprocess
import os
from typing import List, Dict, Optional


class LinuxManager:
    ALLOWED_SERVICES = [
        'ssh', 'nginx', 'apache2', 'mysql', 'postgresql', 'redis',
        'docker', 'cron', 'systemd-journald', 'NetworkManager'
    ]

    @staticmethod
    def list_services(limit: int = 20) -> List[Dict]:
        try:
            result = subprocess.run(
                ['systemctl', 'list-units', '--type=service', '--all', '--no-pager', '-n', str(limit)],
                capture_output=True, text=True, timeout=10
            )
            services = []
            for line in result.stdout.split('\n')[1:]:
                if line.strip() and '.service' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        services.append({
                            'name': parts[0],
                            'load': parts[1],
                            'active': parts[2],
                            'sub': parts[3],
                            'description': ' '.join(parts[4:]) if len(parts) > 4 else ''
                        })
            return services
        except Exception as e:
            return [{'error': str(e)}]

    @staticmethod
    def service_status(service_name: str) -> Dict:
        if service_name not in LinuxManager.ALLOWED_SERVICES:
            return {'error': f'Сервис {service_name} не в whitelist'}
        try:
            result = subprocess.run(
                ['systemctl', 'status', service_name],
                capture_output=True, text=True, timeout=10
            )
            return {
                'name': service_name,
                'status': 'active' if result.returncode == 0 else 'inactive',
                'output': result.stdout[:500]
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def service_action(service_name: str, action: str) -> Dict:
        if service_name not in LinuxManager.ALLOWED_SERVICES:
            return {'error': f'Сервис {service_name} не в whitelist'}
        if action not in ['start', 'stop', 'restart', 'enable', 'disable']:
            return {'error': f'Недопустимое действие: {action}'}
        try:
            result = subprocess.run(
                ['sudo', 'systemctl', action, service_name],
                capture_output=True, text=True, timeout=30
            )
            return {
                'service': service_name,
                'action': action,
                'success': result.returncode == 0,
                'output': result.stdout + result.stderr
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def top_processes(limit: int = 10) -> List[Dict]:
        try:
            result = subprocess.run(
                ['ps', 'aux', '--sort=-%cpu'],
                capture_output=True, text=True, timeout=10
            )
            processes = []
            for line in result.stdout.split('\n')[1:limit+1]:
                if line.strip():
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        processes.append({
                            'user': parts[0],
                            'pid': parts[1],
                            'cpu': parts[2],
                            'mem': parts[3],
                            'command': parts[10][:100]
                        })
            return processes
        except Exception as e:
            return [{'error': str(e)}]

    @staticmethod
    def kill_process(pid: int, signal: str = 'SIGTERM') -> Dict:
        try:
            result = subprocess.run(
                ['sudo', 'kill', f'-{signal}', str(pid)],
                capture_output=True, text=True, timeout=10
            )
            return {
                'pid': pid,
                'signal': signal,
                'success': result.returncode == 0,
                'output': result.stdout + result.stderr
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def list_packages(search: Optional[str] = None, limit: int = 20) -> List[Dict]:
        try:
            cmd = ['dpkg', '-l']
            if search:
                cmd = ['dpkg', '-l', f'*{search}*']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            packages = []
            for line in result.stdout.split('\n')[5:5+limit]:
                if line.strip() and line[0] in ['i', 'r', 'p']:
                    parts = line.split(None, 3)
                    if len(parts) >= 3:
                        packages.append({
                            'status': parts[0],
                            'name': parts[1],
                            'version': parts[2],
                            'description': parts[3] if len(parts) > 3 else ''
                        })
            return packages
        except Exception as e:
            return [{'error': str(e)}]

    @staticmethod
    def list_directory(path: str = '/home') -> Dict:
        safe_paths = ['/home', '/tmp', '/var/log', '/etc', '/opt']
        if not any(path.startswith(p) for p in safe_paths):
            return {'error': f'Путь {path} не разрешён'}
        try:
            result = subprocess.run(['ls', '-lah', path], capture_output=True, text=True, timeout=10)
            return {
                'path': path,
                'content': result.stdout,
                'success': result.returncode == 0
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def read_file(path: str, lines: int = 50) -> Dict:
        safe_dirs = ['/home', '/tmp', '/var/log', '/etc']
        if not any(path.startswith(d) for d in safe_dirs):
            return {'error': f'Путь {path} не разрешён'}
        if not os.path.exists(path):
            return {'error': f'Файл {path} не существует'}
        try:
            with open(path, 'r') as f:
                content = f.readlines()[-lines:]
            return {
                'path': path,
                'content': ''.join(content),
                'success': True
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def network_info() -> Dict:
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
