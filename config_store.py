"""配置读写。

配置文件 config.json 存放在 App 数据目录：
- Android：UI 与后台 Service 同属一个包，共享 getFilesDir()，配置互通。
- PC：当前工作目录，方便调试。

Dr.COM ePortal 的登录/注销协议（URL、AES 密钥、字段结构）已硬编码在 drcom.py，
配置文件只需账号密码 + 检测参数 + 行为开关。
"""
import json
import os

DEFAULT_CONFIG = {
    "portal": {"base_url": "http://172.17.0.2"},
    "credentials": {"username": "", "password": ""},
    "check": {
        "probe_url": "http://connect.rom.miui.com/generate_204",
        "interval_seconds": 120,
        "timeout_seconds": 5,
    },
    "behavior": {
        "relogin_when_online": True,
        "cooldown_after_logout_seconds": 3,
    },
}


def _android_files_dir():
    """Android 上获取 App 私有 files 目录（UI / Service 共用）。失败返回 None。"""
    try:
        from jnius import autoclass

        try:
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            if activity:
                return activity.getFilesDir().getAbsolutePath()
        except Exception:
            pass
        try:
            service = autoclass("org.kivy.android.PythonService").mService
            if service:
                return service.getFilesDir().getAbsolutePath()
        except Exception:
            pass
    except Exception:
        pass
    return None


def data_dir():
    """返回数据目录。优先级：环境变量 > Android files dir > Kivy user_data_dir > cwd。"""
    if "CAMPUS_DATA_DIR" in os.environ:
        return os.environ["CAMPUS_DATA_DIR"]
    d = _android_files_dir()
    if d:
        return d
    try:
        from kivy.app import App

        app = App.get_running_app()
        if app is not None:
            return app.user_data_dir
    except Exception:
        pass
    return os.getcwd()


def config_path():
    return os.path.join(data_dir(), "config.json")


def _merge(base, override):
    """深合并：override 覆盖 base，base 提供缺失键。"""
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config():
    """读取 config.json 并与默认值合并。文件不存在则返回默认配置。"""
    p = config_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            user = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)
    return _merge(DEFAULT_CONFIG, user)


def save_config(cfg):
    d = data_dir()
    os.makedirs(d, exist_ok=True)
    clean = _strip_comments(cfg)
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def _strip_comments(obj):
    if isinstance(obj, dict):
        return {k: _strip_comments(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_comments(x) for x in obj]
    return obj
