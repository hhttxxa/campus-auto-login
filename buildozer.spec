[app]

# App 元信息
title = Campus Auto Login
package.name = campuslogin
package.domain = org.campus

# 源码目录与包含的扩展名
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

# 版本
version = 0.1

# Python 依赖（buildozer 会用 pip 安装到 APK 内）
requirements = python3,kivy,requests,pycryptodome,android,jnius

# 后台服务：LoginService 对应 service.py
services = LoginService:service.py

# Android SDK
android.api = 34
android.minapi = 24
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a

# 权限
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC,POST_NOTIFICATIONS,RECEIVE_BOOT_COMPLETED

# 让 service 作为前台服务运行（带常驻通知，防止被杀）
android.foreground_services = True

# 不全屏、保留状态栏
fullscreen = 0

# 日志
log_level = 2

# 构建后保留构建缓存以加速二次打包
build_dir = ./.buildozer
