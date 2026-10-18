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
import stat
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

    def test_single_flight_file_lock_timeout_rejection(self):
        """测试单飞排他锁在争用超时时严格抛出 TimeoutError，杜绝静默穿透降级"""
        lock1 = mmx.SingleFlightFileLock(self.lock_path, timeout_sec=1.0)
        lock2 = mmx.SingleFlightFileLock(self.lock_path, timeout_sec=0.2)
        with lock1:
            with self.assertRaises(TimeoutError):
                with lock2:
                    pass

    def test_atomic_save_json_permissions_and_integrity(self):
        """测试 atomic_save_json 0o600 权限落地（POSIX）与数据原子刷盘完整性"""
        target_path = os.path.join(self.temp_dir, "secure_creds.json")
        sample_data = {"key": "secret_val", "list": [1, 2, 3]}
        mmx.atomic_save_json(target_path, sample_data)

        self.assertTrue(os.path.exists(target_path))
        loaded = mmx.load_json(target_path)
        self.assertEqual(loaded, sample_data)

        if sys.platform != "win32":
            st = os.stat(target_path)
            mode = stat.S_IMODE(st.st_mode)
            self.assertEqual(mode, 0o600)

    def test_alias_pattern_path_traversal_rejection(self):
        """测试 get_profile_path 严格拒绝跨目录穿越与非法别名输入"""
        invalid_aliases = [
            "../evil",
            "../../etc/passwd",
            "acc/sub",
            "acc\\sub",
            "acc space",
            "acc@123",
            "a" * 65,
            "",
            "   "
        ]
        for inv in invalid_aliases:
            with self.assertRaises(ValueError, msg=f"应该拒绝非法别名: {inv}"):
                mmx.get_profile_path(inv)

        valid_aliases = ["default", "work-1", "user_test_2", "Acc-09", "user.json"]
        for v in valid_aliases:
            path = mmx.get_profile_path(v)
            self.assertTrue(path.endswith(".json"))

    def test_sanitize_token_redaction(self):
        """测试 sanitize_token 对长 Token、Bearer 串的脱敏遮蔽效果"""
        raw_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiIxMjM0NTYifQ.abcd1234efgh5678"
        masked = mmx.sanitize_token(raw_jwt)
        self.assertNotIn("abcd1234efgh5678", masked)
        self.assertNotIn(raw_jwt, masked)
        self.assertEqual(masked, "<REDACTED_TOKEN>")

        log_line = f"Authorization: Bearer {raw_jwt}"
        redacted = mmx.sanitize_token(log_line)
        self.assertNotIn(raw_jwt, redacted)
        self.assertIn("<REDACTED_TOKEN>", redacted)

    def test_extract_account_meta_robustness(self):
        """测试 extract_account_meta 对空数据、短 UID 及无 Demo UID 回退的物理防御"""
        empty_meta = mmx.extract_account_meta({})
        self.assertEqual(empty_meta["userName"], "(无记录)")
        self.assertEqual(empty_meta["userId"], "(无记录)")
        self.assertNotIn("508070720593346564", str(empty_meta))

        meta_short = mmx.extract_account_meta({"userId": "123", "userName": "Alice"})
        self.assertEqual(meta_short["userId"], "123")
        self.assertEqual(meta_short["userName"], "Alice")

if __name__ == "__main__":
    unittest.main()
