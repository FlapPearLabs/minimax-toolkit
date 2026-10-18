#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax Toolkit Universal Cross-Platform Uninstaller
Works out-of-the-box on macOS, Linux, and Windows.
https://github.com/FlapPearLabs/minimax-toolkit

Developed & Maintained by FlapPearLabs
"""

import os
import sys
import shutil
import subprocess

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
MINIMAX_DIR = os.path.join(HOME, ".minimax")
AUTH_PROFILES_DIR = os.path.join(MINIMAX_DIR, "auth_profiles")

IS_TTY = sys.stdout.isatty() and sys.stderr.isatty()
COLOR_GREEN = "\033[92m" if IS_TTY else ""
COLOR_YELLOW = "\033[93m" if IS_TTY else ""
COLOR_CYAN = "\033[96m" if IS_TTY else ""
COLOR_RED = "\033[91m" if IS_TTY else ""
COLOR_DIM = "\033[2m" if IS_TTY else ""
COLOR_BOLD = "\033[1m" if IS_TTY else ""
COLOR_RESET = "\033[0m" if IS_TTY else ""

def uninstall():
    print(f"\n{COLOR_BOLD}{COLOR_YELLOW}正在卸载 MiniMax Toolkit ({sys.platform})...{COLOR_RESET}")
    purge = "--purge" in sys.argv

    # 1. 卸载定时任务
    if sys.platform == "darwin":
        plist_path = os.path.join(HOME, "Library", "LaunchAgents", "com.minimax.dailycheckin.plist")
        if os.path.exists(plist_path):
            subprocess.run(["launchctl", "unload", plist_path], capture_output=True)
            try:
                os.remove(plist_path)
            except Exception:
                pass
            print(f"{COLOR_GREEN}✔ 已注销并删除 macOS LaunchAgent 定时任务{COLOR_RESET}")

    # 2. 清理 CLI 入口与快捷别名
    aliases = [
        "minimax", "mmx", "minimax-help", "mmx-help",
        "minimax-login", "mmx-login",
        "minimax-switch", "mmx-switch",
        "minimax-list", "mmx-list",
        "minimax-status", "mmx-status",
        "minimax-checkin", "mmx-checkin",
        "minimax-audit", "mmx-audit",
        "minimax-doctor", "mmx-doctor",
        "minimax-cron", "mmx-cron"
    ]

    if sys.platform == "win32":
        bin_dir = os.path.join(MINIMAX_DIR, "bin")
        if os.path.exists(bin_dir):
            for a in aliases:
                p_cmd = os.path.join(bin_dir, f"{a}.cmd")
                p_raw = os.path.join(bin_dir, a)
                for target in [p_cmd, p_raw]:
                    if os.path.exists(target):
                        try:
                            os.remove(target)
                        except Exception:
                            pass
            try:
                if not os.listdir(bin_dir):
                    os.rmdir(bin_dir)
            except Exception:
                pass
            print(f"{COLOR_GREEN}✔ 已清理 Windows bin 目录中的命令垫片{COLOR_RESET}")
    else:
        bin_dir = os.path.join(HOME, ".local", "bin")
        removed_count = 0
        for a in aliases:
            target = os.path.join(bin_dir, a)
            if os.path.islink(target) or os.path.exists(target):
                try:
                    os.remove(target)
                    removed_count += 1
                except Exception:
                    pass
        print(f"{COLOR_GREEN}✔ 已清理 ~/.local/bin 中的 {removed_count} 个快捷软链/程序{COLOR_RESET}")

    # 3. 数据与 Profile 处理 (默认安全保护，仅当 --purge 时彻底删除)
    if purge:
        if os.path.exists(AUTH_PROFILES_DIR):
            shutil.rmtree(AUTH_PROFILES_DIR, ignore_errors=True)
            print(f"{COLOR_YELLOW}✔ 已按 --purge 要求彻底清理多账号 Profile 目录{COLOR_RESET}")
    else:
        print(f"{COLOR_CYAN}ℹ 您的账号数据与 Profile ({AUTH_PROFILES_DIR}) 已安全保留。{COLOR_RESET}")
        print(f"{COLOR_DIM}若需彻底清除包括所有登录凭据在内的数据，请执行: python3 uninstall.py --purge{COLOR_RESET}")

    print(f"\n{COLOR_BOLD}{COLOR_GREEN}✔ MiniMax Toolkit 卸载完成。{COLOR_RESET}\n")

if __name__ == "__main__":
    uninstall()
