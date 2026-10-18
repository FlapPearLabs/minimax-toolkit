#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax Toolkit Universal Cross-Platform Installer
Works out-of-the-box on macOS, Linux, and Windows with zero dependencies.
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
MINIMAX_DIR = os.path.join(HOME, ".minimax")
AUTH_PROFILES_DIR = os.path.join(MINIMAX_DIR, "auth_profiles")
LOGS_DIR = os.path.join(MINIMAX_DIR, "logs")

IS_TTY = sys.stdout.isatty() and sys.stderr.isatty()
COLOR_GREEN = "\033[92m" if IS_TTY else ""
COLOR_YELLOW = "\033[93m" if IS_TTY else ""
COLOR_CYAN = "\033[96m" if IS_TTY else ""
COLOR_RED = "\033[91m" if IS_TTY else ""
COLOR_DIM = "\033[2m" if IS_TTY else ""
COLOR_BOLD = "\033[1m" if IS_TTY else ""
COLOR_RESET = "\033[0m" if IS_TTY else ""

def print_banner():
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}========================================================{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}    MiniMax Toolkit 全平台通用安装程序 ({sys.platform}){COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}    Developed by FlapPearLabs (Zero-Dependency){COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}========================================================{COLOR_RESET}\n")

def setup_dirs():
    os.makedirs(AUTH_PROFILES_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    print(f"{COLOR_GREEN}✔ 基础配置目录已就绪: {MINIMAX_DIR}{COLOR_RESET}")

def is_same_path(p1, p2):
    """【铁律防御】跨平台物理判断源与目标是否指向同一文件，杜绝自噬"""
    try:
        return os.path.samefile(p1, p2)
    except Exception:
        return os.path.abspath(p1) == os.path.abspath(p2)

def install_cli():
    src_bin = os.path.join(SCRIPT_DIR, "bin", "minimax")
    if not os.path.exists(src_bin):
        print(f"{COLOR_RED}错误: 未在 {src_bin} 找到主程序。{COLOR_RESET}")
        sys.exit(1)

    if sys.platform == "win32":
        bin_dir = os.path.join(MINIMAX_DIR, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        dest_bin = os.path.join(bin_dir, "minimax")

        # 原地自噬防御
        if not is_same_path(src_bin, dest_bin):
            shutil.copy2(src_bin, dest_bin)

        # 写入 Windows CMD 垫片
        cmd_wrapper = (
            "@echo off\r\n"
            "setlocal\r\n"
            "where python >nul 2>nul\r\n"
            "if %ERRORLEVEL% equ 0 (\r\n"
            "    python \"%~dp0minimax\" %*\r\n"
            ") else (\r\n"
            "    py \"%~dp0minimax\" %*\r\n"
            ")\r\n"
        )
        for name in ["minimax.cmd", "mmx.cmd"]:
            with open(os.path.join(bin_dir, name), "w", encoding="ascii") as f:
                f.write(cmd_wrapper)

        for subcmd in ["login", "switch", "list", "status", "checkin", "audit", "doctor", "cron", "help"]:
            wrapper = f"@echo off\r\ncall \"%~dp0minimax.cmd\" {subcmd} %*\r\n"
            for prefix in [f"mmx-{subcmd}.cmd", f"minimax-{subcmd}.cmd"]:
                with open(os.path.join(bin_dir, prefix), "w", encoding="ascii") as f:
                    f.write(wrapper)

        # 尝试配置 Windows PATH
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                try:
                    cur_path, _ = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    cur_path = ""
                if bin_dir.lower() not in cur_path.lower():
                    new_path = f"{cur_path};{bin_dir}" if cur_path else bin_dir
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                    print(f"{COLOR_GREEN}✔ 已将 {bin_dir} 添加至 Windows 用户 PATH 环境变量{COLOR_RESET}")
        except Exception:
            pass

        print(f"{COLOR_GREEN}✔ CLI 主程序及 Windows 命令垫片已安装至: {bin_dir}{COLOR_RESET}")
        return dest_bin, bin_dir
    else:
        bin_dir = os.path.join(HOME, ".local", "bin")
        os.makedirs(bin_dir, exist_ok=True)
        dest_bin = os.path.join(bin_dir, "minimax")

        # 原地自噬防御
        if not is_same_path(src_bin, dest_bin):
            shutil.copy2(src_bin, dest_bin)
        os.chmod(dest_bin, 0o755)

        # 创建快捷别名软链接
        for alias in [
            "mmx", "minimax-help", "mmx-help",
            "minimax-login", "mmx-login",
            "minimax-switch", "mmx-switch",
            "minimax-list", "mmx-list",
            "minimax-status", "mmx-status",
            "minimax-checkin", "mmx-checkin",
            "minimax-audit", "mmx-audit",
            "minimax-doctor", "mmx-doctor",
            "minimax-cron", "mmx-cron"
        ]:
            link_path = os.path.join(bin_dir, alias)
            if not is_same_path(link_path, dest_bin):
                if os.path.islink(link_path) or os.path.exists(link_path):
                    try:
                        os.remove(link_path)
                    except Exception:
                        pass
                try:
                    os.symlink("minimax", link_path)
                except Exception:
                    pass

        print(f"{COLOR_GREEN}✔ CLI 主程序及快捷软链已安装至: {bin_dir}{COLOR_RESET}")
        return dest_bin, bin_dir

def install_services_if_requested(dest_bin):
    """【铁律防御】后台服务必须显式 Opt-in，严禁静默注册常驻任务"""
    with_services = "--with-services" in sys.argv
    if not with_services:
        print(f"{COLOR_YELLOW}提示: 未指定 --with-services，已跳过定时服务自动注册。{COLOR_RESET}")
        print(f"{COLOR_DIM}若需配置每日 09:05 自动签到，随时运行: minimax cron install 即可。{COLOR_RESET}")
        return

    if sys.platform == "darwin":
        plist_src = os.path.join(SCRIPT_DIR, "launchd", "com.minimax.dailycheckin.plist")
        if os.path.exists(plist_src):
            plist_dest = os.path.join(HOME, "Library", "LaunchAgents", "com.minimax.dailycheckin.plist")
            os.makedirs(os.path.dirname(plist_dest), exist_ok=True)
            with open(plist_src, "r", encoding="utf-8") as f:
                content = f.read()
            content = content.replace("__CLI_PATH__", dest_bin).replace("__LOG_PATH__", os.path.join(LOGS_DIR, "checkin.log"))
            with open(plist_dest, "w", encoding="utf-8") as f:
                f.write(content)
            subprocess.run(["launchctl", "unload", plist_dest], capture_output=True)
            subprocess.run(["launchctl", "load", plist_dest], capture_output=True)
            print(f"{COLOR_GREEN}✔ macOS LaunchAgent 定时打卡服务已成功加载！{COLOR_RESET}")
    else:
        print(f"{COLOR_YELLOW}Linux / Windows 定时服务请参考 docs/ 使用对应配置。{COLOR_RESET}")

def main():
    print_banner()
    setup_dirs()
    dest_bin, bin_dir = install_cli()
    install_services_if_requested(dest_bin)

    print(f"\n{COLOR_BOLD}{COLOR_GREEN}========================================================{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_GREEN}   🎉 MiniMax Toolkit 安装部署全部完成！{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_GREEN}========================================================{COLOR_RESET}")
    print(f"\n快捷指令入门:")
    print(f"  • {COLOR_BOLD}minimax login <alias>{COLOR_RESET}  - 浏览器免扫码绑定新账号 (RFC 8628)")
    print(f"  • {COLOR_BOLD}minimax switch{COLOR_RESET}         - 交互式切换多账号")
    print(f"  • {COLOR_BOLD}minimax list{COLOR_RESET}           - 查看所有已纳管账号与签到状态")
    print(f"  • {COLOR_BOLD}minimax checkin --all{COLOR_RESET}  - 全量账号批量自动打卡")
    print(f"  • {COLOR_BOLD}minimax doctor{COLOR_RESET}         - 运行时环境诊断\n")

if __name__ == "__main__":
    main()
