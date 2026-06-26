"""完整闭环测试：注销 → 冷却 → 登录 → 查状态。

中途会断网几秒，但脚本本地持续运行，登录请求会自动发出恢复网络。
结果写到 logs/test.log，断网恢复后可查看。
"""
import time
import requests

import config_store
import drcom
import state


def main():
    cfg = config_store.load_config()
    state.log("========== 闭环测试开始 ==========")

    # 1. 初始状态
    st0 = drcom.check_status(cfg)
    state.log(f"[1] 初始状态: {st0}")

    # 2. 注销
    state.log("[2] 执行注销...")
    ok, info = drcom.logout(cfg)
    state.log(f"    注销结果: ok={ok} | {info}")

    # 3. 冷却（严格按 behavior）
    cooldown = cfg.get("behavior", {}).get("cooldown_after_logout_seconds", 3)
    state.log(f"[3] 冷却 {cooldown} 秒...")
    time.sleep(cooldown)

    # 4. 查注销后状态
    try:
        st1 = drcom.check_status(cfg)
        state.log(f"[4] 注销后状态: {st1}")
    except Exception as e:
        state.log(f"[4] 注销后状态查询异常（可能已断网）: {e}")

    # 5. 登录
    state.log("[5] 执行登录...")
    try:
        ok, info = drcom.login(cfg)
        state.log(f"    登录结果: ok={ok} | {info}")
    except Exception as e:
        state.log(f"    登录异常: {e}")

    # 6. 查最终状态
    time.sleep(2)
    try:
        st2 = drcom.check_status(cfg)
        state.log(f"[6] 最终状态: {st2}")
    except Exception as e:
        state.log(f"[6] 最终状态查询异常: {e}")

    state.log("========== 闭环测试结束 ==========")
    print("测试完成，查看 logs/app.log")


if __name__ == "__main__":
    main()
