# 校园网自动登录 App（Dr.COM ePortal / 广州热点）

把手机变成校园网自动登录器：手机插电、连校园 Wi-Fi，App 后台自动维护登录态。
检测逻辑严格按需求：**已登录就注销再登录，未登录就登录**；手机离开校园网时自动静默，回到校园网才干活。

> ✅ **登录协议已逆向验证通过**：完整「注销→登录」闭环在 PC 上实测成功（解绑MAC成功→Portal认证成功→网络恢复）。

---

## 工作原理

### 校园网判断 + 状态检测

1. **是否在校园网**：访问 `http://172.17.0.2/`（校园网私有 IP，校外不可达）。
   - 连不上 → 不在校园网，跳过。
   - 连得上 → 在校园网，进入第 2 步。
2. **是否已登录**：访问外网探测 URL（`http://connect.rom.miui.com/generate_204`）。
   - 被重定向到 `172.17.0.2` → 未登录 → **执行登录**。
   - 正常返回 204 → 已登录 → **注销→冷却→重新登录**（严格按需求；App 内可关开关）。
3. 每隔 `interval_seconds`（默认 120 秒）循环一次。

### 登录协议（已逆向，硬编码在 `drcom.py`）

逆向自 portal 页面 JS（`a40.js` / `a41.js`）：

- **加密方式**：登录/注销的整个 data 对象 `JSON.stringify` 后，用 **AES-128-ECB + PKCS7** 加密，密钥固定 `5c1d5ad4dea0e8dd`，base64 后作为 `params` 查询参数发出（JSONP GET）。
- **登录**：`GET http://172.17.0.2:801/eportal/portal/login?callback=dr1003&params=<加密>&jsVersion=4.2.1`
  - data 含 `user_account=",0,学号"`、`user_password="密码"`、`wlan_user_ip`、`wlan_ac_ip`、`wlan_ac_name` 等
- **注销**：`GET http://172.17.0.2:801/eportal/portal/mac/unbind?...&params=<加密>`
- **动态参数**：未登录时访问 portal 首页会 302 跳到 `a79.htm?wlanuserip=...&wlanacname=...&wlanacip=...`，从重定向 URL 自动抓取。
- **状态查询**：`GET http://172.17.0.2/drcom/chkstatus`（明文 JSONP，看 `result` 字段）

无需手动抓包填配置——协议已全部写进代码，你只需填账号密码。

---

## PC 上验证（已通过）

```bash
pip install -r requirements.txt          # 含 pycryptodome（AES 加密）
cp config.json.example config.json       # 填你的账号密码
python test_cycle.py                     # 跑完整「注销→登录」闭环，看 logs/app.log
```

`test_cycle.py` 会：注销→冷却3秒→登录→查状态，全程写本地日志。中途断网几秒会自动恢复。
预期日志：
```
[1] 初始状态: online
[2] 注销...  ok=True | 解绑终端MAC成功！
[4] 注销后状态: offline
[5] 登录...  ok=True | Portal协议认证成功！
[6] 最终状态: online
```

也可单独测：
```bash
python -c "import drcom,config_store as c; print(drcom.check_status(c.load_config()))"
python -c "import drcom,config_store as c; print(drcom.login(c.load_config()))"
python -c "import drcom,config_store as c; print(drcom.logout(c.load_config()))"
```

跑 UI（PC 也能开）：
```bash
pip install kivy
python main.py
```

---

## 打包成 APK

> **Buildozer 只能在 Linux 上跑。** Windows 用户用下面任一方式。

### 方式 A：GitHub Actions 云端打包（推荐，免装环境）

1. 把本项目推到 GitHub。
2. 推送后 Actions 自动构建（见 `.github/workflows/build.yml`）。
3. 在仓库 **Actions → 最新 run → Artifacts** 下载 `campuslogin-apk`，解压得到 APK。

### 方式 B：WSL2 本地打包

```bash
sudo apt update && sudo apt install -y python3-pip build-essential git zip unzip openjdk-17-jdk autoconf libtool pkg-config
pip install buildozer cython
buildozer -v android debug        # 产物在 bin/*.apk
```

### 安装到手机

- `adb install bin/campuslogin-0.1-debug.apk`，或把 APK 传到手机手动安装（允许"未知来源"）。
- 打开 App → 填账号密码 → 保存 → 点"启动服务"。

---

## 手机保活设置（重要）

国产 ROM 容易杀后台，务必设置：
- **电池优化**：设置 → 应用 → 校园网登录 → 电池 → 不限制/无限制。
- **自启动**：允许自启动，并锁定后台（最近任务里下拉锁定）。
- **省电模式**：关闭对 App 的限制。
- 手机插电、保持校园 Wi-Fi 连接、给手机分配静态 IP 更稳。

---

## 目录说明

| 文件 | 作用 |
|------|------|
| `drcom.py` | 核心客户端：AES 加密 / 校园网判断 / 状态检测 / 登录 / 注销 |
| `service.py` | 后台循环（前台 Service，防杀） |
| `main.py` | Kivy App 界面 |
| `config_store.py` | 配置读写（App 私有目录） |
| `state.py` | 状态与日志持久化 |
| `test_cycle.py` | PC 闭环测试脚本 |
| `config.json.example` | 配置模板（填账号密码即可） |
| `buildozer.spec` | APK 构建配置 |
| `.github/workflows/build.yml` | 云端打包 |

---

## 注意

- "已登录→注销→重登"会瞬时断网，是需求要求的行为；App 内有开关可临时关闭。
- 若学校限制单账号在线设备数，注销重登会把其他设备顶下线——符合预期。
- 登录用的 `wlan_user_mac` 固定填 `000000000000`（与原 portal JS 一致，由网关自动识别真实 MAC）。
