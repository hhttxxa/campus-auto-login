"""后台检测循环（p4a Service 入口，PC 也可直接运行）。

每轮：
  1. check_status(cfg)
     - off_campus → 跳过（手机不在校园网）
     - online     → 若 relogin_when_online：注销→冷却→登录；否则保持
     - offline    → 登录
  2. 保存状态、写日志
  3. sleep(interval)，循环

Android 上以“前台 Service + 常驻通知”运行，避免系统杀进程。
"""
import sys
import time

import requests

import config_store
import drcom
import state

_running = True


def stop():
    global _running
    _running = False


def _is_android():
    return "android" in sys.platform or _has_module("jnius")


def _has_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def start_foreground():
    """Android：把 Service 提升为前台并显示常驻通知。失败则静默跳过。"""
    try:
        from jnius import autoclass

        PythonService = autoclass("org.kivy.android.PythonService")
        m_service = PythonService.mService
        if not m_service:
            return
        Context = autoclass("android.content.Context")
        NotificationCompat = autoclass("androidx.core.app.NotificationCompat")

        channel_id = "campus_login_service"
        # Android O+ 需要通知渠道
        try:
            NotificationChannel = autoclass("android.app.NotificationChannel")
            NotificationManager = autoclass("android.app.NotificationManager")
            nm = m_service.getSystemService(Context.NOTIFICATION_SERVICE)
            channel = NotificationChannel(channel_id, "校园网登录服务", NotificationManager.IMPORTANCE_LOW)
            nm.createNotificationChannel(channel)
        except Exception:
            pass

        builder = NotificationCompat.Builder(m_service, channel_id)
        builder.setContentTitle("校园网自动登录")
        builder.setContentText("正在后台维护登录状态")
        builder.setSmallIcon(m_service.getApplicationInfo().icon)
        builder.setOngoing(True)
        m_service.startForeground(1, builder.build())
    except Exception as e:
        state.log(f"前台通知设置失败（不影响登录功能）: {e}")


def tick(cfg, session):
    """执行一轮检测。返回本轮状态字符串。"""
    st = drcom.check_status(cfg, session)
    behavior = cfg.get("behavior", {})

    if st == "off_campus":
        state.log("不在校园网，跳过")
    elif st == "online":
        if behavior.get("relogin_when_online", True):
            state.log("已登录，执行 注销→重登")
            ok, info = drcom.logout(cfg, session)
            state.log(f"  注销: {'成功' if ok else '失败'} | {info}")
            cooldown = behavior.get("cooldown_after_logout_seconds", 3)
            for _ in range(int(cooldown)):
                if not _running:
                    break
                time.sleep(1)
            ok, info = drcom.login(cfg, session)
            state.log(f"  登录: {'成功' if ok else '失败'} | {info}")
        else:
            state.log("已登录，保持")
    else:  # offline
        state.log("未登录，执行登录")
        ok, info = drcom.login(cfg, session)
        state.log(f"  登录: {'成功' if ok else '失败'} | {info}")

    state.save_state(st, last_action=time.time())
    return st


def run():
    global _running
    _running = True
    state.log("===== 服务启动 =====")
    if _is_android():
        start_foreground()

    session = requests.Session()
    while _running:
        try:
            cfg = config_store.load_config()
            interval = int(cfg.get("check", {}).get("interval_seconds", 120))
            tick(cfg, session)
        except Exception as e:
            state.log(f"循环异常: {e}")
            interval = 60
        # 分段睡眠，保证 stop() 响应及时
        for _ in range(max(5, interval)):
            if not _running:
                break
            time.sleep(1)

    state.log("===== 服务停止 =====")


def main():
    run()


if __name__ == "__main__":
    main()
