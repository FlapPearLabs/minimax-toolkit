# MiniMax Toolkit 命令行完整参考手册 (Command Reference)

> **项目名称**: MiniMax Toolkit (`minimax` CLI)  
> **开源地址**: `https://github.com/FlapPearLabs/minimax-toolkit`

---

## 常用命令一览

| 主命令 | 快捷别名 | 说明 |
| :--- | :--- | :--- |
| `minimax login [alias]` | `mmx login`, `mmx-login` | 拉起浏览器完成 RFC 8628 设备授权并纳管新账号 |
| `minimax switch [alias]` | `mmx switch`, `mmx-switch` | 原子切换当前活跃账号（支持无参交互式选择） |
| `minimax list` | `mmx list`, `mmx-list`, `mmx ls` | 查看已纳管账号清单、Token 剩余寿命与今日打卡状态 |
| `minimax status [alias]` | `mmx status`, `mmx-status` | 查看当前或指定账号的 7 天连签明细与积分流水 |
| `minimax checkin [--all]` | `mmx checkin`, `mmx-checkin` | 执行签到领取每日积分（默认当前号，`--all` 批量打卡） |
| `minimax audit [--all]` | `mmx audit`, `mmx-audit` | 全面体检与 Token 滚动无感续杯（Rolling Refresh） |
| `minimax doctor` | `mmx doctor`, `mmx-doctor` | 检查本地运行环境、网关连通性与活跃挂载态 |
| `minimax cron <action>` | `mmx cron`, `mmx-cron` | 安装/卸载系统常驻定时任务（macOS / Linux / Windows） |

---

## 详细命令剖析

### 1. `minimax login [alias]`
- **功能**: 生成高熵 PKCE 密钥对，向 MiniMax 申请 Device Code，并在系统默认浏览器中打开授权页。
- **参数**:
  - `alias` (可选): 指定要保存的账号别名，默认使用 `account_N` 自动递增。
- **示例**:
  ```bash
  minimax login personal
  minimax login work
  ```

### 2. `minimax switch [alias]`
- **功能**: 
  1. 自动执行 **Sync-before-Switch**，将当前生效中的凭据（含最新 Token 与代数）刷回原账号 Profile。
  2. 原子将目标 Profile 写入官方客户端识别的 `~/.minimax/auth/.../auth.json`。
- **参数**:
  - `alias` (可选): 目标账号别名。若不填，CLI 会展示当前纳管的全部账号供用户选择。
- **示例**:
  ```bash
  minimax switch personal
  # 或者交互式菜单
  minimax switch
  ```

### 3. `minimax list`
- **功能**: 以优雅的表格列出所有纳管账号，展示别名、UID、Token 过期时间倒计时、凭据代数以及今日打卡状态（已签到/未签到）。活跃账号前附带 `*` 标识。
- **示例**:
  ```bash
  minimax list
  ```

### 4. `minimax status [alias]`
- **功能**: 查询连签周期进度（如 `Scene 2 (Day 6 / 7)`）、今日应得积分及 7 天周期内每一天的打卡状态。
- **示例**:
  ```bash
  minimax status
  minimax status personal
  ```

### 5. `minimax checkin [--all]`
- **功能**: 
  - 默认调用当前活跃账号执行签到。
  - 传入 `--all` 时，轮询纳管的全部 3~4 个账号，依次无感切号并调用 Matrix Gateway 签到接口，全量完成后原位复原此前活跃账号。
  - 遵循**幂等性**：若当日已签到，跳过 claim 领分，不产生重复无用请求。
- **示例**:
  ```bash
  minimax checkin
  minimax checkin --all
  ```

### 6. `minimax cron [install|uninstall|status]`
- **功能**: 系统级定时打卡服务管理。
  - **macOS**: 注册 `~/Library/LaunchAgents/com.minimax.dailycheckin.plist`，每日 09:05 自动唤醒执行。
  - **Linux**: 注册 `~/.config/systemd/user/minimax-checkin.timer`。
  - **Windows**: 注册 Windows Task Scheduler 计划任务。
- **示例**:
  ```bash
  minimax cron install
  minimax cron status
  minimax cron uninstall
  ```

### 7. `minimax doctor`
- **功能**: 输出白盒化物理自检报告，检查 Python 运行时、用户目录、已纳管账号数、活跃凭据路径、定时任务激活态以及网关探针 HTTP 状态。
- **示例**:
  ```bash
  minimax doctor
  ```
