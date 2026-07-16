"""
公共工具模块
包含配置读取、加解密等共享功能
"""
import os
import sys
import json
import base64
import platform
from pathlib import Path
from datetime import datetime


def read_config() -> dict:
    """
    读取 config.yml 文件
    
    Returns:
        配置字典
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    config = {}
    with open(config_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    config[key] = value
    return config


def get_config_dir() -> str:
    """
    获取配置文件目录（使用AppData目录）
    
    Returns:
        配置目录路径
    """
    # 使用 %APPDATA%/EmailTodoApp 目录
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(appdata, 'EmailTodoApp')
    else:
        # macOS/Linux: ~/.config/EmailTodoApp
        config_dir = os.path.join(os.path.expanduser('~'), '.config', 'EmailTodoApp')
    
    # 确保目录存在
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_db_path() -> str:
    """
    获取数据库路径
    
    Returns:
        数据库文件路径
    """
    return os.path.join(get_config_dir(), "todos.db")


def get_encryption_key() -> bytes:
    """
    生成或获取加密密钥（基于机器特征）
    密钥在同一台机器上是一致的
    
    Returns:
        加密密钥
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    
    machine_id = f"{platform.node()}-{platform.system()}-email-todo-app"
    salt = b'email_todo_salt_v1'
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
    return key


def encrypt_password(password: str) -> str:
    """
    加密密码
    
    Args:
        password: 明文密码
        
    Returns:
        加密后的密码字符串
    """
    if not password:
        return ""
    from cryptography.fernet import Fernet
    
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(password.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_password(encrypted_password: str) -> str:
    """
    解密密码
    
    Args:
        encrypted_password: 加密的密码字符串
        
    Returns:
        解密后的明文密码
    """
    if not encrypted_password:
        return ""
    try:
        from cryptography.fernet import Fernet
        
        key = get_encryption_key()
        f = Fernet(key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode())
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        print(f"解密密码失败: {e}")
        return ""


def get_log_dir() -> str:
    """
    获取日志目录
    
    Returns:
        日志目录路径
    """
    log_dir = os.path.join(get_config_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def log(message: str, prefix: str = ""):
    """
    记录日志，同时输出到终端和按天存储的日志文件
    
    Args:
        message: 日志消息
        prefix: 日志前缀标签（如 "LLM返回", "POP3" 等）
    """
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 格式化日志行
    if prefix:
        log_line = f"[{timestamp}] [{prefix}] {message}"
    else:
        log_line = f"[{timestamp}] {message}"
    
    # 输出到终端（避免 Windows 控制台 GBK 编码导致的乱码）
    try:
        safe_line = log_line.encode(sys.stdout.encoding or 'gbk', errors='replace').decode(
            sys.stdout.encoding or 'gbk')
        print(safe_line)
    except Exception:
        print(log_line)
    
    # 写入日志文件（按天命名）
    try:
        log_dir = get_log_dir()
        log_file = os.path.join(log_dir, f"{now.strftime('%Y-%m-%d')}.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception as e:
        print(f"写入日志文件失败: {e}")
