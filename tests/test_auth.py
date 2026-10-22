import os
import sys
import json
import time
import threading
import unittest
import tempfile
import shutil
import subprocess
import stat
import hashlib
import base64
from _cli_loader import load_cli

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_PATH = os.path.join(REPO_DIR, "bin", "minimax")
mmx = load_cli()


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

    def test_lock_is_reentrant_in_same_thread(self):
        """【P0 回归】同一线程嵌套加锁必须立即成功，绝不能自锁死 30 秒"""
        started = time.time()
        with mmx.SingleFlightFileLock(self.lock_path):
            with mmx.SingleFlightFileLock(self.lock_path):
                with mmx.SingleFlightFileLock(self.lock_path):
                    self.assertLess(time.time() - started, 5.0)
        # 全部退出后必须彻底释放，另一个线程可立即获取
        with mmx.SingleFlightFileLock(self.lock_path, timeout_sec=1.0):
            pass

    def test_lock_blocks_other_thread(self):
        """不同线程仍必须严格互斥（可重入只对同线程生效）"""
        errors = []

        def contender():
            try:
                with mmx.SingleFlightFileLock(self.lock_path, timeout_sec=0.3):
                    errors.append("acquired")
            except TimeoutError:
                errors.append("timeout")

        with mmx.SingleFlightFileLock(self.lock_path):
            t = threading.Thread(target=contender)
            t.start()
            t.join(10)
        self.assertEqual(errors, ["timeout"])

    def test_sync_before_switch_state_preservation(self):
        """【核心防御测试】验证切号前自动将活跃最新 Token 刷回对应 Profile，杜绝状态回滚"""
        temp_home = tempfile.mkdtemp()
        try:
            old_minimax_dir = mmx.MINIMAX_DIR
            old_profiles_dir = mmx.AUTH_PROFILES_DIR
            old_active_path = mmx.ACTIVE_AUTH_PATH
            old_lock_path = mmx.LOCK_FILE_PATH

            mmx.MINIMAX_DIR = os.path.join(temp_home, ".minimax")
            mmx.AUTH_PROFILES_DIR = os.path.join(mmx.MINIMAX_DIR, "auth_profiles")
            mmx.ACTIVE_AUTH_DIR = os.path.join(mmx.MINIMAX_DIR, "auth", "prod", "cn", "mcode-public")
            mmx.ACTIVE_AUTH_PATH = os.path.join(mmx.ACTIVE_AUTH_DIR, "auth.json")
            mmx.LOCK_FILE_PATH = os.path.join(mmx.MINIMAX_DIR, "auth", "token_refresh.lock")
            os.makedirs(mmx.AUTH_PROFILES_DIR, exist_ok=True)
            os.makedirs(mmx.ACTIVE_AUTH_DIR, exist_ok=True)

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

            mmx.sync_active_to_profile()

            synced_profile = mmx.load_json(mmx.get_profile_path("account_a"))
            synced_rec = synced_profile["records"][rec_key]
            self.assertEqual(synced_rec["accessToken"], "token_a_v2_REFRESHED")
            self.assertEqual(synced_rec["generation"], 2)
        finally:
            mmx.MINIMAX_DIR = old_minimax_dir
            mmx.AUTH_PROFILES_DIR = old_profiles_dir
            mmx.ACTIVE_AUTH_PATH = old_active_path
            mmx.LOCK_FILE_PATH = old_lock_path
            shutil.rmtree(temp_home, ignore_errors=True)

    def test_single_flight_file_lock_timeout_rejection(self):
        """【跨进程】真实多进程争用时必须严格超时，杜绝静默穿透降级"""
        holder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lock_holder.py")
        proc = subprocess.Popen([sys.executable, holder, self.lock_path, "1.5"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace")
        try:
            line = proc.stdout.readline().strip()
            self.assertEqual(line, "HELD")
            with self.assertRaises(TimeoutError):
                with mmx.SingleFlightFileLock(self.lock_path, timeout_sec=0.3):
                    pass
        finally:
            proc.wait(timeout=15)
        # 持有进程退出后必须能立刻获取
        with mmx.SingleFlightFileLock(self.lock_path, timeout_sec=2.0):
            pass

    def test_atomic_save_json_permissions_and_integrity(self):
        """测试 atomic_save_json 0o600 权限落地（POSIX）与数据原子刷盘完整性"""
        target_path = os.path.join(self.temp_dir, "secure_creds.json")
        sample_data = {"key": "secret_val", "list": [1, 2, 3]}
        mmx.atomic_save_json(target_path, sample_data)

        self.assertTrue(os.path.exists(target_path))
        self.assertEqual(mmx.load_json(target_path), sample_data)

        if sys.platform != "win32":
            mode = stat.S_IMODE(os.stat(target_path).st_mode)
            self.assertEqual(mode, 0o600)

    def test_alias_pattern_path_traversal_rejection(self):
        """测试 get_profile_path 严格拒绝跨目录穿越与非法别名输入"""
        invalid_aliases = ["../evil", "../../etc/passwd", "acc/sub", "acc\\sub",
                           "acc space", "acc@123", "a" * 65, "", "   "]
        for inv in invalid_aliases:
            with self.assertRaises(ValueError, msg=f"应该拒绝非法别名: {inv}"):
                mmx.get_profile_path(inv)

        for v in ["default", "work-1", "user_test_2", "Acc-09", "user.json"]:
            self.assertTrue(mmx.get_profile_path(v).endswith(".json"))

    def test_sanitize_token_redaction(self):
        """测试 sanitize_token 对长 Token、Bearer 串的脱敏遮蔽效果"""
        def b64(obj):
            return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

        raw_jwt = ".".join([b64({"alg": "HS256", "typ": "JWT"}), b64({"userId": "123456"}), "abcd1234efgh5678"])
        masked = mmx.sanitize_token(raw_jwt)
        self.assertNotIn("abcd1234efgh5678", masked)
        self.assertEqual(masked, "<REDACTED_TOKEN>")

        redacted = mmx.sanitize_token(f"Authorization: Bearer {raw_jwt}")
        self.assertNotIn(raw_jwt, redacted)
        self.assertIn("<REDACTED_TOKEN>", redacted)

        self.assertNotIn("mmoat_realsecret123456", mmx.sanitize_token("token=mmoat_realsecret123456"))

    def test_extract_account_meta_robustness(self):
        """测试 extract_account_meta 对空数据、明文 UID、JWT 回退与脱敏的物理防御"""
        empty_meta = mmx.extract_account_meta({})
        self.assertEqual(empty_meta["userName"], "")
        self.assertEqual(empty_meta["userId"], "")
        self.assertEqual(empty_meta["generation"], 0)

        meta_short = mmx.extract_account_meta({"userId": "123", "userName": "Alice"})
        self.assertEqual(meta_short["userId"], "123")
        self.assertEqual(meta_short["userName"], "Alice")

        # 不透明 mmoat_ token 不得被强行解析成垃圾数据
        opaque = mmx.extract_account_meta({"accessToken": "mmoat_abcdef123456", "refreshToken": "mmort_x"})
        self.assertEqual(opaque["userId"], "")

        # 合法 JWT 才允许解析出 user.id
        payload = base64.urlsafe_b64encode(json.dumps({"user": {"id": "998877"}}).encode()).decode().rstrip("=")
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
        jwt = f"{header}.{payload}.sig"
        parsed = mmx.extract_account_meta({"accessToken": jwt})
        self.assertEqual(parsed["userId"], "998877")

    def test_user_display_never_leaks_full_uid(self):
        self.assertEqual(mmx.user_display({"userName": "MiniMax用户", "userId": "508070720593346564"}),
                         "MiniMax用户 (50807072..)")
        self.assertEqual(mmx.user_display({"userName": "MiniMax用户", "userId": ""}), "MiniMax用户")


if __name__ == "__main__":
    unittest.main()
