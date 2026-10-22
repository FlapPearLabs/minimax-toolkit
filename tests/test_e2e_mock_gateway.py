import os
import sys
import json
import time
import hashlib
import shutil
import tempfile
import threading
import unittest
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_PATH = os.path.join(REPO_DIR, "bin", "minimax")

SIGNATURE_SALT = "I*7Cf%WZ#S&%1RlZJ&C2"
YY_SUFFIX = "ooui"


def md5(value):
    return hashlib.md5(value.encode("utf-8")).hexdigest()


class MockState:
    def __init__(self):
        self.lock = threading.Lock()
        self.device_codes = {}
        self.tokens = {}          # access_token -> account
        self.refresh_tokens = {}  # refresh_token -> access_token
        self.counter = 0
        self.signature_failures = []
        self.claims = []
        self.refresh_grants = 0

    def new_account(self, device_code):
        with self.lock:
            self.counter += 1
            idx = self.counter
            access = f"mmoat_mockacc{idx}"
            refresh = f"mmort_mockacc{idx}"
            account = {"idx": idx, "claimed": False, "device_code": device_code}
            self.tokens[access] = account
            self.refresh_tokens[refresh] = access
            return access, refresh


class MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    state = None  # injected

    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _verify_gateway_signature(self, raw_body):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            now_ms = int(query["unix"][0])
        except Exception:
            # 无签名探针（doctor 连通性检查）不算客户端加签失败
            return False
        body_sig = raw_body.decode("utf-8") if raw_body else ""
        body_yy = body_sig if raw_body else "{}"
        expected_yy = md5(urllib.parse.quote(self.path, safe="") + "_" + body_yy + md5(str(now_ms)) + YY_SUFFIX)
        expected_sig = md5(str(now_ms // 1000) + SIGNATURE_SALT + body_sig)
        ok = self.headers.get("yy") == expected_yy and self.headers.get("x-signature") == expected_sig
        if not ok:
            self.state.signature_failures.append(self.path)
        return ok

    def _auth_account(self):
        auth = self.headers.get("Authorization") or ""
        token = auth[7:] if auth.startswith("Bearer ") else ""
        return token, self.state.tokens.get(token)

    def do_POST(self):
        raw = self._read_body()
        if self.path.startswith("/oauth2/device/code"):
            form = urllib.parse.parse_qs(raw.decode("utf-8"))
            if form.get("code_challenge_method") != ["S256"] or not form.get("code_challenge"):
                self._send(400, {"error": "invalid_request"})
                return
            with self.state.lock:
                self.state.counter += 0
                device_code = f"device-{len(self.state.device_codes) + 1}"
                self.state.device_codes[device_code] = "pending"
            self._send(200, {
                "device_code": device_code,
                "user_code": "MOCK-0001",
                "verification_uri_complete": "http://127.0.0.1/activate",
                "verification_uri": "http://127.0.0.1/activate",
                "interval": 1,
                "expires_in": 60,
            })
            return

        if self.path.startswith("/oauth2/token"):
            form = urllib.parse.parse_qs(raw.decode("utf-8"))
            grant = (form.get("grant_type") or [""])[0]
            if grant == "urn:ietf:params:oauth:grant-type:device_code":
                device_code = (form.get("device_code") or [""])[0]
                if not device_code or device_code not in self.state.device_codes:
                    self._send(400, {"error": "invalid_grant"})
                    return
                access, refresh = self.state.new_account(device_code)
                self._send(200, {"access_token": access, "refresh_token": refresh,
                                 "token_type": "Bearer", "expires_in": 3600})
                return
            if grant == "refresh_token":
                refresh = (form.get("refresh_token") or [""])[0]
                access = self.state.refresh_tokens.get(refresh)
                if not access:
                    self._send(400, {"error": "invalid_grant",
                                     "error_description": "refresh token can no longer be used"})
                    return
                with self.state.lock:
                    self.state.refresh_grants += 1
                    old = self.state.tokens.pop(access)
                    new_access = f"{access}_r{self.state.refresh_grants}"
                    new_refresh = f"{refresh}_r{self.state.refresh_grants}"
                    self.state.tokens[new_access] = old
                    self.state.refresh_tokens[new_refresh] = new_access
                self._send(200, {"access_token": new_access, "refresh_token": new_refresh,
                                 "token_type": "Bearer", "expires_in": 3600})
                return
            self._send(400, {"error": "unsupported_grant_type"})
            return

        if self.path.startswith("/minimax-cloud/api/v1/signin/claim"):
            if not self._verify_gateway_signature(raw):
                self._send(403, {"base_resp": {"status_code": 1001, "status_msg": "bad signature"}})
                return
            token, account = self._auth_account()
            if not account:
                self._send(401, {"base_resp": {"status_code": 1002, "status_msg": "unauthorized"}})
                return
            with self.state.lock:
                account["claimed"] = True
                self.state.claims.append(token)
            self._send(200, {"base_resp": {"status_code": 0, "status_msg": "ok"},
                             "data": {"points": 400}})
            return

        self._send(404, {"error": "not_found"})

    def do_GET(self):
        if self.path.startswith("/minimax-cloud/api/v1/signin/status"):
            if not self._verify_gateway_signature(b""):
                self._send(403, {"base_resp": {"status_code": 1001, "status_msg": "bad signature"}})
                return
            token, account = self._auth_account()
            if not account:
                self._send(401, {"base_resp": {"status_code": 1002, "status_msg": "unauthorized"}})
                return
            status = 3 if account["claimed"] else 2
            self._send(200, {
                "base_resp": {"status_code": 0, "status_msg": "ok"},
                "data": {"scene": 2, "days": [
                    {"day_no": 1, "points": 400, "bonus_points": 0, "status": 3, "is_today": False},
                    {"day_no": 2, "points": 400, "bonus_points": 0, "status": status, "is_today": True},
                ]},
            })
            return

        self._send(404, {"error": "not_found"})


class TestEndToEndMockGateway(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = MockState()
        handler = type("BoundHandler", (MockHandler,), {"state": cls.state})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.temp_home = tempfile.mkdtemp()
        self.env = os.environ.copy()
        self.env["HOME"] = self.temp_home
        self.env["USERPROFILE"] = self.temp_home
        self.env["MINIMAX_HOME"] = os.path.join(self.temp_home, ".minimax")
        self.env["MINIMAX_ACCOUNT_BASE"] = self.base
        self.env["MINIMAX_GATEWAY_BASE"] = self.base
        self.env["MINIMAX_NO_BROWSER"] = "1"
        self.env["PYTHONUTF8"] = "1"
        self.env["PYTHONIOENCODING"] = "utf-8"
        with self.state.lock:
            self.state.claims.clear()
            self.state.signature_failures.clear()

    def tearDown(self):
        shutil.rmtree(self.temp_home, ignore_errors=True)

    def run_cli(self, *args, timeout=60):
        return subprocess.run([sys.executable, CLI_PATH] + list(args),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=self.env, timeout=timeout, input="")

    def profile_path(self, alias):
        return os.path.join(self.temp_home, ".minimax", "auth_profiles", f"{alias}.json")

    def test_full_lifecycle_login_switch_checkin(self):
        # 1. 设备码登录两个账号
        for alias in ("acc1", "acc2"):
            res = self.run_cli("login", alias, "--no-browser")
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertIn("绑定成功", res.stdout)
            self.assertTrue(os.path.exists(self.profile_path(alias)))

        # 2. 清单（离线）显示两个账号，acc1 为默认活跃
        res = self.run_cli("list", "--offline", "--json")
        payload = json.loads(res.stdout)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["current"], "acc1")

        # 3. 切号必须快速成功（P0 死锁回归）
        started = time.time()
        res = self.run_cli("switch", "acc2", timeout=45)
        elapsed = time.time() - started
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertLess(elapsed, 10.0, f"switch 耗时 {elapsed:.1f}s，疑似重新引入锁死")
        self.assertIn("账号切换成功", res.stdout)

        # 4. 单账号打卡（默认当前账号 acc2），必须真实 claim
        res = self.run_cli("checkin")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("签到成功", res.stdout)

        # 5. 全量打卡：acc2 已领、acc1 新领，总计 2 次 claim
        res = self.run_cli("checkin", "--all")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(len(self.state.claims), 2)
        self.assertEqual(len(set(self.state.claims)), 2)

        # 6. 全部请求签名必须被服务端复核通过
        self.assertEqual(self.state.signature_failures, [])

        # 7. audit：token 仍有效，不应触发刷新
        res = self.run_cli("audit", "--all")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("有效健康", res.stdout)

        # 8. state.json 反映最近一次成功执行
        state = json.load(open(os.path.join(self.temp_home, ".minimax", "state.json")))
        self.assertEqual(state["last_run_result"], "ok")
        self.assertEqual(state["last_run_summary"]["total"], 2)
        self.assertEqual(state["last_run_summary"]["claimed"], 1)
        self.assertEqual(state["last_run_summary"]["already"], 1)

        # 9. doctor 走 mock 网关也应健康
        res = self.run_cli("doctor", "--json")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        doc = json.loads(res.stdout)
        self.assertTrue(doc["healthy"], doc["checks"])
        self.assertEqual(len(doc["profiles"]), 2)

        # 10. cron status 已是真实实现
        res = self.run_cli("cron", "status")
        self.assertIn(res.returncode, (0, 1))
        self.assertIn("定时打卡服务状态", res.stdout)

    def test_refresh_rotation_persists_to_profile_and_active(self):
        res = self.run_cli("login", "rotate", "--no-browser")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

        path = self.profile_path("rotate")
        active = os.path.join(self.temp_home, ".minimax", "auth", "prod", "cn", "mcode-public", "auth.json")
        profile = json.load(open(path))
        rec_key = list(profile["records"].keys())[0]
        old_token = profile["records"][rec_key]["accessToken"]
        old_generation = profile["records"][rec_key]["generation"]

        # 人为把 token 置为已过期，触发滚动续期
        profile["records"][rec_key]["expiresAtMs"] = int(time.time() * 1000) - 1000
        json.dump(profile, open(path, "w"))

        res = self.run_cli("audit", "rotate")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("无感续杯", res.stdout)

        new_profile = json.load(open(path))
        new_token = new_profile["records"][rec_key]["accessToken"]
        self.assertNotEqual(new_token, old_token)
        self.assertEqual(new_profile["records"][rec_key]["generation"], old_generation + 1)

        # 活跃凭据同样被同步刷新（首次 login 已自动激活）
        active_data = json.load(open(active))
        self.assertEqual(list(active_data["records"].values())[0]["accessToken"], new_token)

    def test_expired_refresh_token_reports_cleanly(self):
        res = self.run_cli("login", "deadref", "--no-browser")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

        path = self.profile_path("deadref")
        profile = json.load(open(path))
        rec_key = list(profile["records"].keys())[0]
        profile["records"][rec_key]["expiresAtMs"] = int(time.time() * 1000) - 1000
        profile["records"][rec_key]["refreshToken"] = "mmort_revoked"
        json.dump(profile, open(path, "w"))

        res = self.run_cli("audit", "deadref")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertNotIn("Traceback", res.stdout + res.stderr)
        self.assertIn("自愈失败", res.stdout)


if __name__ == "__main__":
    unittest.main()
