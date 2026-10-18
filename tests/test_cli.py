#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax Toolkit CLI Unit Tests
https://github.com/FlapPearLabs/minimax-toolkit
"""

import os
import sys
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
        self.env["PYTHONUTF8"] = "1"
        self.env["PYTHONIOENCODING"] = "utf-8"

    def tearDown(self):
        shutil.rmtree(self.temp_home, ignore_errors=True)

    def test_version_command(self):
        res = subprocess.run([sys.executable, CLI_PATH, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)
        self.assertEqual(res.returncode, 0)
        self.assertIn("minimax-toolkit v", res.stdout)

    def test_help_command(self):
        res = subprocess.run([sys.executable, CLI_PATH, "help"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)
        self.assertEqual(res.returncode, 0)
        self.assertIn("核心命令用法", res.stdout)
        self.assertIn("minimax login", res.stdout)
        self.assertIn("minimax switch", res.stdout)

    def test_unknown_command(self):
        res = subprocess.run([sys.executable, CLI_PATH, "foobar_invalid"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)
        self.assertEqual(res.returncode, 1)
        self.assertIn("未知命令: foobar_invalid", res.stdout)

    def test_doctor_empty_environment(self):
        res = subprocess.run([sys.executable, CLI_PATH, "doctor"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)
        self.assertEqual(res.returncode, 0)
        self.assertIn("MiniMax Toolkit 运行时自检诊断报告", res.stdout)
        self.assertIn("纳管账号数量:    0 个", res.stdout)

    def test_list_empty_environment(self):
        res = subprocess.run([sys.executable, CLI_PATH, "list"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env)
        self.assertEqual(res.returncode, 0)
        self.assertIn("暂无任何录入账号", res.stdout)

if __name__ == "__main__":
    unittest.main()
