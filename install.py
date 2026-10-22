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
MINIMAX_DIR = os.environ.get("MINIMAX_HOME") or os.path.join(HOME, ".minimax")
AUTH_PROFILES_DIR = os.path.join(MINIMAX_DIR, "auth_profiles")
LOGS_DIR = os.path.join(MINIMAX_DIR, "logs")
MIN_PYTHON = (3, 8)

IS_TTY = sys.stdout.isatty() and sys.stderr.isatty()
COLOR_GREEN = "\033[92m" if IS_TTY else ""
COLOR_YELLOW = "\033[93m" if IS_TTY else ""
COLOR_CYAN = "\033[96m" if IS_TTY else ""
COLOR_RED = "\033[91m" if IS_TTY else ""
COLOR_DIM = "\033[2m" if IS_TTY else ""
COLOR_BOLD = "\033[1m" if IS_TTY else ""
COLOR_RESET = "\033[0m" if IS_TTY else ""

ALIASES = [
    "mmx", "minimax-help", "mmx-help",
    "minimax-login", "mmx-login",
    "minimax-switch", "mmx-switch",
    "minimax-list", "mmx-list",
    "minimax-status", "mmx-status",
    "minimax-checkin", "mmx-checkin",
    "minimax-audit", "mmx-audit",
    "minimax-doctor", "mmx-doctor",
    "minimax-cron", "mmx-cron",
]
SUBCOMMANDS = ["login", "switch", "list", "status", "checkin", "audit", "doctor", "cron", "help"]


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


def _windows_cmd_wrapper():
    # 优先 py -3，其次 python3，最后 python（避开 Windows Store 假别名）
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        "where py >nul 2>nul\r\n"
        "if %ERRORLEVEL% equ 0 (\r\n"
        "    py -3 \"%~dp0minimax\" %*\r\n"
        "    exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "where python3 >nul 2>nul\r\n"
        "if %ERRORLEVEL% equ 0 (\r\n"
        "    python3 \"%~dp0minimax\" %*\r\n"
        "    exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "python \"%~dp0minimax\" %*\r\n"
        "exit /b %ERRORLEVEL%\r\n"
    )


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

        wrapper = _windows_cmd_wrapper()
        for name in ["minimax.cmd", "mmx.cmd"]:
            with open(os.path.join(bin_dir, name), "w", encoding="ascii", newline="") as f:
                f.write(wrapper)

        for subcmd in SUBCOMMANDS:
            body = f"@echo off\r\ncall \"%~dp0minimax.cmd\" {subcmd} %*\r\nexit /b %ERRORLEVEL%\r\n"
            for prefix in [f"mmx-{subcmd}.cmd", f"minimax-{subcmd}.cmd"]:
                with open(os.path.join(bin_dir, prefix), "w", encoding="ascii", newline="") as f:
                    f.write(body)

        # 尝试配置 Windows PATH (精确分项比对，杜绝子串误判)
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                try:
                    cur_path, _ = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    cur_path = ""
                parts = [p.strip() for p in cur_path.split(os.pathsep) if p.strip()]
                norm_bin = os.path.normcase(bin_dir.rstrip('\\'))
                if not any(os.path.normcase(p.rstrip('\\')) == norm_bin for p in parts):
                    new_path = f"{cur_path};{bin_dir}" if cur_path else bin_dir
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                    print(f"{COLOR_GREEN}✔ 已将 {bin_dir} 添加至 Windows 用户 PATH 环境变量{COLOR_RESET}")
        except Exception:
            pass

        print(f"{COLOR_GREEN}✔ CLI 主程序及 Windows 命令垫片已安装至: {bin_dir}{COLOR_RESET}")
        return dest_bin, bin_dir

    bin_dir = os.path.join(HOME, ".local", "bin")
    os.makedirs(bin_dir, exist_ok=True)
    dest_bin = os.path.join(bin_dir, "minimax")

    # 原地自噬防御
    if not is_same_path(src_bin, dest_bin):
        shutil.copy2(src_bin, dest_bin)
    os.chmod(dest_bin, 0o755)

    for alias in ALIASES:
        link_path = os.path.join(bin_dir, alias)
        if is_same_path(link_path, dest_bin):
            continue
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


def verify_cli(dest_bin):
    """安装后真实性验证：实际执行一次 --version，杜绝「装上但跑不起来」"""
    res = subprocess.run([sys.executable, dest_bin, "--version"],
                         capture_output=True, text=True, errors="replace")
    if res.returncode != 0:
        print(f"{COLOR_RED}✘ 安装后自检失败: {(res.stderr or res.stdout).strip()}{COLOR_RESET}")
        return False
    print(f"{COLOR_GREEN}✔ 安装后自检通过: {res.stdout.strip()}{COLOR_RESET}")
    return True


def resolve_checkin_mode(argv):
    for idx, arg in enumerate(argv):
        if arg.startswith("--checkin-mode="):
            return arg.split("=", 1)[1].strip().lower()
        if arg == "--checkin-mode" and idx + 1 < len(argv):
            return argv[idx + 1].strip().lower()
    if "--with-services" in argv:
        return "calendar"
    return "none"


def install_services(dest_bin, mode):
    """【铁律防御】后台服务必须显式 Opt-in，严禁静默注册常驻任务"""
    if mode == "none":
        print(f"{COLOR_YELLOW}提示: 未指定 --checkin-mode，已跳过定时服务自动注册。{COLOR_RESET}")
        print(f"{COLOR_DIM}若需配置自动签到，随时运行: minimax cron install [--mode calendar|boot] 即可。{COLOR_RESET}")
        return True
    if mode not in ("calendar", "boot"):
        print(f"{COLOR_RED}错误: --checkin-mode 仅支持 calendar / boot / none，收到: {mode}{COLOR_RESET}")
        return False

    # 单一真源：调度逻辑全部收敛在 CLI 的 cron 子命令里
    res = subprocess.run([sys.executable, dest_bin, "cron", "install", "--mode", mode],
                         capture_output=True, text=True, errors="replace")
    output = (res.stdout or "") + (res.stderr or "")
    print(output.rstrip())
    return res.returncode == 0


def check_path_hint(bin_dir):
    if sys.platform == "win32":
        return
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if os.path.abspath(bin_dir) in [os.path.abspath(p) for p in path_parts if p]:
        return
    print(f"{COLOR_YELLOW}△ {bin_dir} 不在当前 PATH 中，请将下面一行加入 shell 配置后重开终端:{COLOR_RESET}")
    print(f'  export PATH="{bin_dir}:$PATH"')


def main():
    print_banner()

    if sys.version_info[:2] < MIN_PYTHON:
        print(f"{COLOR_RED}错误: 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+，当前为 "
              f"{sys.version.split()[0]} ({sys.executable}){COLOR_RESET}")
        sys.exit(1)

    mode = resolve_checkin_mode(sys.argv[1:])

    setup_dirs()
    dest_bin, bin_dir = install_cli()

    if not verify_cli(dest_bin):
        sys.exit(1)

    if not install_services(dest_bin, mode):
        sys.exit(1)

    check_path_hint(bin_dir)

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
