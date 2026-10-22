# MiniMax Toolkit 架构与协议底层逆向设计规范

> **仓库真源**: `https://github.com/FlapPearLabs/minimax-toolkit`
> **设计主体**: FlapPearLabs (AI-native systems builder)
> **定位**: 零依赖、纯 Python 3 标准库的多账号管理与无感自愈签到引擎

---

## 1. 架构全景图

MiniMax Toolkit 是一套开箱即用的轻量化凭据调度组件，旨在替代笨重的高内存 Electron UI，通过标准协议与物理自愈机制直接与 MiniMax 认证及业务网关对话。

```
┌───────────────────────────────────────────────────────────────┐
│                     minimax CLI 调度中心                       │
└───────┬───────────────────┬───────────────────┬───────────────┘
        │                   │                   │
   [免扫码登录]         [切号与同步]         [自动打卡/巡检]
        │                   │                   │
  RFC 8628 Device     Sync-before-Switch   Matrix Gateway
   Code + S256 PKCE    可重入单飞锁        x-signature + yy
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────────┐┌──────────────────┐┌──────────────────┐
│ account.minimax  ││  auth_profiles/  ││ agent.minimax.cn │
│ OAuth 2.0 端点   ││  持久化凭据目录   ││ 业务网关 API     │
└──────────────────┘└──────────────────┘└──────────────────┘
        │                   │                   │
        └──────────┬────────┴─────────┬─────────┘
                   ▼                  ▼
          state.json (运行账本)   系统调度器
          last_run/last_success   launchd / systemd / schtasks
```

---

## 2. 核心认证协议逆向机理

### 2.1 RFC 8628 免扫码设备授权码流 (Device Authorization Grant)

MiniMax Code 官方客户端（内部研发代号 `Mavis`）在底层采用 **RFC 8628 + RFC 7636 (S256 PKCE)** 协议：

1. **生成高熵 Code Verifier 与 S256 Challenge**:
   - `code_verifier`: 32 字节高熵随机串经 URL-safe Base64 编码（剔除 `=` 填充）。
   - `code_challenge`: $\text{Base64URL}(\text{SHA-256}(code\_verifier))$。
2. **请求设备验证码**:
   - `POST https://account.minimax.cn/oauth2/device/code`
   - 参数:
     - `client_id`: `mcode-public`
     - `scope`: `agent.default`
     - `audience`: `agent-backend`
     - `code_challenge`: 计算出的 PKCE Challenge
     - `code_challenge_method`: `S256`
   - 返回: `device_code`, `user_code`, `verification_uri_complete`, `interval`。
3. **拉起浏览器免输入绑定**:
   - CLI 自动打开 `verification_uri_complete`。用户仅需在网页端点击“确认授权”。
4. **轮询拉取授权令牌**:
   - `POST https://account.minimax.cn/oauth2/token`
   - 参数:
     - `grant_type`: `urn:ietf:params:oauth:grant-type:device_code`
     - `device_code`: 设备识别码
     - `client_id`: `mcode-public`
     - `code_verifier`: 客户端持有的原始高熵密钥
   - 返回: `access_token` (`mmoat_...`), `refresh_token` (`mmort_...`), `expires_in`。

> 生产环境的 `mmoat_` 是**不透明字符串**而非 JWT，因此不要把 UID 解析建立在 token 结构上；
> 若服务端在响应中返回 `user_id`，才写入本地档案。缺失时网关按 Bearer 凭据鉴权。

---

## 3. 业务网关逆向加签机制 (Matrix Gateway)

MiniMax 签到与资产接口归属于 `https://agent.minimax.cn`，请求受到请求级防篡改加签校验。

### 3.1 签名因子定义
- 静态加签盐值: `I*7Cf%WZ#S&%1RlZJ&C2`
- 验签混淆后缀: `ooui`
- 业务应用标识: `app_id = 3001`

### 3.2 加签算法形式化
1. **时间戳锚定**: 提取 UTC Epoch 秒数 $t_{sec}$ 与毫秒数 $t_{ms}$。
2. **请求头签名 (`x-signature`)**:
   $$x\_signature = \text{MD5}(t_{sec} + \text{"I*7Cf%WZ#S&%1RlZJ&C2"} + \text{BodyString})$$
3. **URL 参数验签 (`yy`)**:
   $$yy = \text{MD5}(\text{URLEncode}(PathWithQuery) + \text{"\_"} + \text{BodyString}_{yy} + \text{MD5}(t_{ms}) + \text{"ooui"})$$

网关在接收到请求时会从物理层核验 $x\_signature$ 与 $yy$，并在请求头附带 `Authorization: Bearer <mmoat_token>` 完成双重校验。

> **对齐细节**：无 body 的 GET 请求里，`BodyString`（用于 `x-signature`）为空串，而 `BodyString_yy`（用于 `yy`）取 `{}`；
> 有 body 时两者都取实际 JSON 串（key 排序、`separators=(",",":")`）。
> `tests/test_e2e_mock_gateway.py` 在服务端按同一算法复算两个签名，任何漂移都会红灯。

---

## 4. 凭据拓扑与跨平台文件系统规范

### 4.1 官方客户端凭据落盘拓扑
- **macOS / Linux**: `~/.minimax/auth/prod/cn/mcode-public/auth.json`
- **Windows**: `%USERPROFILE%\.minimax\auth\prod\cn\mcode-public\auth.json`

### 4.2 本工具的数据拓扑
- 档案持久化路径: `~/.minimax/auth_profiles/<alias>.json`
- 全局排他锁: `~/.minimax/auth/token_refresh.lock`
- 打卡审计日志: `~/.minimax/logs/checkin.log`（只由 `log()` 写入）
- 调度器进程日志: `~/.minimax/logs/scheduler.{out,err}.log`（由 launchd/systemd 重定向）
- 运行账本: `~/.minimax/state.json`（`last_run_at` / `last_success_at` / `last_run_result` / `last_run_summary` / `last_refresh_at`）

> 日志分轨是硬性设计：审计日志与进程 stdout 若指向同一文件，每条日志会被写两遍，
> 且未捕获回溯会污染对账记录。

### 4.3 环境变量覆盖
`MINIMAX_HOME` / `MINIMAX_ACCOUNT_BASE` / `MINIMAX_GATEWAY_BASE` 允许把整套数据目录与端点指向沙盒或代理，
这也是 E2E 测试能在不接触真实账号的前提下跑通全链路的前提。

---

## 5. 工程防御与核心硬准则落地

### 5.1 换号前同步防回滚 (Sync-before-Switch)
- **风险**: 活跃进程在使用期间会自动轮换 Token 并递增代数（Generation）。若直接切换覆盖，会导致旧 profile 中的陈旧 Token 覆写最新状态，引发 Token 失效。
- **解法**: `cmd_switch` 持锁执行，首先原子核对当前 `auth.json` 的别名与代数，无感同步刷回对应 profile，再将目标账号原子挂载至活跃路径。

### 5.2 同线程可重入的单飞文件排他锁
- **风险 A（并发）**: 定时任务、后台刷新与终端 CLI 并发触发时，多次使用同一个 `refresh_token` 会触发 OAuth 服务端重放风控导致整号登出。
- **风险 B（自锁）**: `flock` / `msvcrt` 以「打开的文件描述」为单位加锁 —— 同一进程内二次 `open()` 再加锁**同样会阻塞**。
  早期实现里 `switch` 持锁后又调用同样加锁的 `sync_active_to_profile()` / `refresh_token_if_needed()`，
  结果每次切号都卡满 30 秒超时并抛 `TimeoutError`。
- **解法**: 锁对象维持「文件路径 → (持有线程, 深度)」注册表：
  - 同一线程嵌套进入 → 深度计数，不再触碰操作系统锁（不再自锁死）；
  - 不同线程 / 不同进程 → 仍走 `flock` / `msvcrt.locking` 真实排他，超时严格抛错。

### 5.3 原地执行自噬防御 (Anti-Self-Destruction)
- **风险**: 用户在目标目录原地克隆或源码与安装目标指向同一物理路径时，粗暴的删除重建会导致自身代码被抹除。
- **解法**: 安装器通过 `os.path.samefile` 与绝对真实路径比对，断言一致时跳过复制，保证源码毫发无损。

### 5.4 数学守恒对账硬断言 (Conservation Law Invariant)
- **准则**: 批量打卡统计严禁单点放行，必须验证全局数学守恒：
  $$\text{Total} \equiv \text{Claimed} + \text{AlreadyClaimed} + \text{Idle} + \text{Failed}$$
  只要有一条数据漏计或双重计数，系统立刻以退出码 `4` 阻断，并在 `state.json` 标记 `invariant_violation`。

### 5.5 打卡新鲜度控制面 (Freshness Control Plane)
- **风险**: 定时任务「装上了」不等于「真的在跑」。真实事故中，任务连续 3 天因网络错误静默失败，
  只在日志里堆叠回溯，无人发现。
- **解法**: 每次 checkin 结束写入 `state.json`；`doctor` 据此判定：
  - 最近成功打卡 > 36h → `fail`（退出码 1）
  - 最近执行 > 26h → `warn`（调度器可能没在跑）
  - 同时核对调度器**真实激活态**（`launchctl list` / `systemctl --user is-active` / `schtasks /query`），
    而不是只看配置文件是否存在。

### 5.6 异常边界与退出码契约
- 所有命令的未预期异常都在 `main()` 统一收敛为脱敏单行错误 + 退出码 `3`；
  定时任务日志里永远不会出现 Python 回溯，也不会泄露 Token。
- 退出码语义固定：`0` 成功 / `1` 业务失败 / `2` 用法错误 / `3` 内部错误 / `4` 守恒失败，
  便于 cron、CI 与监控直接消费。

### 5.7 三平台调度器一等公民
- macOS: 生成 plist 后 `launchctl bootout`（按 label 清理历史加载）再 `bootstrap`，避免同名 label 重复加载失败。
- Linux: 生成 systemd user unit；`calendar` 带 `Persistent=true` 补偿休眠错过；无 `systemctl` 时降级为「写文件 + 提示手动激活」。
- Windows: `schtasks` 创建 `daily` / `onlogon` 任务，安装一种模式时清理另一种，避免重复打卡。
- 安装器与服务管理共用同一份实现：`install.py --checkin-mode=...` 实际调用 `minimax cron install`，
  杜绝两份代码各自漂移。
