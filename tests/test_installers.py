import os
import sys
import json
import shutil
import tempfile
import unittest
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLER_PATH = os.path.join(REPO_DIR, "install.py")
UNINSTALLER_PATH = os.path.join(REPO_DIR, "uninstall.py")


class TestInstallersLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp_home = tempfile.mkdtemp()
        self.env = os.environ.copy()
        self.env["HOME"] = self.temp_home
        self.env["USERPROFILE"] = self.temp_home
        self.env["MINIMAX_HOME"] = os.path.join(self.temp_home, ".minimax")
        self.env["PYTHONUTF8"] = "1"
        self.env["PYTHONIOENCODING"] = "utf-8"

    def tearDown(self):
        shutil.rmtree(self.temp_home, ignore_errors=True)

    def bin_dir(self):
        if sys.platform == "win32":
            return os.path.join(self.temp_home, ".minimax", "bin")
        return os.path.join(self.temp_home, ".local", "bin")

    def run_py(self, script, *args, timeout=120):
        return subprocess.run([sys.executable, script] + list(args),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=self.env, timeout=timeout)

    def test_install_and_uninstall_lifecycle(self):
        """测试 install.py 与 uninstall.py 完整闭环、后置自检与产物验证"""
        res = self.run_py(INSTALLER_PATH)
        self.assertEqual(res.returncode, 0, f"install.py 失败: {res.stderr}\n{res.stdout}")
        self.assertIn("安装部署全部完成", res.stdout)
        self.assertIn("安装后自检通过", res.stdout)
        self.assertIn("已跳过定时服务自动注册", res.stdout)

        bin_dir = self.bin_dir()
        if sys.platform == "win32":
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "minimax")))
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "minimax.cmd")))
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "mmx.cmd")))
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "mmx-checkin.cmd")))
        else:
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "minimax")))
            self.assertTrue(os.path.islink(os.path.join(bin_dir, "mmx")))
            self.assertTrue(os.path.islink(os.path.join(bin_dir, "minimax-checkin")))
            self.assertTrue(os.path.islink(os.path.join(bin_dir, "mmx-switch")))

        unres = self.run_py(UNINSTALLER_PATH)
        self.assertEqual(unres.returncode, 0, f"uninstall.py 失败: {unres.stderr}\n{unres.stdout}")
        self.assertIn("卸载完成", unres.stdout)

        if sys.platform == "win32":
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "minimax.cmd")))
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "mmx-checkin.cmd")))
        else:
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "minimax")))
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "mmx")))
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "minimax-checkin")))

    def test_windows_cmd_wrapper_propagates_exit_code(self):
        """【P1 回归】cmd 的 if(...) 块会在解析期展开 %ERRORLEVEL%，导致永远返回 0"""
        import importlib.util as _iu
        spec = _iu.spec_from_file_location("mmx_installer", INSTALLER_PATH)
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        wrapper = mod._windows_cmd_wrapper()
        self.assertIn("goto :mmx_py", wrapper)
        self.assertNotIn("if %ERRORLEVEL% equ 0 (", wrapper)
        # 每个解释器分支后都必须紧跟一次独立的 exit /b %ERRORLEVEL%
        self.assertEqual(wrapper.count("exit /b %ERRORLEVEL%"), 3)

    def test_install_rejects_unknown_checkin_mode(self):
        res = self.run_py(INSTALLER_PATH, "--checkin-mode=hourly")
        self.assertEqual(res.returncode, 1)
        self.assertIn("仅支持 calendar / boot / none", res.stdout)

    def test_anti_self_destruction_when_executing_in_place(self):
        """
        【铁律 15 防御测试：原地执行自噬防御 (Anti-Self-Destruction)】
        源码与目标同路径时执行 install.py，源码必须毫发无损。
        """
        main_script = os.path.join(REPO_DIR, "bin", "minimax")
        self.assertTrue(os.path.exists(main_script))
        size_before = os.path.getsize(main_script)

        res = subprocess.run([sys.executable, INSTALLER_PATH], cwd=REPO_DIR,
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", env=self.env)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(os.path.exists(main_script))
        self.assertEqual(os.path.getsize(main_script), size_before)

    def test_uninstall_skips_foreign_same_name_files(self):
        """安全边界：~/.local/bin 下不属于本工具的同名文件不得被删除"""
        if sys.platform == "win32":
            self.skipTest("仅 POSIX 有同名文件语义")
        bin_dir = self.bin_dir()
        os.makedirs(bin_dir, exist_ok=True)
        foreign = os.path.join(bin_dir, "minimax")
        with open(foreign, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho totally-unrelated-tool\n")

        res = self.run_py(UNINSTALLER_PATH)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(foreign))
        self.assertIn("已跳过非本工具的同名文件", res.stdout)

    def test_uninstall_with_purge_cleans_runtime_state(self):
        """测试 uninstall.py --purge 彻底清理凭据、日志、state.json 与运行时状态"""
        self.run_py(INSTALLER_PATH)

        mmx_dir = os.path.join(self.temp_home, ".minimax")
        profiles_dir = os.path.join(mmx_dir, "auth_profiles")
        logs_dir = os.path.join(mmx_dir, "logs")
        os.makedirs(profiles_dir, exist_ok=True)
        os.makedirs(logs_dir, exist_ok=True)
        dummy_profile = os.path.join(profiles_dir, "test.json")
        with open(dummy_profile, "w", encoding="utf-8") as f:
            f.write('{"test": true}')
        dummy_log = os.path.join(logs_dir, "checkin.log")
        with open(dummy_log, "w", encoding="utf-8") as f:
            f.write("sample log")
        state_path = os.path.join(mmx_dir, "state.json")
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"last_run_result": "ok"}, f)

        unres = self.run_py(UNINSTALLER_PATH, "--purge")
        self.assertEqual(unres.returncode, 0)
        self.assertIn("彻底清理", unres.stdout)

        self.assertFalse(os.path.exists(profiles_dir))
        self.assertFalse(os.path.exists(dummy_profile))
        self.assertFalse(os.path.exists(dummy_log))
        self.assertFalse(os.path.exists(state_path))


    def test_purge_refuses_directories_without_toolkit_fingerprint(self):
        """安全边界：MINIMAX_HOME 指向普通工程目录时，--purge 不得删除其中的 bin/ 与 logs/"""
        project = os.path.join(self.temp_home, "some-project")
        os.makedirs(os.path.join(project, "bin"))
        os.makedirs(os.path.join(project, "logs"))
        keep = os.path.join(project, "bin", "important.sh")
        with open(keep, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")

        env = dict(self.env)
        env["MINIMAX_HOME"] = project
        res = subprocess.run([sys.executable, UNINSTALLER_PATH, "--purge"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", env=env)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(os.path.exists(keep))
        self.assertIn("未发现 MiniMax Toolkit 数据指纹", res.stdout)


if __name__ == "__main__":
    unittest.main()
