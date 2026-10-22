import os
import sys
import shutil
import tempfile
import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from _cli_loader import load_cli

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_PATH = os.path.join(REPO_DIR, "bin", "minimax")
mmx = load_cli()


def ok_run(*args, **kwargs):
    return CompletedProcess(args=args[0] if args else [], returncode=0, stdout="", stderr="")


class TestSchedulerGeneration(unittest.TestCase):
    def setUp(self):
        self.temp_home = tempfile.mkdtemp()
        self._old = (mmx.HOME, mmx.MINIMAX_DIR, mmx.LOGS_DIR, mmx.AUTH_PROFILES_DIR)
        mmx.HOME = self.temp_home
        mmx.MINIMAX_DIR = os.path.join(self.temp_home, ".minimax")
        mmx.LOGS_DIR = os.path.join(mmx.MINIMAX_DIR, "logs")
        mmx.AUTH_PROFILES_DIR = os.path.join(mmx.MINIMAX_DIR, "auth_profiles")
        os.makedirs(mmx.LOGS_DIR, exist_ok=True)

    def tearDown(self):
        mmx.HOME, mmx.MINIMAX_DIR, mmx.LOGS_DIR, mmx.AUTH_PROFILES_DIR = self._old
        shutil.rmtree(self.temp_home, ignore_errors=True)

    def test_launchd_calendar_plist(self):
        with patch("minimax.subprocess.run", side_effect=ok_run):
            rc = mmx._install_launchd("calendar")
        self.assertEqual(rc, mmx.EXIT_OK)

        path = mmx.launchd_plist_path()
        content = open(path, "r", encoding="utf-8").read()
        self.assertIn("<key>StartCalendarInterval</key>", content)
        self.assertIn("<key>Hour</key>", content)
        self.assertIn("<integer>9</integer>", content)
        self.assertIn("<integer>5</integer>", content)
        self.assertIn("checkin", content)
        self.assertIn("--all", content)
        self.assertIn("RunAtLoad</key>\n    <false/>", content)
        # 日志必须分轨，不能把 stdout 重新灌回审计日志（历史双写缺陷）
        self.assertIn("scheduler.out.log", content)
        self.assertIn("scheduler.err.log", content)
        self.assertNotIn("checkin.log", content)

    def test_launchd_boot_plist(self):
        with patch("minimax.subprocess.run", side_effect=ok_run):
            rc = mmx._install_launchd("boot")
        self.assertEqual(rc, mmx.EXIT_OK)
        content = open(mmx.launchd_plist_path(), "r", encoding="utf-8").read()
        self.assertNotIn("StartCalendarInterval", content)
        self.assertIn("RunAtLoad</key>\n    <true/>", content)

    def test_xml_escape_helper(self):
        self.assertEqual(mmx.xml_escape('a & <b> "c" \'d\''),
                         "a &amp; &lt;b&gt; &quot;c&quot; &apos;d&apos;")

    def test_launchd_escapes_xml_special_chars(self):
        # 只用 Windows 也合法的字符（& 与空格）建真实目录，其余字符用 helper 覆盖
        mmx.LOGS_DIR = os.path.join(self.temp_home, "weird & logs")
        os.makedirs(mmx.LOGS_DIR, exist_ok=True)
        with patch("minimax.subprocess.run", side_effect=ok_run):
            mmx._install_launchd("calendar")
        content = open(mmx.launchd_plist_path(), "r", encoding="utf-8").read()
        self.assertIn("weird &amp; logs", content)

    def test_systemd_calendar_units(self):
        with patch.dict(os.environ, {"MINIMAX_HOME": "/opt/mmx sandbox"}), \
             patch("minimax.shutil.which", return_value=None), \
             patch("minimax.subprocess.run", side_effect=ok_run):
            rc = mmx._install_systemd("calendar")
        self.assertEqual(rc, mmx.EXIT_OK)

        unit_dir = mmx.systemd_user_dir()
        service = open(os.path.join(unit_dir, f"{mmx.SYSTEMD_UNIT}.service"), "r", encoding="utf-8").read()
        timer = open(os.path.join(unit_dir, f"{mmx.SYSTEMD_UNIT}.timer"), "r", encoding="utf-8").read()
        self.assertIn("checkin --all", service)
        self.assertIn("Type=oneshot", service)
        self.assertIn("scheduler.out.log", service)
        self.assertNotIn("checkin.log", service)
        self.assertIn("OnCalendar=*-*-* 09:05:00", timer)
        self.assertIn("Persistent=true", timer)
        # systemd user manager 的 PATH 是固定的，必须显式补齐解释器目录，否则 pyenv/conda 下 127
        self.assertIn("Environment=\"PATH=", service)
        self.assertIn(os.path.dirname(sys.executable), service)
        self.assertIn('Environment="MINIMAX_HOME=/opt/mmx sandbox"', service)

    def test_systemd_units_follow_xdg_config_home(self):
        xdg = os.path.join(self.temp_home, "xdg")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": xdg}), \
             patch("minimax.shutil.which", return_value=None), \
             patch("minimax.subprocess.run", side_effect=ok_run):
            mmx._install_systemd("calendar")
        self.assertTrue(os.path.exists(os.path.join(xdg, "systemd", "user", f"{mmx.SYSTEMD_UNIT}.timer")))

    def test_systemd_boot_units(self):
        with patch("minimax.shutil.which", return_value=None), \
             patch("minimax.subprocess.run", side_effect=ok_run):
            rc = mmx._install_systemd("boot")
        self.assertEqual(rc, mmx.EXIT_OK)
        timer = open(os.path.join(mmx.systemd_user_dir(), f"{mmx.SYSTEMD_UNIT}.timer"),
                     "r", encoding="utf-8").read()
        self.assertIn("OnBootSec=", timer)
        self.assertNotIn("OnCalendar=", timer)

    def test_systemd_enable_failure_is_reported(self):
        def failing_run(cmd, *a, **kw):
            if "enable" in cmd:
                return CompletedProcess(args=cmd, returncode=1, stdout="", stderr="System has not been booted with systemd")
            return CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with patch("minimax.shutil.which", return_value="/bin/systemctl"), \
             patch("minimax.subprocess.run", side_effect=failing_run):
            rc = mmx._install_systemd("calendar")
        self.assertEqual(rc, mmx.EXIT_ERROR)

    def test_windows_task_calendar(self):
        calls = []

        def capture(cmd, *a, **kw):
            calls.append(cmd)
            return CompletedProcess(args=cmd, returncode=0, stdout="SUCCESS", stderr="")

        with patch("minimax.subprocess.run", side_effect=capture):
            rc = mmx._install_windows_task("calendar")
        self.assertEqual(rc, mmx.EXIT_OK)
        created = [c for c in calls if "/create" in c]
        self.assertEqual(len(created), 1)
        # 先建后删：创建之前不得删除另一种模式的可用任务
        self.assertIn("/create", calls[0])
        cmd = created[0]
        self.assertIn("/sc", cmd)
        self.assertIn("daily", cmd)
        self.assertIn("09:05", cmd)
        self.assertIn("checkin --all", cmd[cmd.index("/tr") + 1])
        # 必须清理另一种模式，避免双任务重复打卡
        self.assertTrue(any("/delete" in c and mmx.WINDOWS_TASK_BOOT in c for c in calls))

    def test_windows_task_boot(self):
        calls = []

        def capture(cmd, *a, **kw):
            calls.append(cmd)
            return CompletedProcess(args=cmd, returncode=0, stdout="SUCCESS", stderr="")

        with patch("minimax.subprocess.run", side_effect=capture):
            rc = mmx._install_windows_task("boot")
        self.assertEqual(rc, mmx.EXIT_OK)
        created = [c for c in calls if "/create" in c][0]
        self.assertIn("onlogon", created)

    def test_detect_scheduler_reads_generated_mode(self):
        with patch.object(sys, "platform", "darwin"), \
             patch("minimax.subprocess.run", side_effect=ok_run):
            mmx._install_launchd("boot")
            info = mmx.detect_scheduler()
        self.assertTrue(info["installed"])
        self.assertEqual(info["mode"], "boot")

    def test_scheduler_cli_command_prefers_installed_entry(self):
        if sys.platform == "win32":
            self.skipTest("Windows 使用 .cmd 垫片路径")
        bin_dir = os.path.join(self.temp_home, ".local", "bin")
        os.makedirs(bin_dir, exist_ok=True)
        installed = os.path.join(bin_dir, "minimax")
        with open(installed, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env python3\n")
        self.assertEqual(mmx.scheduler_cli_command(), [installed])


if __name__ == "__main__":
    unittest.main()
