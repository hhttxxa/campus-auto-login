"""Dr.COM ePortal 4.2.1 校园网认证客户端（广州热点）。

逆向自 portal 页面 JS（a40.js / a41.js）：
- 登录/注销请求把整个 data 对象 JSON.stringify 后用 AES-128-ECB + PKCS7 加密，
  密钥固定 "5c1d5ad4dea0e8dd"，base64 后作为 params 查询参数发出（JSONP GET）。
- 状态检测用 /drcom/chkstatus（明文，看 result 字段）。
- 动态参数 wlan_user_ip / wlan_ac_ip / wlan_ac_name：未登录时访问 portal 首页会
  302 跳到 a79.htm?wlanuserip=...&wlanacname=...&wlanacip=...，从重定向 URL 取。

校园网判据：172.17.0.2 是校园网内网私有 IP，只有连上校园网才可达——用它的
可达性判断"是否在校园网"，手机漫游时自动适配。

本模块不依赖 Kivy / Android，可在 PC 上独立测试。
"""
import base64
import json
import re
import time

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from urllib.parse import urlparse, parse_qs, quote

# 逆向自 a40.js: _util.aes_en
_AES_KEY = b"5c1d5ad4dea0e8dd"
# 逆向自 a41.js: page.portal_api / page.host
_PORTAL_API = "http://172.17.0.2:801/eportal/portal/"
_LOGIN_URL = _PORTAL_API + "login"
_LOGOUT_URL = _PORTAL_API + "mac/unbind"
_CHKSTATUS_URL = "http://172.17.0.2/drcom/chkstatus"
_PORTAL_HOME = "http://172.17.0.2/"


def aes_encrypt(plain):
    """AES-128-ECB + PKCS7，返回 base64 字符串。对应 JS 的 util.aes_en。"""
    cipher = AES.new(_AES_KEY, AES.MODE_ECB)
    data = pad(plain.encode("utf-8"), AES.block_size)
    return base64.b64encode(cipher.encrypt(data)).decode("ascii")


def aes_decrypt(b64):
    cipher = AES.new(_AES_KEY, AES.MODE_ECB)
    return unpad(cipher.decrypt(base64.b64decode(b64)), AES.block_size).decode("utf-8")


def _jsonp_callback(text):
    """从 JSONP 响应 dr100X({...}); 中提取 dict。"""
    m = re.search(r"\((\{.*\})\)\s*;?\s*$", text.strip(), re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def on_campus(cfg, timeout=None):
    """172.17.0.2 只有校园网内可达。可达=True（在校园网），不可达=False。"""
    timeout = timeout or cfg.get("check", {}).get("timeout_seconds", 5)
    try:
        requests.get(_PORTAL_HOME, timeout=timeout, allow_redirects=False)
        return True
    except requests.RequestException:
        return False


def _fetch_term_info(session, timeout):
    """访问 portal 首页，跟随 302 到 a79.htm，从 URL 取 wlan_user_ip / wlan_ac_ip / wlan_ac_name。

    返回 dict；未登录时正常，已登录时首页不跳转、取不到则返回空值占位。
    """
    info = {"wlan_user_ip": "", "wlan_ac_ip": "", "wlan_ac_name": ""}
    try:
        r = session.get(_PORTAL_HOME, timeout=timeout, allow_redirects=True)
    except requests.RequestException:
        return info
    # 在最终 URL 的查询串里找参数（a79.htm?wlanuserip=...&wlanacname=...&wlanacip=...）
    q = parse_qs(urlparse(r.url).query)
    if "wlanuserip" in q:
        info["wlan_user_ip"] = q["wlanuserip"][0]
    if "wlanacip" in q:
        info["wlan_ac_ip"] = q["wlanacip"][0]
    if "wlanacname" in q:
        info["wlan_ac_name"] = q["wlanacname"][0]
    # 兜底：从页面文本里抓 v46ip / ss5
    if not info["wlan_user_ip"]:
        body = r.text or ""
        m = re.search(r"v46ip\s*=\s*['\"](\d+\.\d+\.\d+\.\d+)", body)
        if m:
            info["wlan_user_ip"] = m.group(1)
    return info


def check_status(cfg, session=None):
    """返回状态字符串：
    - 'off_campus' : 不在校园网（portal 不可达），跳过
    - 'offline'    : 在校园网但未登录
    - 'online'     : 已联网
    """
    s = session or requests.Session()
    chk = cfg.get("check", {})
    timeout = chk.get("timeout_seconds", 5)

    if not on_campus(cfg, timeout):
        return "off_campus"

    # 用 chkstatus 判断：result 字段。未登录时 result 通常为 0 且无在线信息；
    # 也可结合外网探测。这里用外网探测为主（更直观），chkstatus 作辅助。
    probe = chk.get("probe_url", "http://connect.rom.miui.com/generate_204")
    try:
        r = s.get(probe, timeout=timeout, allow_redirects=True)
    except requests.RequestException:
        return "offline"
    if "172.17.0.2" in r.url:
        return "offline"
    if r.status_code in (301, 302, 307):
        return "offline"
    if 200 <= r.status_code < 400:
        return "online"
    return "offline"


def _build_login_data(cfg, term_info):
    """构造登录 data（与 a40.js portal_login 一致）。"""
    creds = cfg.get("credentials", {})
    username = creds.get("username", "")
    password = creds.get("password", "")
    # user_account 格式 ",0,学号"（运营商0=默认）
    user_account = ",0," + username
    return {
        "login_method": 1,
        "user_account": user_account,
        "user_password": password,
        "wlan_user_ip": term_info.get("wlan_user_ip", ""),
        "wlan_user_ipv6": "",
        "wlan_user_mac": "000000000000",
        "wlan_ac_ip": term_info.get("wlan_ac_ip", ""),
        "wlan_ac_name": term_info.get("wlan_ac_name", ""),
        "jsVersion": "4.2.1",
        "login_t": "0",
        "js_status": "0",
        "is_page": "1",
        "is_page_new": int(time.time() * 1000) % 10000 + 500,
        "terminal_type": 1,
        "lang": "zh-cn",
        "rcn": "",
    }


def _build_logout_data(cfg, term_info):
    """构造注销 data（与 a40.js mac/unbind 一致）。"""
    creds = cfg.get("credentials", {})
    username = creds.get("username", "")
    # wlan_user_ip 在 JS 里是 ipToParseInt 转成的整数
    ip_int = _ip_to_int(term_info.get("wlan_user_ip", "0.0.0.0"))
    return {
        "user_account": username,
        "wlan_user_mac": "000000000000",
        "wlan_user_ip": ip_int,
        "jsVersion": "4.2.1",
    }


def _ip_to_int(ip):
    try:
        a, b, c, d = [int(x) for x in ip.split(".")]
        return (a << 24) | (b << 16) | (c << 8) | d
    except (ValueError, AttributeError):
        return 0


def _post_jsonp(session, url, data, timeout):
    """把 data 加密成 params，发 JSONP GET，返回解析后的 dict。"""
    params_b64 = aes_encrypt(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    cb = "dr1003"
    qs = {
        "callback": cb,
        "params": params_b64,
        "jsVersion": "4.2.1",
        "_": str(int(time.time() * 1000)),
        "lang": "zh",
    }
    headers = {
        "Referer": _PORTAL_HOME,
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/119.0 Safari/537.36",
        "Accept": "*/*",
    }
    try:
        r = session.get(url, params=qs, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return None, f"请求失败: {e}"
    body = r.text or ""
    parsed = _jsonp_callback(body)
    return parsed, body


def login(cfg, session=None):
    """登录。返回 (ok: bool, info: str)。"""
    s = session or requests.Session()
    timeout = cfg.get("check", {}).get("timeout_seconds", 5)
    term = _fetch_term_info(s, timeout)
    if not term.get("wlan_user_ip"):
        return False, "未能获取 wlan_user_ip（可能已登录或不在校园网）"
    data = _build_login_data(cfg, term)
    parsed, raw = _post_jsonp(s, _LOGIN_URL, data, timeout)
    if parsed is None:
        return False, f"响应解析失败: {raw[:200]}"
    ok = str(parsed.get("result")) in ("1", "ok")
    return ok, f"result={parsed.get('result')} msg={parsed.get('msg','')}"


def logout(cfg, session=None):
    """注销/解绑 MAC。返回 (ok: bool, info: str)。"""
    s = session or requests.Session()
    timeout = cfg.get("check", {}).get("timeout_seconds", 5)
    term = _fetch_term_info(s, timeout)
    data = _build_logout_data(cfg, term)
    parsed, raw = _post_jsonp(s, _LOGOUT_URL, data, timeout)
    if parsed is None:
        return False, f"响应解析失败: {raw[:200]}"
    ok = str(parsed.get("result")) in ("1", "ok")
    return ok, f"result={parsed.get('result')} msg={parsed.get('msg','')}"
