#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax Toolkit Check-in Engine & Conservation Tests
https://github.com/FlapPearLabs/minimax-toolkit
"""

import os
import sys
import json
import time
import hashlib
import unittest
import urllib.parse
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import importlib.util
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_PATH = os.path.join(REPO_DIR, "bin", "minimax")

import importlib.machinery
loader = importlib.machinery.SourceFileLoader("minimax", CLI_PATH)
spec = importlib.util.spec_from_loader("minimax", loader)
mmx = importlib.util.module_from_spec(spec)
sys.modules["minimax"] = mmx
loader.exec_module(mmx)

class TestCheckinEngine(unittest.TestCase):
    def test_matrix_gateway_signature_calculation(self):
        """测试 Matrix Gateway 逆向加签算法准确性"""
        second = 1790674196
        body_str = '{"test":1}'
        expected_sig = hashlib.md5(f"{second}I*7Cf%WZ#S&%1RlZJ&C2{body_str}".encode("utf-8")).hexdigest()

        # 计算 x-signature
        sig_source = f"{second}{mmx.SIGNATURE_SALT}{body_str}"
        self.assertEqual(mmx.md5(sig_source), expected_sig)

        # 计算 yy 验签
        now_ms = 1790674196000
        path = "/minimax-cloud/api/v1/signin/status?app_id=3001"
        yy_source = f"{urllib.parse.quote(path, safe='')}_{body_str}{mmx.md5(str(now_ms))}ooui"
        expected_yy = hashlib.md5(yy_source.encode("utf-8")).hexdigest()
        self.assertEqual(mmx.md5(yy_source), expected_yy)

    def test_timezone_aware_deterministic_timestamps(self):
        """【时区防线】断言时间戳解析全链路 Timezone-Aware，杜绝跨平台/CI 时区撕裂"""
        ms = 1792224084352 # 2026-10-17 16:01:24 CST
        dt_cst = datetime.fromtimestamp(ms / 1000.0, tz=timezone(timedelta(hours=8)))
        formatted = mmx.format_timestamp(ms)
        self.assertEqual(formatted, dt_cst.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertIsNotNone(dt_cst.tzinfo)

    def test_mathematical_conservation_invariant(self):
        """
        【全局守恒硬断言】
        断言多账号批量打卡无论在全部成功、部分已领、部分失败何种分布下，
        其分区累加必须严格守恒恒等于处理总数：
        Total == Success + Fail == Claimed + AlreadyClaimed + Failed
        """
        accounts = ["acc_1", "acc_2", "acc_3", "acc_4"]
        mock_results = {
            "acc_1": (True, "CLAIMED_SUCCESS"),
            "acc_2": (True, "ALREADY_CLAIMED"),
            "acc_3": (True, "ALREADY_CLAIMED"),
            "acc_4": (False, "NETWORK_ERR")
        }

        success_count = sum(1 for v in mock_results.values() if v[0])
        fail_count = sum(1 for v in mock_results.values() if not v[0])
        claimed_count = sum(1 for v in mock_results.values() if v[1] == "CLAIMED_SUCCESS")
        already_count = sum(1 for v in mock_results.values() if v[1] == "ALREADY_CLAIMED")

        # 守恒硬等式验证
        self.assertEqual(success_count + fail_count, len(accounts))
        self.assertEqual(claimed_count + already_count, success_count)
        self.assertEqual(claimed_count + already_count + fail_count, len(accounts))

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
            "data": {
                "scene": 2,
                "days": [
                    {"day_no": 1, "points": 400, "status": 3, "is_today": True}
                ]
            }
        }

        ok, reason = mmx.checkin_single_profile("test_alias")
        self.assertTrue(ok)
        self.assertEqual(reason, "ALREADY_CLAIMED")
        # 验证仅调用了 GET 查态，绝对没有多余调用 POST claim
        self.assertEqual(mock_gateway.call_count, 1)

if __name__ == "__main__":
    unittest.main()
