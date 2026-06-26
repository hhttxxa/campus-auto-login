"""校园网自动登录 App（Kivy UI）。

功能：
- 状态卡：当前状态、最近动作时间、下次检测倒计时
- 手动按钮：立即检测 / 手动登录 / 手动注销
- 配置表单：账号、密码、检测间隔、portal URL、relogin 开关
- 启动/停止后台服务
- 日志列表（自动刷新）

平台：
- Android：通过 p4a AndroidService 启动 service.py 后台运行
- PC：在子线程内直接跑 service.run()，方便调试
"""
import sys
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout

import config_store
import drcom
import service
import state

KV = """
<RootWidget>:
    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(8)

    ScrollView:
        size_hint_y: None
        height: dp(40)
        Label:
            text: '校园网自动登录（Dr.COM）'
            font_size: sp(20)
            size_hint_y: None
            height: dp(40)
            bold: True

    BoxLayout:
        size_hint_y: None
        height: dp(80)
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 0.95, 0.95, 0.97, 1
            Rectangle:
                pos: self.pos
                size: self.size
        padding: dp(10)
        spacing: dp(4)
        Label:
            id: status_label
            text: '状态：未知'
            font_size: sp(16)
            halign: 'left'
            text_size: self.size
        Label:
            id: detail_label
            text: ''
            font_size: sp(13)
            color: 0.4, 0.4, 0.4, 1
            halign: 'left'
            text_size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(8)
        Button:
            text: '立即检测'
            on_press: root.do_check()
        Button:
            text: '手动登录'
            on_press: root.do_login()
        Button:
            text: '手动注销'
            on_press: root.do_logout()

    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(8)
        Button:
            id: svc_btn
            text: '启动服务'
            on_press: root.toggle_service()
        Button:
            text: '清空日志'
            on_press: root.clear_logs()

    Label:
        text: '配置'
        font_size: sp(15)
        bold: True
        size_hint_y: None
        height: dp(24)

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        Label:
            text: '学号/账号'
            size_hint_x: 0.3
        TextInput:
            id: username
            multiline: False

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        Label:
            text: '密码'
            size_hint_x: 0.3
        TextInput:
            id: password
            multiline: False
            password: True

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        Label:
            text: '检测间隔(秒)'
            size_hint_x: 0.3
        TextInput:
            id: interval
            multiline: False
            input_filter: 'int'

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        Label:
            text: 'Portal URL'
            size_hint_x: 0.3
        TextInput:
            id: portal_url
            multiline: False

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        Label:
            text: '已登录则注销重登'
            size_hint_x: 0.7
        Switch:
            id: relogin
            active: True

    Button:
        text: '保存配置'
        size_hint_y: None
        height: dp(44)
        on_press: root.save_config()

    Label:
        text: '日志'
        font_size: sp(15)
        bold: True
        size_hint_y: None
        height: dp(24)

    ScrollView:
        Label:
            id: log_label
            text: ''
            font_size: sp(12)
            halign: 'left'
            valign: 'top'
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]
            color: 0.2, 0.2, 0.2, 1
"""


class RootWidget(BoxLayout):
    pass


class CampusApp(App):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._svc_thread = None
        self._android_svc = None

    def build(self):
        Builder.load_string(KV)
        root = RootWidget()
        self._load_config_to_ui(root)
        Clock.schedule_interval(self._refresh, 2)
        return root

    # ---------- 配置 ----------

    def _load_config_to_ui(self, root):
        cfg = config_store.load_config()
        root.ids.username.text = cfg.get("credentials", {}).get("username", "")
        root.ids.password.text = cfg.get("credentials", {}).get("password", "")
        root.ids.interval.text = str(cfg.get("check", {}).get("interval_seconds", 120))
        root.ids.portal_url.text = cfg.get("portal", {}).get("base_url", "http://172.17.0.2")
        root.ids.relogin.active = cfg.get("behavior", {}).get("relogin_when_online", True)

    def save_config(self, *args):
        root = self.root
        cfg = config_store.load_config()
        cfg.setdefault("credentials", {})["username"] = root.ids.username.text
        cfg["credentials"]["password"] = root.ids.password.text
        cfg.setdefault("check", {})["interval_seconds"] = int(root.ids.interval.text or "120")
        cfg.setdefault("portal", {})["base_url"] = root.ids.portal_url.text or "http://172.17.0.2"
        cfg.setdefault("behavior", {})["relogin_when_online"] = root.ids.relogin.active
        config_store.save_config(cfg)
        state.log("配置已保存")

    # ---------- 手动操作 ----------

    def _current_cfg(self):
        # 先把界面上的改动落盘，保证手动操作用最新配置
        self.save_config()
        return config_store.load_config()

    def do_check(self, *args):
        cfg = self._current_cfg()
        st = drcom.check_status(cfg)
        state.save_state(st, last_action=__import__("time").time())
        state.log(f"手动检测: {st}")

    def do_login(self, *args):
        cfg = self._current_cfg()
        ok, info = drcom.login(cfg)
        state.log(f"手动登录: {'成功' if ok else '失败'} | {info}")

    def do_logout(self, *args):
        cfg = self._current_cfg()
        ok, info = drcom.logout(cfg)
        state.log(f"手动注销: {'成功' if ok else '失败'} | {info}")

    # ---------- 服务控制 ----------

    def toggle_service(self, *args):
        btn = self.root.ids.svc_btn
        if self._is_service_running():
            self._stop_service()
            btn.text = '启动服务'
        else:
            self._start_service()
            btn.text = '停止服务'

    def _is_service_running(self):
        if self._android_svc is not None:
            return True
        return self._svc_thread is not None and self._svc_thread.is_alive()

    def _start_service(self):
        if self._is_android():
            try:
                from android import AndroidService

                self._android_svc = AndroidService("校园网自动登录", "正在后台维护登录状态")
                self._android_svc.start("LoginService")
                state.log("已启动 Android 后台服务")
            except Exception as e:
                state.log(f"启动 Android 服务失败: {e}")
        else:
            service._running = True
            self._svc_thread = threading.Thread(target=service.run, daemon=True)
            self._svc_thread.start()
            state.log("已启动后台线程（PC 模式）")

    def _stop_service(self):
        if self._is_android():
            try:
                if self._android_svc:
                    self._android_svc.stop()
                self._android_svc = None
                state.log("已停止 Android 后台服务")
            except Exception as e:
                state.log(f"停止 Android 服务失败: {e}")
        else:
            service.stop()
            self._svc_thread = None
            state.log("已停止后台线程")

    def _is_android(self):
        return "android" in sys.platform

    # ---------- 刷新 ----------

    def clear_logs(self, *args):
        state.clear_logs()

    def _refresh(self, *args):
        st = state.load_state()
        status_map = {
            "off_campus": "不在校园网（跳过）",
            "online": "已联网",
            "offline": "未登录",
        }
        status = st.get("status")
        text = status_map.get(status, "未知")
        self.root.ids.status_label.text = f"状态：{text}"

        import time as _t

        updated = st.get("updated")
        if updated:
            t = _t.strftime("%H:%M:%S", _t.localtime(updated))
            self.root.ids.detail_label.text = f"最近动作：{t}    服务：{'运行中' if self._is_service_running() else '已停止'}"
        else:
            self.root.ids.detail_label.text = "服务：未启动"

        logs = state.read_logs(150)
        self.root.ids.log_label.text = "\n".join(logs) if logs else "（暂无日志）"


if __name__ == "__main__":
    CampusApp().run()
