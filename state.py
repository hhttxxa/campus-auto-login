"""状态与日志持久化。UI 和后台 Service 通过文件共享（避免跨进程 IPC 复杂度）。

- logs/app.log：追加写日志行
- state.json：最近一次状态快照
"""
import json
import os
import time

from config_store import data_dir


def _log_path():
    return os.path.join(data_dir(), "logs", "app.log")


def _state_path():
    return os.path.join(data_dir(), "state.json")


def log(msg):
    """追加一行日志，返回带时间戳的完整行。"""
    os.makedirs(os.path.dirname(_log_path()), exist_ok=True)
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    return line


def save_state(status, last_action=None, extra=None):
    data = {
        "status": status,
        "last_action": last_action,
        "updated": time.time(),
    }
    if extra:
        data.update(extra)
    try:
        os.makedirs(os.path.dirname(_state_path()), exist_ok=True)
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass


def load_state():
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def read_logs(n=200):
    try:
        with open(_log_path(), "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [ln.rstrip("\n") for ln in lines[-n:]]
    except OSError:
        return []


def clear_logs():
    try:
        with open(_log_path(), "w", encoding="utf-8") as f:
            f.write("")
    except OSError:
        pass
