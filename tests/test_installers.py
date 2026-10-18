#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax Toolkit Installer & Anti-Self-Destruction Tests
https://github.com/FlapPearLabs/minimax-toolkit
"""

import os
import sys
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
        self.env["PYTHONUTF8"] = "1"
        self.env["PYTHONIOENCODING"] = "utf-8"

    def tearDown(self):
        shutil.rmtree(self.temp_home, ignore_errors=True)

    def test_install_and_uninstall_lifecycle(self):
        """测试 install.py 与 uninstall.py 完整闭环与产物验证"""
        # 1. 运行安装器 (无 --with-services)
        res = subprocess.run([sys.executable, INSTALLER_PATH], capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)
        self.assertEqual(res.returncode, 0, f"install.py 失败: {res.stderr}\n{res.stdout}")
        self.assertIn("安装部署全部完成", res.stdout)

        # 2. 检查安装落盘物
        if sys.platform == "win32":
            bin_dir = os.path.join(self.temp_home, ".minimax", "bin")
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "minimax")))
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "minimax.cmd")))
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "mmx.cmd")))
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "mmx-checkin.cmd")))
        else:
            bin_dir = os.path.join(self.temp_home, ".local", "bin")
            self.assertTrue(os.path.exists(os.path.join(bin_dir, "minimax")))
            self.assertTrue(os.path.islink(os.path.join(bin_dir, "mmx")))
            self.assertTrue(os.path.islink(os.path.join(bin_dir, "minimax-checkin")))
            self.assertTrue(os.path.islink(os.path.join(bin_dir, "mmx-switch")))

        # 3. 运行卸载器 (默认保留数据)
        unres = subprocess.run([sys.executable, UNINSTALLER_PATH], capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)
        self.assertEqual(unres.returncode, 0, f"uninstall.py 失败: {unres.stderr}\n{unres.stdout}")
        self.assertIn("卸载完成", unres.stdout)

        # 4. 验证程序已清理
        if sys.platform == "win32":
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "minimax.cmd")))
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "mmx-checkin.cmd")))
        else:
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "minimax")))
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "mmx")))
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "minimax-checkin")))

    def test_anti_self_destruction_when_executing_in_place(self):
        """
        【铁律 15 防御测试：原地执行自噬防御 (Anti-Self-Destruction)】
        当用户在目标目录原地克隆或源码与目标处于同一目录时执行 install.py，
        物理断言：源码文件必须毫发无损保留，严禁发生自我删除抛出 FileNotFoundError！
        """
        # 构造源与目标一致的测试场景
        bin_dir = os.path.join(REPO_DIR, "bin")
        main_script = os.path.join(bin_dir, "minimax")
        self.assertTrue(os.path.exists(main_script))
        file_size_before = os.path.getsize(main_script)

        # 在 REPO_DIR 原地执行
        res = subprocess.run([sys.executable, INSTALLER_PATH], cwd=REPO_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)
        self.assertEqual(res.returncode, 0)

        # 物理断言源码未被自噬
        self.assertTrue(os.path.exists(main_script))
        self.assertEqual(os.path.getsize(main_script), file_size_before)

    def test_uninstall_with_purge(self):
        """测试 uninstall.py --purge 彻底清理账号凭据、日志与运行时状态"""
        # 1. 运行安装器
        subprocess.run([sys.executable, INSTALLER_PATH], capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)

        # 2. 模拟创建 profile 和 log
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
            f.write('sample log')

        self.assertTrue(os.path.exists(dummy_profile))
        self.assertTrue(os.path.exists(dummy_log))

        # 3. 执行 purge 卸载
        unres = subprocess.run([sys.executable, UNINSTALLER_PATH, "--purge"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)
        self.assertEqual(unres.returncode, 0)
        self.assertIn("彻底清理", unres.stdout)

        # 4. 物理断言数据目录已清理
        self.assertFalse(os.path.exists(profiles_dir))
        self.assertFalse(os.path.exists(dummy_profile))
        self.assertFalse(os.path.exists(dummy_log))

if __name__ == "__main__":
    unittest.main()
