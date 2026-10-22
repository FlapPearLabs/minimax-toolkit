import os
import sys
import json
import subprocess
import unittest
import tempfile
import shutil

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_PATH = os.path.join(REPO_DIR, "bin", "minimax")


class TestMinimaxCLI(unittest.TestCase):
    def setUp(self):
        self.temp_home = tempfile.mkdtemp()
        self.env = os.environ.copy()
        self.env["HOME"] = self.temp_home
        self.env["USERPROFILE"] = self.temp_home
        self.env["MINIMAX_HOME"] = os.path.join(self.temp_home, ".minimax")
        self.env.pop("MINIMAX_ACCOUNT_BASE", None)
        self.env.pop("MINIMAX_GATEWAY_BASE", None)
        self.env["PYTHONUTF8"] = "1"
        self.env["PYTHONIOENCODING"] = "utf-8"

    def tearDown(self):
        shutil.rmtree(self.temp_home, ignore_errors=True)

    def run_cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, CLI_PATH] + list(args),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=self.env, input=stdin)

    def test_version_command(self):
        res = self.run_cli("--version")
        self.assertEqual(res.returncode, 0)
        self.assertIn("minimax-toolkit v", res.stdout)

    def test_help_command(self):
        res = self.run_cli("help")
        self.assertEqual(res.returncode, 0)
        self.assertIn("核心命令用法", res.stdout)
        self.assertIn("minimax login", res.stdout)
        self.assertIn("minimax switch", res.stdout)
        self.assertIn("minimax cron", res.stdout)

    def test_no_args_prints_help(self):
        res = self.run_cli()
        self.assertEqual(res.returncode, 0)
        self.assertIn("核心命令用法", res.stdout)

    def test_unknown_command_is_usage_error(self):
        res = self.run_cli("foobar_invalid")
        self.assertEqual(res.returncode, 2)
        self.assertIn("未知命令: foobar_invalid", res.stdout)

    def test_doctor_offline_empty_environment(self):
        res = self.run_cli("doctor", "--offline")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("MiniMax Toolkit 运行时自检诊断报告", res.stdout)
        self.assertIn("0 个账号", res.stdout)
        self.assertNotIn("Traceback", res.stdout + res.stderr)

    def test_doctor_json_is_machine_readable(self):
        res = self.run_cli("doctor", "--offline", "--json")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["version"], "0.2.0")
        self.assertIn("checks", payload)
        self.assertIsInstance(payload["healthy"], bool)

    def test_list_empty_environment(self):
        res = self.run_cli("list")
        self.assertEqual(res.returncode, 0)
        self.assertIn("暂无任何录入账号", res.stdout)

    def test_list_json_empty_environment(self):
        res = self.run_cli("list", "--offline", "--json")
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["accounts"], [])

    def test_switch_without_alias_in_non_tty_fails_cleanly(self):
        """【P1 回归】无 TTY 时必须友好报错，绝不能 EOFError 回溯"""
        res = self.run_cli("switch", stdin="")
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertNotIn("Traceback", res.stdout + res.stderr)
        self.assertNotIn("EOFError", res.stdout + res.stderr)

    def test_checkin_invalid_alias_fails_cleanly(self):
        """【P1 回归】非法别名必须友好报错，绝不能 ValueError 回溯"""
        res = self.run_cli("checkin", "no such")
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("非法的账号别名", res.stdout + res.stderr)
        self.assertNotIn("Traceback", res.stdout + res.stderr)

    def test_status_missing_alias_fails_cleanly(self):
        res = self.run_cli("status", "ghost")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("未找到账号", res.stdout + res.stderr)
        self.assertNotIn("Traceback", res.stdout + res.stderr)

    def test_cron_status_is_implemented(self):
        """【P0 回归】cron status 必须是真的实现，而不是 '未知操作'"""
        res = self.run_cli("cron", "status")
        self.assertIn(res.returncode, (0, 1))
        self.assertNotIn("未知操作", res.stdout)
        self.assertIn("定时打卡服务状态", res.stdout)

    def test_cron_unknown_action_is_usage_error(self):
        res = self.run_cli("cron", "explode")
        self.assertEqual(res.returncode, 2)
        self.assertIn("未知操作", res.stdout)

    def test_cron_rejects_unknown_mode(self):
        res = self.run_cli("cron", "install", "--mode", "hourly")
        self.assertEqual(res.returncode, 2)
        self.assertIn("未知调度模式", res.stdout)

    def test_symlink_dispatch(self):
        """测试通过符号链接/垫片别名 (如 mmx-list) 调用的自动命令调度"""
        temp_link_dir = tempfile.mkdtemp()
        try:
            if sys.platform != "win32":
                link_path = os.path.join(temp_link_dir, "mmx-list")
                os.symlink(CLI_PATH, link_path)
                res = subprocess.run([link_path], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", env=self.env)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertIn("MiniMax 纳管账号清单", res.stdout)
            else:
                res = self.run_cli("list")
                self.assertEqual(res.returncode, 0)
                self.assertIn("MiniMax 纳管账号清单", res.stdout)
        finally:
            shutil.rmtree(temp_link_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
