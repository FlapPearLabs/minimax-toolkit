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
MINIMAX_DIR = os.environ.get("MINIMAX_HOME") or os.path.join(HOME, ".minimax")
AUTH_PROFILES_DIR = os.path.join(MINIMAX_DIR, "auth_profiles")
LOGS_DIR = os.path.join(MINIMAX_DIR, "logs")
STATE_PATH = os.path.join(MINIMAX_DIR, "state.json")
LAUNCHD_LABEL = "com.minimax.dailycheckin"
SYSTEMD_UNIT = "minimax-checkin"
WINDOWS_TASKS = ("MiniMaxDailyCheckin", "MiniMaxBootCheckin")

IS_TTY = sys.stdout.isatty() and sys.stderr.isatty()
COLOR_GREEN = "\033[92m" if IS_TTY else ""
COLOR_YELLOW = "\033[93m" if IS_TTY else ""
COLOR_CYAN = "\033[96m" if IS_TTY else ""
COLOR_RED = "\033[91m" if IS_TTY else ""
COLOR_DIM = "\033[2m" if IS_TTY else ""
COLOR_BOLD = "\033[1m" if IS_TTY else ""
COLOR_RESET = "\033[0m" if IS_TTY else ""

ALIASES = [
    "minimax", "mmx", "minimax-help", "mmx-help",
    "minimax-login", "mmx-login",
    "minimax-switch", "mmx-switch",
    "minimax-list", "mmx-list",
    "minimax-status", "mmx-status",
    "minimax-checkin", "mmx-checkin",
    "minimax-audit", "mmx-audit",
    "minimax-doctor", "mmx-doctor",
    "minimax-cron", "mmx-cron",
]


def remove_scheduler():
    if sys.platform == "darwin":
        plist = os.path.join(HOME, "Library", "LaunchAgents", f"{LAUNCHD_LABEL}.plist")
        if os.path.exists(plist):
            subprocess.run(["launchctl", "unload", plist], capture_output=True)
            try:
                os.remove(plist)
            except Exception:
                pass
            print(f"{COLOR_GREEN}✔ 已注销并删除 macOS LaunchAgent 定时任务{COLOR_RESET}")
        return

    if sys.platform.startswith("linux"):
        unit_dir = os.path.join(HOME, ".config", "systemd", "user")
        removed = False
        if shutil.which("systemctl"):
            res = subprocess.run(["systemctl", "--user", "disable", "--now", f"{SYSTEMD_UNIT}.timer"],
                                 capture_output=True, text=True, errors="replace")
            if res.returncode != 0 and os.path.exists(os.path.join(unit_dir, f"{SYSTEMD_UNIT}.timer")):
                detail = (res.stderr or res.stdout or "").strip()
                print(f"{COLOR_YELLOW}△ systemctl --user disable 未成功{(': ' + detail) if detail else ''}{COLOR_RESET}")
        for name in (f"{SYSTEMD_UNIT}.service", f"{SYSTEMD_UNIT}.timer"):
            path = os.path.join(unit_dir, name)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    removed = True
                except Exception:
                    pass
        if shutil.which("systemctl"):
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        if removed:
            print(f"{COLOR_GREEN}✔ 已停用并删除 systemd user timer{COLOR_RESET}")
        return

    if sys.platform == "win32":
        removed = False
        for name in WINDOWS_TASKS:
            res = subprocess.run(["schtasks", "/delete", "/tn", name, "/f"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            if res.returncode == 0:
                removed = True
        if removed:
            print(f"{COLOR_GREEN}✔ 已删除 Windows 计划任务{COLOR_RESET}")


def is_our_script(path):
    """安全边界：只删除确实属于本工具的文件，避免误删同名第三方命令"""
    try:
        if os.path.islink(path):
            return True
        with open(path, "rb") as f:
            head = f.read(4096).decode("utf-8", errors="ignore").lower()
        return "minimax" in head
    except Exception:
        return False


def remove_cli():
    if sys.platform == "win32":
        bin_dir = os.path.join(MINIMAX_DIR, "bin")
        if os.path.exists(bin_dir):
            for a in ALIASES:
                for target in (os.path.join(bin_dir, f"{a}.cmd"), os.path.join(bin_dir, a)):
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

        # 清理 Windows 用户 PATH 环境变量
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                try:
                    cur_path, _ = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    cur_path = ""
                if cur_path:
                    parts = [p.strip() for p in cur_path.split(os.pathsep) if p.strip()]
                    norm_bin = os.path.normcase(bin_dir.rstrip('\\'))
                    new_parts = [p for p in parts if os.path.normcase(p.rstrip('\\')) != norm_bin]
                    if len(new_parts) != len(parts):
                        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, os.pathsep.join(new_parts))
                        print(f"{COLOR_GREEN}✔ 已从 Windows 用户 PATH 环境变量中移除 {bin_dir}{COLOR_RESET}")
        except Exception:
            pass
        return

    bin_dir = os.path.join(HOME, ".local", "bin")
    removed_count = 0
    skipped = []
    for a in ALIASES:
        target = os.path.join(bin_dir, a)
        if not (os.path.islink(target) or os.path.exists(target)):
            continue
        if not is_our_script(target):
            skipped.append(a)
            continue
        try:
            os.remove(target)
            removed_count += 1
        except Exception:
            pass
    print(f"{COLOR_GREEN}✔ 已清理 ~/.local/bin 中的 {removed_count} 个快捷软链/程序{COLOR_RESET}")
    if skipped:
        print(f"{COLOR_YELLOW}△ 已跳过非本工具的同名文件: {', '.join(skipped)}{COLOR_RESET}")


def purge_data():
    norm_home = os.path.abspath(HOME)
    norm_mmx = os.path.abspath(MINIMAX_DIR)
    # 严格安全边界检查：仅允许删除 HOME 之下的目录
    if not (norm_mmx.startswith(norm_home + os.sep) and norm_mmx != norm_home):
        print(f"{COLOR_RED}✘ 安全校验拒绝清理越界路径: {norm_mmx}{COLOR_RESET}")
        return False
    # 目录指纹校验：MINIMAX_HOME 可能被指向普通工程目录，绝不能盲删其中的 bin/ 与 logs/
    markers = [os.path.join(MINIMAX_DIR, "auth_profiles"),
               os.path.join(MINIMAX_DIR, "auth"),
               STATE_PATH]
    if not any(os.path.exists(m) for m in markers):
        print(f"{COLOR_YELLOW}△ {MINIMAX_DIR} 未发现 MiniMax Toolkit 数据指纹，跳过 --purge 清理。{COLOR_RESET}")
        return False

    for sub in (AUTH_PROFILES_DIR, LOGS_DIR, os.path.join(MINIMAX_DIR, "auth"),
                os.path.join(MINIMAX_DIR, "bin")):
        if os.path.exists(sub):
            shutil.rmtree(sub, ignore_errors=True)
    if os.path.exists(STATE_PATH):
        try:
            os.remove(STATE_PATH)
        except Exception:
            pass
    try:
        if os.path.exists(norm_mmx) and not os.listdir(norm_mmx):
            os.rmdir(norm_mmx)
    except Exception:
        pass
    print(f"{COLOR_YELLOW}✔ 已按 --purge 要求彻底清理多账号凭据、日志及运行时状态{COLOR_RESET}")
    return True


def uninstall():
    print(f"\n{COLOR_BOLD}{COLOR_YELLOW}正在卸载 MiniMax Toolkit ({sys.platform})...{COLOR_RESET}")
    purge = "--purge" in sys.argv

    remove_scheduler()
    remove_cli()

    if purge:
        purge_data()
    else:
        print(f"{COLOR_CYAN}ℹ 您的账号数据与 Profile ({AUTH_PROFILES_DIR}) 已安全保留。{COLOR_RESET}")
        print(f"{COLOR_DIM}若需彻底清除包括所有登录凭据在内的数据，请执行: python3 uninstall.py --purge{COLOR_RESET}")

    print(f"\n{COLOR_BOLD}{COLOR_GREEN}✔ MiniMax Toolkit 卸载完成。{COLOR_RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(uninstall())
