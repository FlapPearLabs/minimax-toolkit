"""统一的 CLI 模块加载器。

unittest 发现阶段会 import 所有 test_*.py，如果每个测试模块各自
SourceFileLoader 一次 bin/minimax，sys.modules["minimax"] 会被后加载的
模块覆盖，导致 unittest.mock.patch("minimax.xxx") 打到错误的模块实例上。
这里做一次进程级缓存，保证所有测试共享同一个模块对象。
"""

import os
import sys
import importlib.util
import importlib.machinery

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_PATH = os.path.join(REPO_DIR, "bin", "minimax")


def load_cli():
    if "minimax_cli" in sys.modules:
        return sys.modules["minimax_cli"]
    loader = importlib.machinery.SourceFileLoader("minimax", CLI_PATH)
    spec = importlib.util.spec_from_loader("minimax", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["minimax"] = module
    sys.modules["minimax_cli"] = module
    loader.exec_module(module)
    return module
