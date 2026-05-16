import json
import math
import time
import os
import importlib

import requests

# Lấy discord_config_path an toàn từ Define, có fallback
try:
    DefineModule = importlib.import_module("Define")
    discord_config_path = getattr(DefineModule, "discord_config_path", None)
except Exception:
    DefineModule = None
    discord_config_path = None

if discord_config_path is None:
    # Fallback: đoán root đường dẫn để lấy file cấu hình chung (ít khắt khe hơn)
    if os.name == "nt":
        root_guess = os.path.dirname(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    else:
        root_guess = "/app" if os.path.exists("/app/code/_settings/config.txt") else "/home/ubuntu/fr_bot"
    candidate_paths = [
        os.path.join(root_guess, "code", "_settings", "config.json"),
        os.path.join(root_guess, "_settings", "config.json"),
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            discord_config_path = p
            break

current_step = 0

bar = ['→', '↘', '↓', '↙', '←', '↖', '↑', '↗']

def step(messages=None):
    if messages is None:
        messages = ["Running..."]
    global current_step
    current_step += 1
    if current_step >= 8:
        current_step = 0

    clear_lines = "\033[K" * len(messages)  # Xóa tất cả các dòng cũ
    move_cursor_up = f"\033[{len(messages) + 1}A"  # Đưa con trỏ lên trên

    output = "\n".join(f"{msg}" for msg in messages) + f"\n{bar[current_step]}..."
    print(f"{clear_lines}\n{output}{move_cursor_up}\r", end='', flush=True)

def clear_console():
    """
    Clear the console output.
    """
    print("\033[2J\033[H", end='', flush=True)

def try_this(func, params, log_func, retries=5, delay=10):
    """
    Retry a function with specified parameters up to a number of retries.
    """
    log_func(f"Try {func.__name__}: {params}, retries: {retries}, delay: {delay} seconds")
    if params is None:
        params = {}
    for attempt in range(retries):
        try:
            return func(**params)
        except Exception as e:
            log_func(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    log_func("All attempts failed")
    raise Exception("All attempts failed")

def write_log(message, filename):
    """
    Write a log message to a file.
    """
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    print(f"[{timestamp}] - {message}")
    # Tạo thư mục cha nếu chưa tồn tại (hỗ trợ volume trống)
    parent = os.path.dirname(filename)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(filename, 'a') as f:
        f.write(f"{timestamp} - {message}\n")
    # DONE

def check_config_empty_by_error(fields):
    for field in fields:
        if not field:
            raise ValueError(f"Missing configuration for {field}")

# Đọc webhook discord nếu có cấu hình
webhook_url = ''
if discord_config_path and os.path.exists(discord_config_path):
    try:
        with open(discord_config_path, 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
        webhook_url = config.get('discord', {}).get('webhook', '')
    except Exception:
        webhook_url = ''

def push_notification(message):
    """
    Gửi thông báo đến Discord thông qua webhook.
    :param message: Nội dung thông báo
    """
    if not webhook_url:
        return False
    data = {
        "content": message
    }
    try:
        response = requests.post(webhook_url, json=data)
        return response.status_code == 204
    except Exception:
        return False


def round_keep_n_digits(x, n=2):
    if x == 0:
        return 0
    digits = int(math.log10(abs(x))) + 1  # số chữ số của x
    scale = 10 ** (digits - n)            # tỉ lệ để làm tròn
    return round(x / scale) * scale
