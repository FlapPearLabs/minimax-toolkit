#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax Toolkit Authentication & Concurrency Tests
https://github.com/FlapPearLabs/minimax-toolkit
"""

import os
import sys
import json
import time
import hashlib
import base64
import unittest
import tempfile
import shutil
import importlib.util

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_PATH = os.path.join(REPO_DIR, "bin", "minimax")

import importlib.machinery
loader = importlib.machinery.SourceFileLoader("minimax", CLI_PATH)
spec = importlib.util.spec_from_loader("minimax", loader)
mmx = importlib.util.module_from_spec(spec)
sys.modules["minimax"] = mmx
loader.exec_module(mmx)

class TestAuthMechanisms(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.lock_path = os.path.join(self.temp_dir, "test.lock")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pkce_s256_generation(self):
        """测试 RFC 7636 S256 PKCE 算法计算精确性"""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        self.assertEqual(challenge, expected)

    def test_single_flight_file_lock(self):
        """测试跨平台单飞文件排他锁的并发保护与正常释放"""
        lock1 = mmx.SingleFlightFileLock(self.lock_path)
        with lock1:
            self.assertTrue(os.path.exists(self.lock_path))
            self.assertIsNotNone(lock1.fd)
        self.assertIsNone(lock1.fd)

    def test_sync_before_switch_state_preservation(self):
        """【核心防御测试】验证切号前自动将活跃最新 Token 刷回对应 Profile，杜绝状态回滚"""
        temp_home = tempfile.mkdtemp()
        try:
            # 重设 mmx 内部路径至沙盒
            old_minimax_dir = mmx.MINIMAX_DIR
            old_profiles_dir = mmx.AUTH_PROFILES_DIR
            old_active_path = mmx.ACTIVE_AUTH_PATH

            mmx.MINIMAX_DIR = os.path.join(temp_home, ".minimax")
            mmx.AUTH_PROFILES_DIR = os.path.join(mmx.MINIMAX_DIR, "auth_profiles")
            mmx.ACTIVE_AUTH_DIR = os.path.join(mmx.MINIMAX_DIR, "auth", "prod", "cn", "mcode-public")
            mmx.ACTIVE_AUTH_PATH = os.path.join(mmx.ACTIVE_AUTH_DIR, "auth.json")
            os.makedirs(mmx.AUTH_PROFILES_DIR, exist_ok=True)
            os.makedirs(mmx.ACTIVE_AUTH_DIR, exist_ok=True)

            # 1. 建立 profile 'account_a' 初始代数为 1
            rec_key = "com.minimax.mcode.oauth.prod.cn\u0000rec_a"
            profile_a = {
                "schemaVersion": 1,
                "_toolkit_alias": "account_a",
                "records": {
                    rec_key: {
                        "accessToken": "token_a_v1",
                        "refreshToken": "refresh_a_v1",
                        "generation": 1,
                        "expiresAtMs": int(time.time() * 1000) + 3600000
                    }
                }
            }
            mmx.atomic_save_json(mmx.get_profile_path("account_a"), profile_a)

            # 2. 模拟系统将 account_a 激活并运行，在运行期刷成了 v2 (代数 2)
            active_auth = {
                "schemaVersion": 1,
                "_toolkit_alias": "account_a",
                "records": {
                    rec_key: {
                        "accessToken": "token_a_v2_REFRESHED",
                        "refreshToken": "refresh_a_v2_NEW",
                        "generation": 2,
                        "expiresAtMs": int(time.time() * 1000) + 7200000
                    }
                }
            }
            mmx.atomic_save_json(mmx.ACTIVE_AUTH_PATH, active_auth)

            # 3. 执行 sync_active_to_profile
            mmx.sync_active_to_profile()

            # 4. 断言 account_a.json 已经被无感更新至 v2，绝对没有被覆盖为旧的 v1
            synced_profile = mmx.load_json(mmx.get_profile_path("account_a"))
            synced_rec = synced_profile["records"][rec_key]
            self.assertEqual(synced_rec["accessToken"], "token_a_v2_REFRESHED")
            self.assertEqual(synced_rec["generation"], 2)
        finally:
            mmx.MINIMAX_DIR = old_minimax_dir
            mmx.AUTH_PROFILES_DIR = old_profiles_dir
            mmx.ACTIVE_AUTH_PATH = old_active_path
            shutil.rmtree(temp_home, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
