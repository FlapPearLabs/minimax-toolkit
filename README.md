# MiniMax Toolkit (`minimax` CLI)

> **Zero-Dependency Multi-Account Manager & Automated Check-in Engine for MiniMax Code**  
> Developed & Maintained by [FlapPearLabs](https://github.com/FlapPearLabs)

[![CI & Zero-Leak Audit](https://github.com/FlapPearLabs/minimax-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/FlapPearLabs/minimax-toolkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-brightgreen.svg)]()

---

## 💡 为什么需要 MiniMax Toolkit？

MiniMax Code 官方客户端基于 Electron 框架，运行内存较高，且单机仅支持挂载单一登录凭据，不支持多账号便捷轮换。同时，每日签到积分是模型高频调用的重要免费额度来源。

**MiniMax Toolkit** 彻底剥离 UI 负担，以**零依赖、纯 Python 3 标准库**打造了一套开箱即用的底层凭据治理与自动化打卡套件：

- 🔄 **多账号无缝纳管**: 专为 3~4 个日常主力/备用账号设计，免去繁琐切换退出。
- ⚡ **RFC 8628 免扫码授权**: 基于 OAuth 2.0 Device Flow 与 S256 PKCE，CLI 一键拉起浏览器授权，无需手机反复扫码。
- 🛡️ **自愈防回滚机制 (Sync-before-Switch)**: 切号前自动对齐落盘最新 Token，彻底杜绝运行期刷新与 profile 回滚冲突。
- 🔒 **单飞文件排他锁 (Single-Flight Lock)**: 并发刷新排他保护，阻断 OAuth Refresh Token 重放风控。
- 🕒 **系统级原生无感签到**: 原生对接 macOS `launchd` / Linux `systemd` / Windows 计划任务，每日 09:05 纯静默自愈打卡。
- 📊 **全局数学守恒对账**: 批量打卡全流程注入严格守恒断言，确保结果绝对真实不可伪造。

---

## 🚀 极速安装

系统已预装 Python 3 即可无缝部署，无需任何第三方 pip 依赖：

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

---

## 🛠️ 快速上手

### 1. 纳管已有账号或登录新账号
```bash
# 导入当前正在使用的凭据为 main
minimax login main

# 登录第二个账号（自动拉起默认浏览器点击确认即可）
minimax login dev_account
```

### 2. 账号清单与状态概览
```bash
minimax list
```
终端将输出优雅的格式化表格：
```text
=== MiniMax 纳管账号清单 (2 个账号) ===
别名             用户标识                   凭据代数     Token有效期             今日状态          
--------------------------------------------------------------------------------
*main            MiniMax用户 (50807072..)   Gen 24       2026-10-18 17:10:57     已签到✔
 dev_account     MiniMax用户 (50918231..)   Gen 1        2026-10-18 19:22:10     未签到
--------------------------------------------------------------------------------
* 标注星号为当前活跃全局账号。切换命令: minimax switch <alias>
```

### 3. 一键原子切号
```bash
minimax switch dev_account
```
切换时将首先把当前账号的最新代数与 Token 原子保存回 Profile，随后无感挂载目标账号，MiniMax 客户端下次启动或请求时即刻生效。

### 4. 签到打卡与积分查询
```bash
# 查看当前账号 7 天连签明细与今日积分
minimax status

# 单账号签到
minimax checkin

# 轮询纳管的全部账号批量打卡（自动切号打卡并在完成后恢复现场）
minimax checkin --all
```

### 5. 注册系统级后台定时打卡服务
```bash
# 一键安装系统级守护服务（macOS 注册 LaunchAgent，Linux 注册 systemd timer）
minimax cron install

# 查看守护任务健康状态
minimax cron status
```

---

## 📖 完整命令速查

| 命令 | 别名 | 功能说明 |
| :--- | :--- | :--- |
| `minimax login [alias]` | `mmx login` | 浏览器免扫码绑定新账号 |
| `minimax switch [alias]` | `mmx switch` | 原子切换全局活跃账号 |
| `minimax list` | `mmx list` | 查看所有账号生命周期与今日打卡 |
| `minimax status [alias]` | `mmx status` | 查询 7 天连签周期与积分明细 |
| `minimax checkin [--all]` | `mmx checkin` | 执行今日签到领分（支持 `--all` 全量） |
| `minimax audit [--all]` | `mmx audit` | 健康体检与 Token 滚动无感续杯 |
| `minimax doctor` | `mmx doctor` | 运行时自检、环境诊断与物理网关探针 |
| `minimax cron <action>` | `mmx cron` | 定时任务管理 (`install` / `uninstall` / `status`) |

详细协议分析与架构设计可参阅 [docs/architecture.md](docs/architecture.md)。

---

## 🛡️ 架构与安全承诺

1. **Zero-PII & Zero-Leak**: 全仓库绝不包含任何开发者私人身份信息，跨平台路径全链路使用动态环境变量解析，100% 通过 CI 自动化安全扫描。
2. **纯标准库零外溢**: 仅依赖 Python 3 标准库（`urllib`, `hashlib`, `json`, `os`, `sys`），不引入任何外部第三方包，杜绝依赖供应链投毒与版本漂移。
3. **原地自噬防御 (Anti-Self-Destruction)**: 安装器严格实施路径指纹比对，源码目录与目标目录相同时平滑自适应，绝不发生误删。

---

## 📄 开源许可证

本项目基于 [MIT 许可证](LICENSE) 发布。  
Copyright © 2026 [FlapPearLabs](https://github.com/FlapPearLabs). All rights reserved.
