# MiniMax Toolkit (`minimax` CLI)

> **Zero-Dependency Multi-Account Manager & Automated Check-in Engine for MiniMax Code**
> Developed & Maintained by [FlapPearLabs](https://github.com/FlapPearLabs)

[![CI & Zero-Leak Audit](https://github.com/FlapPearLabs/minimax-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/FlapPearLabs/minimax-toolkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-brightgreen.svg)]()

---

## 💡 为什么需要 MiniMax Toolkit？

MiniMax Code 官方客户端基于 Electron 框架，运行内存较高，且单机仅支持挂载单一登录凭据，不支持多账号便捷轮换。同时，每日签到积分是模型高频调用的重要免费额度来源。

**MiniMax Toolkit** 彻底剥离 UI 负担，以**零依赖、纯 Python 3 标准库**打造了一套开箱即用的底层凭据治理与自动化打卡套件：

- 🔄 **多账号无缝纳管**：专为 3~4 个日常主力/备用账号设计，免去繁琐切换退出。
- ⚡ **RFC 8628 免扫码授权**：基于 OAuth 2.0 Device Flow 与 S256 PKCE，CLI 一键拉起浏览器授权，无需手机反复扫码。
- 🛡️ **自愈防回滚机制 (Sync-before-Switch)**：切号前自动对齐落盘最新 Token，杜绝运行期刷新与 profile 回滚冲突。
- 🔒 **同线程可重入的单飞排他锁**：同一进程内嵌套调用不再自锁死；跨线程、跨进程仍严格串行化 Token 刷新。
- 🕒 **全平台原生静默签到**：macOS `launchd`、Linux `systemd user timer`、Windows 计划任务三端一等公民支持，支持 `calendar`（每日 09:05）与 `boot`（开机/登录后）两种调度模式。
- 📊 **可观测的对账与自检**：每次打卡写入 `state.json`，`doctor` 检查凭据有效期、调度器真实激活态、最近一次打卡新鲜度与网关连通性，不健康返回非 0。
- 🧪 **真实链路 E2E**：本地 mock 网关在测试中**服务端复算 `yy` / `x-signature`**，签名算法一旦漂移立刻红灯。

---

## 🚀 极速安装

系统已预装 Python 3.10+ 即可无缝部署，无需任何第三方 pip 依赖：

### macOS & Linux
```bash
git clone https://github.com/FlapPearLabs/minimax-toolkit.git ~/.minimax-toolkit
cd ~/.minimax-toolkit
./install.sh
```

### Windows (PowerShell)
```powershell
git clone https://github.com/FlapPearLabs/minimax-toolkit.git "$HOME\.minimax-toolkit"
cd "$HOME\.minimax-toolkit"
.\install.ps1
```

> 安装完成后，终端可直接使用 `minimax` 或缩写 `mmx`。
> 安装器会在落盘后**实际执行一次 `minimax --version` 自检**，装完但跑不起来会直接报错。

### 可选：安装即注册定时打卡

```bash
# 每日 09:05 自动打卡（台式机 / 常开机）
./install.sh --checkin-mode=calendar

# 开机或登录后自动打卡，并每 6 小时兜底（笔记本 / 常休眠）
./install.sh --checkin-mode=boot

# 不注册任何后台任务（默认）
./install.sh --checkin-mode=none
```

Windows 同理：`.\install.ps1 --checkin-mode=calendar`。

---

## 🛠️ 快速上手

### 1. 纳管已有账号或登录新账号
```bash
# 导入当前正在使用的凭据为 main
minimax login main

# 登录第二个账号（自动拉起默认浏览器点击确认即可）
minimax login dev_account

# 覆盖已存在账号 / 不自动打开浏览器（CI、远程终端）
minimax login dev_account --force --no-browser
```

### 2. 账号清单与状态概览
```bash
minimax list
```
终端将输出对齐的格式化表格：
```text
=== MiniMax 纳管账号清单 (2 个账号) ===
别名             用户标识                   凭据代数    Token有效期             今日状态
--------------------------------------------------------------------------------------------
*main            MiniMax用户 (50807072..)   Gen 24      2026-10-18 17:10:57     已签到✔
 dev_account     MiniMax用户 (50918231..)   Gen 1       2026-10-18 19:22:10     待领取
--------------------------------------------------------------------------------------------
* 标注星号为当前活跃全局账号。切换命令: minimax switch <alias>
```

```bash
minimax list --offline        # 不发起任何网络请求，纯本地快照
minimax list --json           # 机器可读输出（Agent / 脚本友好）
```

### 3. 一键原子切号
```bash
minimax switch dev_account
```
切换时首先把当前账号的最新代数与 Token 原子保存回 Profile，随后无感挂载目标账号，MiniMax 客户端下次启动或请求时即刻生效。

### 4. 签到打卡与积分查询
```bash
# 查看当前账号 7 天连签明细与今日积分
minimax status

# 单账号签到（默认当前活跃账号）
minimax checkin

# 指定账号 / 轮询纳管的全部账号
minimax checkin dev_account
minimax checkin --all
```

### 5. 注册系统级后台定时打卡服务
```bash
# 一键安装（默认 calendar 模式：每日 09:05）
minimax cron install

# 笔记本模式：开机/登录后执行 + 每 6 小时兜底
minimax cron install --mode boot

# 查看守护任务真实激活状态与最近执行时间
minimax cron status

# 卸载
minimax cron uninstall
```

| 平台 | 落盘位置 | 激活方式 |
| :--- | :--- | :--- |
| macOS | `~/Library/LaunchAgents/com.minimax.dailycheckin.plist` | `launchctl bootstrap gui/$UID` |
| Linux | `~/.config/systemd/user/minimax-checkin.{service,timer}` | `systemctl --user enable --now` |
| Windows | 计划任务 `MiniMaxDailyCheckin` / `MiniMaxBootCheckin` | `schtasks /create` |

---

## 📖 完整命令速查

| 命令 | 别名 | 功能说明 |
| :--- | :--- | :--- |
| `minimax login [alias]` | `mmx login` | 浏览器免扫码绑定新账号（`--force` / `--no-browser`） |
| `minimax switch [alias]` | `mmx switch` | 原子切换全局活跃账号（无参进交互菜单） |
| `minimax list [--offline] [--json]` | `mmx list` | 查看所有账号生命周期与今日打卡 |
| `minimax status [alias] [--json]` | `mmx status` | 查询 7 天连签周期与积分明细 |
| `minimax checkin [alias\|--all]` | `mmx checkin` | 执行今日签到领分（默认当前账号） |
| `minimax audit [alias\|--all]` | `mmx audit` | 健康体检与 Token 滚动无感续杯 |
| `minimax doctor [--json] [--offline]` | `mmx doctor` | 凭据 / 调度器 / 打卡新鲜度 / 网关全链路诊断 |
| `minimax cron <install\|uninstall\|status>` | `mmx cron` | 三平台定时任务管理（`--mode calendar\|boot`） |

### 退出码约定

| 退出码 | 含义 |
| :--- | :--- |
| `0` | 成功 |
| `1` | 业务失败（账号不存在、打卡失败、自愈失败、`doctor` 不健康） |
| `2` | 用法错误（未知命令、非法别名、缺参、非法模式） |
| `3` | 未预期内部错误（已捕获并脱敏，不打印 Python 回溯） |
| `4` | 守恒断言失败（分区计数与总数不一致） |

### 环境变量

| 变量 | 默认值 | 用途 |
| :--- | :--- | :--- |
| `MINIMAX_HOME` | `~/.minimax` | 沙盒/多实例数据目录 |
| `MINIMAX_ACCOUNT_BASE` | `https://account.minimax.cn` | OAuth 端点（可指向代理） |
| `MINIMAX_GATEWAY_BASE` | `https://agent.minimax.cn` | 业务网关（可指向代理或 mock） |
| `MINIMAX_NO_BROWSER` | 未设置 | 设为 `1` 时登录不自动打开浏览器 |
| `MINIMAX_DEBUG` | 未设置 | 设为 `1` 时内部错误额外打印回溯（仅排障用） |

详细协议分析与架构设计可参阅 [docs/architecture.md](docs/architecture.md) 与 [docs/command-reference.md](docs/command-reference.md)。

---

## 🛡️ 架构与安全承诺

1. **Zero-PII & Zero-Leak**：全仓库不含开发者私人路径与真实凭据，CI 对 macOS / Linux / Windows 用户目录、真实 `mmoat_/mmort_` Token、JWT、手机号做硬门禁扫描。
2. **纯标准库零外溢**：仅依赖 Python 3 标准库，不引入任何第三方包，杜绝依赖供应链投毒与版本漂移。
3. **原子落盘与 0600 权限**：凭据先写临时文件、`fsync` 后再 `os.replace`，POSIX 下强制 `0600`。
4. **原地自噬防御**：安装器通过 `os.path.samefile` 物理比对，源码目录与目标目录相同时绝不误删。
5. **异常边界收敛**：任何命令抛出未预期异常都会转成脱敏的单行错误 + 稳定退出码，不会把 Python 回溯灌进定时任务日志。

---

## ✅ 如何验证它真的在工作

```bash
minimax doctor            # 人类可读诊断
minimax doctor --json     # CI / 监控可直接断言 healthy
minimax cron status       # 调度器是否真的被系统激活
```

`doctor` 会读取 `~/.minimax/state.json` 中最近一次打卡时间：**超过 36 小时未成功打卡直接判 fail**，专治「任务装上了但静默失败好几天没人发现」。

本地回归：
```bash
python3 -m unittest discover -s tests -v
```

测试覆盖三类证据：

1. **纯单元**：PKCE S256、网关加签、时区、路径穿越、原子写权限。
2. **并发/进程级**：同线程可重入、跨线程互斥、真实子进程抢锁超时。
3. **端到端**：`tests/test_e2e_mock_gateway.py` 拉起本地 mock 网关，跑通
   `login → list → switch → checkin → claim → audit → doctor → cron status`，
   并由 mock 服务端**复算 `yy` 与 `x-signature`** 校验签名正确性。

---

## 📄 开源许可证

本项目基于 [MIT 许可证](LICENSE) 发布。
Copyright © 2026 [FlapPearLabs](https://github.com/FlapPearLabs). All rights reserved.
