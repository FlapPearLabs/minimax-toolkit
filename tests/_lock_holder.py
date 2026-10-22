"""测试辅助进程：持有跨进程排他锁指定秒数后退出。

由 tests/test_auth.py 以子进程方式拉起，用于验证 flock / msvcrt 的
真实跨进程互斥语义（而非同进程内的可重入短路）。
"""

import os
import sys
import time
import importlib.util
import importlib.machinery

LOCK_PATH = sys.argv[1]
HOLD_SECONDS = float(sys.argv[2])

CLI_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "minimax")

loader = importlib.machinery.SourceFileLoader("minimax_lock_holder", CLI_PATH)
spec = importlib.util.spec_from_loader("minimax_lock_holder", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

with module.SingleFlightFileLock(LOCK_PATH):
    print("HELD", flush=True)
    time.sleep(HOLD_SECONDS)
