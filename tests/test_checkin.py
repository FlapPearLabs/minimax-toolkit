import os
import sys
import json
import time
import hashlib
import unittest
import urllib.parse
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from _cli_loader import load_cli

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_PATH = os.path.join(REPO_DIR, "bin", "minimax")
mmx = load_cli()


class TestCheckinEngine(unittest.TestCase):
    def test_matrix_gateway_signature_calculation(self):
        """测试 Matrix Gateway 逆向加签算法准确性"""
        second = 1790674196
        body_str = '{"test":1}'
        expected_sig = hashlib.md5(f"{second}I*7Cf%WZ#S&%1RlZJ&C2{body_str}".encode("utf-8")).hexdigest()

        sig_source = f"{second}{mmx.SIGNATURE_SALT}{body_str}"
        self.assertEqual(mmx.md5(sig_source), expected_sig)

        now_ms = 1790674196000
        path = "/minimax-cloud/api/v1/signin/status?app_id=3001"
        yy_source = f"{urllib.parse.quote(path, safe='')}_{body_str}{mmx.md5(str(now_ms))}ooui"
        self.assertEqual(mmx.md5(yy_source), hashlib.md5(yy_source.encode("utf-8")).hexdigest())

    def test_timezone_aware_deterministic_timestamps(self):
        """【时区防线】断言时间戳解析全链路 Timezone-Aware，杜绝跨平台/CI 时区撕裂"""
        ms = 1792224084352  # 2026-10-17 16:01:24 CST
        dt_cst = datetime.fromtimestamp(ms / 1000.0, tz=timezone(timedelta(hours=8)))
        self.assertEqual(mmx.format_timestamp(ms), dt_cst.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertIsNotNone(dt_cst.tzinfo)

    @patch("minimax.write_state")
    @patch("minimax.list_profiles")
    @patch("minimax.checkin_single_profile")
    def test_conservation_invariant_partition(self, mock_single, mock_profiles, mock_state):
        """
        【全局守恒硬断言 - 真实调用 cmd_checkin】
        无论成功/已领/空闲/失败如何分布，四个分区之和必须严格等于处理总数，
        且汇总状态机只能落入 ok / partial / failed 三态。
        """
        accounts = ["acc_1", "acc_2", "acc_3", "acc_4"]
        distribution = {
            "acc_1": (True, "CLAIMED_SUCCESS"),
            "acc_2": (True, "ALREADY_CLAIMED"),
            "acc_3": (True, "NO_CLAIMABLE"),
            "acc_4": (False, "NETWORK_ERR"),
        }
        mock_profiles.return_value = accounts
        mock_single.side_effect = lambda alias, only_status=False: distribution[alias]

        captured = {}
        mock_state.side_effect = lambda patch: captured.update(patch)

        rc = mmx.cmd_checkin(["--all"])
        self.assertEqual(rc, mmx.EXIT_ERROR)  # 有失败 -> 非 0
        summary = captured["last_run_summary"]
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["claimed"], 1)
        self.assertEqual(summary["already"], 1)
        self.assertEqual(summary["idle"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["claimed"] + summary["already"] + summary["idle"] + summary["failed"],
                         summary["total"])
        self.assertEqual(captured["last_run_result"], "partial")

    @patch("minimax.write_state")
    @patch("minimax.list_profiles")
    @patch("minimax.checkin_single_profile")
    def test_conservation_all_success_sets_success_timestamp(self, mock_single, mock_profiles, mock_state):
        mock_profiles.return_value = ["a", "b"]
        mock_single.return_value = (True, "CLAIMED_SUCCESS")
        captured = {}
        mock_state.side_effect = lambda patch: captured.update(patch)

        rc = mmx.cmd_checkin(["--all"])
        self.assertEqual(rc, mmx.EXIT_OK)
        self.assertEqual(captured["last_run_result"], "ok")
        self.assertIn("last_success_at", captured)

    @patch("minimax.call_minimax_gateway")
    @patch("minimax.refresh_token_if_needed")
    @patch("minimax.load_json")
    def test_checkin_flow_idempotency_already_claimed(self, mock_load, mock_refresh, mock_gateway):
        """测试已签到状态下的幂等性（跳过 claim 领分，不重复请求）"""
        mock_load.return_value = {
            "schemaVersion": 1,
            "records": {
                "com.minimax.mcode.oauth.prod.cn\u0000rec": {
                    "accessToken": "mmoat_test",
                    "refreshToken": "mmort_test",
                    "userId": "123456",
                    "expiresAtMs": int(time.time() * 1000) + 3600000
                }
            }
        }
        mock_refresh.return_value = ("mmoat_test", False)
        mock_gateway.return_value = {
            "base_resp": {"status_code": 0, "status_msg": "ok"},
            "data": {"scene": 2, "days": [{"day_no": 1, "points": 400, "status": 3, "is_today": True}]}
        }

        ok, reason = mmx.checkin_single_profile("test_alias")
        self.assertTrue(ok)
        self.assertEqual(reason, "ALREADY_CLAIMED")
        self.assertEqual(mock_gateway.call_count, 1)

    @patch("minimax.call_minimax_gateway")
    @patch("minimax.refresh_token_if_needed")
    @patch("minimax.load_json")
    def test_checkin_flow_claims_and_persists_nothing_else(self, mock_load, mock_refresh, mock_gateway):
        """可领取状态必须且只能发起一次 claim，并返回 CLAIMED_SUCCESS"""
        mock_load.return_value = {
            "schemaVersion": 1,
            "records": {
                "k": {"accessToken": "mmoat_test", "refreshToken": "mmort_test",
                      "expiresAtMs": int(time.time() * 1000) + 3600000}
            }
        }
        mock_refresh.return_value = ("mmoat_test", False)
        mock_gateway.side_effect = [
            {"base_resp": {"status_code": 0}, "data": {"scene": 2, "days": [
                {"day_no": 2, "points": 400, "bonus_points": 100, "status": 2, "is_today": True}]}},
            {"base_resp": {"status_code": 0}, "data": {"points": 500}},
        ]

        ok, reason = mmx.checkin_single_profile("test_alias")
        self.assertTrue(ok)
        self.assertEqual(reason, "CLAIMED_SUCCESS")
        self.assertEqual(mock_gateway.call_count, 2)
        claim_call = mock_gateway.call_args_list[1]
        self.assertEqual(claim_call.args[0], "/minimax-cloud/api/v1/signin/claim")
        self.assertEqual(claim_call.kwargs.get("method"), "POST")

    @patch("minimax.call_minimax_gateway")
    @patch("minimax.refresh_token_if_needed")
    @patch("minimax.load_json")
    def test_checkin_network_failure_is_not_an_exception(self, mock_load, mock_refresh, mock_gateway):
        """网络失败必须被吸收为结构化 reason，绝不能冒泡成回溯"""
        mock_load.return_value = {"records": {"k": {"accessToken": "mmoat_test", "refreshToken": "mmort_test",
                                                    "expiresAtMs": int(time.time() * 1000) + 3600000}}}
        mock_refresh.return_value = ("mmoat_test", False)
        mock_gateway.side_effect = RuntimeError("MiniMax 网关网络连接失败: boom")

        ok, reason = mmx.checkin_single_profile("test_alias")
        self.assertFalse(ok)
        self.assertEqual(reason, "NETWORK_ERR")

    def test_exit_code_constants_are_distinct(self):
        codes = {mmx.EXIT_OK, mmx.EXIT_ERROR, mmx.EXIT_USAGE, mmx.EXIT_INTERNAL, mmx.EXIT_INVARIANT}
        self.assertEqual(len(codes), 5)


if __name__ == "__main__":
    unittest.main()
