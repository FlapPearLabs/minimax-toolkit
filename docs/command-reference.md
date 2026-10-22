# MiniMax Toolkit 命令行完整参考手册 (Command Reference)

> **项目名称**: MiniMax Toolkit (`minimax` CLI)
> **开源地址**: `https://github.com/FlapPearLabs/minimax-toolkit`
> **版本**: 0.2.0

---

## 常用命令一览

| 主命令 | 快捷别名 | 说明 |
| :--- | :--- | :--- |
| `minimax login [alias]` | `mmx login`, `mmx-login` | 拉起浏览器完成 RFC 8628 设备授权并纳管新账号 |
| `minimax switch [alias]` | `mmx switch`, `mmx-switch` | 原子切换当前活跃账号（支持无参交互式选择） |
| `minimax list` | `mmx list`, `mmx-list`, `mmx ls` | 查看已纳管账号清单、Token 剩余寿命与今日打卡状态 |
| `minimax status [alias]` | `mmx status`, `mmx-status` | 查看当前或指定账号的 7 天连签明细与积分流水 |
| `minimax checkin [alias\|--all]` | `mmx checkin`, `mmx-checkin` | 执行签到领取每日积分（默认当前账号） |
| `minimax audit [alias\|--all]` | `mmx audit`, `mmx-audit` | 全面体检与 Token 滚动无感续杯（Rolling Refresh） |
| `minimax doctor` | `mmx doctor`, `mmx-doctor` | 检查凭据、调度器、打卡新鲜度与网关连通性 |
| `minimax cron <action>` | `mmx cron`, `mmx-cron` | 安装/卸载/查看三平台系统级定时任务 |

全局选项：

```text
--offline / --no-network   跳过网络探测（list / doctor）
--json                     机器可读输出（list / status / doctor）
```

环境变量：

```text
MINIMAX_HOME            默认 ~/.minimax
MINIMAX_ACCOUNT_BASE    默认 https://account.minimax.cn
MINIMAX_GATEWAY_BASE    默认 https://agent.minimax.cn
MINIMAX_NO_BROWSER=1    登录时不自动打开浏览器
MINIMAX_DEBUG=1         内部错误额外打印回溯（仅排障）
```

退出码：`0` 成功 / `1` 业务失败 / `2` 用法错误 / `3` 未预期内部错误 / `4` 守恒断言失败。

---

## 详细命令剖析

### 1. `minimax login [alias] [--force] [--no-browser]`

- **功能**: 生成高熵 PKCE 密钥对，向 MiniMax 申请 Device Code，并在系统默认浏览器中打开授权页。
- **参数**:
  - `alias`（可选）: 账号别名。交互式终端下若留空则提示输入，默认建议下一个 `account_N`；非交互环境下自动生成 `account_N`。
  - `--force` / `-f`: 覆盖已存在的同名账号，不再询问。
  - `--no-browser`: 不自动拉起浏览器（远程终端 / CI 场景）。
- **行为**:
  - 轮询间隔遵循服务端 `interval`，遇到 `slow_down` 自动退避。
  - 首次登录时自动把该账号挂载为当前活跃账号。
  - 授权失败/拒绝/过期均返回稳定退出码，不打印回溯。
- **示例**:
  ```bash
  minimax login personal
  minimax login work --force
  minimax login ci_account --no-browser
  ```

### 2. `minimax switch [alias] [--yes]`

- **功能**:
  1. 持锁执行 **Sync-before-Switch**，把当前活跃凭据（最新 Token 与代数）刷回原账号 Profile。
  2. 目标 Token 若临近过期，锁内自动滚动续期。
  3. 原子将目标 Profile 写入官方客户端识别的 `~/.minimax/auth/prod/cn/mcode-public/auth.json`。
- **参数**:
  - `alias`（可选）: 目标账号别名。留空时进入交互式菜单。
  - `--yes` / `-y`: 跳过目标 Token 预刷新（批量脚本场景）。
- **非交互环境**: 未指定别名时直接返回用法错误（退出码 2），不会因 `EOFError` 崩溃。
- **示例**:
  ```bash
  minimax switch personal
  minimax switch            # 交互式菜单
  ```

### 3. `minimax list [--offline] [--json]`

- **功能**: 列出所有纳管账号：别名、脱敏 UID、凭据代数、Token 过期时间、今日打卡状态。活跃账号前带 `*`。
- **选项**:
  - `--offline`: 不发起任何网络请求，只读本地快照（离线/飞行模式）。
  - `--json`: 输出结构化 JSON（`current` / `count` / `accounts[]`）。
- **示例**:
  ```bash
  minimax list
  minimax list --offline
  minimax list --json | jq '.accounts[].status'
  ```

### 4. `minimax status [alias] [--json]`

- **功能**: 查询连签周期进度（如 `Scene 2 (Day 6 / 7)`）、今日应得积分与当前状态（未开始/待领取/已签到/已失效）。
- **示例**:
  ```bash
  minimax status
  minimax status personal
  minimax status --json
  ```

### 5. `minimax checkin [alias | --all]`

- **功能**:
  - 默认对**当前活跃账号**执行签到。
  - 传入 `alias` 对指定账号签到。
  - 传入 `--all` 轮询全部纳管账号。
  - 遵循**幂等性**：当日已签到则跳过 claim，不产生重复写请求。
  - 每轮结束写入 `~/.minimax/state.json`，并执行分区守恒断言：
    `total == claimed + already + idle + failed`。
- **退出码**: 全部成功 `0`；存在失败 `1`；守恒被破坏 `4`。
- **示例**:
  ```bash
  minimax checkin
  minimax checkin --all
  minimax checkin dev_account
  ```

### 6. `minimax audit [alias | --all]`

- **功能**: 逐个账号检查凭据完整性；Token 临近或已过期时在**单飞锁内**滚动续期，并把新 Token 同时写回 Profile 与活跃 `auth.json`。
- **退出码**: 全部健康 `0`；任一账号需要重新登录 `1`。
- **示例**:
  ```bash
  minimax audit
  minimax audit --all
  ```

### 7. `minimax cron <install|uninstall|status> [--mode calendar|boot]`

- **功能**: 系统级定时打卡服务管理（三平台一等公民）。

  | 平台 | 生成产物 | 激活命令 |
  | :--- | :--- | :--- |
  | macOS | `~/Library/LaunchAgents/com.minimax.dailycheckin.plist` | `launchctl bootstrap gui/$UID` |
  | Linux | `~/.config/systemd/user/minimax-checkin.service` + `.timer` | `systemctl --user enable --now` |
  | Windows | `MiniMaxDailyCheckin` / `MiniMaxBootCheckin` | `schtasks /create` |

- **模式**:
  - `calendar`（默认）: 每日 09:05 执行；systemd 带 `Persistent=true`，休眠错过会补跑。
  - `boot`: 开机/登录即执行；systemd 额外每 6 小时兜底。
  - 两种模式互斥安装，安装时会清理另一种模式的残留任务。
- **status**: 报告「是否安装 / 模式 / 是否被系统真正激活 / 最近一次执行时间」。已安装但未激活返回 `1`。
- **示例**:
  ```bash
  minimax cron install
  minimax cron install --mode boot
  minimax cron status
  minimax cron uninstall
  ```

### 8. `minimax doctor [--json] [--offline]`

- **功能**: 白盒化自检，逐项输出 `ok / warn / fail`：

  | 检查项 | 判定 |
  | :--- | :--- |
  | `python` | 是否 >= 3.8，失败的版本直接 fail |
  | `home` | `~/.minimax` 是否存在且可写 |
  | `profiles` | 纳管账号数量 |
  | `active_auth` | 活跃凭据是否挂载、代数、到期时间；已过期 warn |
  | `scheduler` | 三平台调度器是否安装且被系统激活 |
  | `last_checkin` | `state.json` 最近执行/成功时间；>36h 未成功 fail，>26h 未执行 warn |
  | `gateway` | 业务网关连通性（任何 HTTP 响应都算链路可达） |
  | `path` | `minimax` 是否已在 PATH 中 |

- **退出码**: 无 fail 项 `0`；存在 fail 项 `1`。可直接用于监控探针。
- **示例**:
  ```bash
  minimax doctor
  minimax doctor --json
  minimax doctor --offline
  ```
