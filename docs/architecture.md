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
   Code + S256 PKCE    SingleFlightLock    x-signature + yy
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────────┐┌──────────────────┐┌──────────────────┐
│ account.minimax  ││  auth_profiles/  ││ agent.minimax.cn │
│ OAuth 2.0 端点   ││  持久化凭据目录   ││ 业务网关 API     │
└──────────────────┘└──────────────────┘└──────────────────┘
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
   - CLI 自动打开 `verification_uri_complete`。用户仅需在网页端点击“确认授权”，无需繁琐手机扫码或验证码中转。
4. **轮询拉取授权令牌**:
   - `POST https://account.minimax.cn/oauth2/token`
   - 参数:
     - `grant_type`: `urn:ietf:params:oauth:grant-type:device_code`
     - `device_code`: 设备识别码
     - `client_id`: `mcode-public`
     - `code_verifier`: 客户端持有的原始高熵密钥
   - 返回: `access_token` (`mmoat_...`), `refresh_token` (`mmort_...`), `expires_in`。

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
   $$yy = \text{MD5}(\text{URLEncode}(PathWithQuery) + \text{"\_"} + \text{BodyString} + \text{MD5}(t_{ms}) + \text{"ooui"})$$

网关在接收到请求时会从物理层核验 $x\_signature$ 与 $yy$，并在请求头附带 `Authorization: Bearer <mmoat_token>` 完成双重校验。

---

## 4. 凭据拓扑与跨平台文件系统规范

### 4.1 官方客户端凭据落盘拓扑
- **macOS / Linux**: `~/.minimax/auth/prod/cn/mcode-public/auth.json`
- **Windows**: `%USERPROFILE%\.minimax\auth\prod\cn\mcode-public\auth.json`

### 4.2 Multi-Account 档案存储拓扑
MiniMax Toolkit 采用外置无侵入的档案目录架构：
- 档案持久化路径: `~/.minimax/auth_profiles/<alias>.json`
- 全局排他锁: `~/.minimax/auth/token_refresh.lock`
- 打卡审计日志: `~/.minimax/logs/checkin.log`

---

## 5. 工程防御与核心硬准则落地

本工具在设计之初吸取了大量系统级工程教训（避免踩坑）：

### 5.1 换号前同步防回滚 (Sync-before-Switch)
- **风险**: 活跃进程在使用期间会自动轮换 Token 并递增代数（Generation）。若直接切换覆盖，会导致旧 profile 中的陈旧 Token 覆写最新状态，引发 Token 失效。
- **解法**: `cmd_switch` 执行前，首先原子核对当前 `auth.json` 的别名与代数，无感同步刷回对应 profile，再将目标账号原子挂载至活跃路径。

### 5.2 跨平台单飞文件排他锁 (Single-Flight Lock)
- **风险**: 当定时任务、后台刷新进程与终端 CLI 并发触发时，多次使用同一个 `refresh_token` 会触发 OAuth 服务端的重放风控导致整号登出。
- **解法**: 通过 `SingleFlightFileLock`（macOS/Linux 下 `fcntl.flock`，Windows 下 `msvcrt.locking`）实施物理级排他锁，并发进程串行化刷新。

### 5.3 原地执行自噬防御 (Anti-Self-Destruction)
- **风险**: 用户在目标目录原地克隆或源码与安装目标指向同一物理路径时，粗暴的删除重建会导致自身代码被抹除抛出 `FileNotFoundError`。
- **解法**: 安装器通过 `os.path.samefile` 与绝对真实路径比对，断言一致时自动跳过复制，保证源码毫发无损。

### 5.4 数学守恒对账硬断言 (Conservation Law Invariant)
- **准则**: 批量打卡与统计逻辑严禁单点放行，必须验证全局数学守恒：
  $$\text{Total} \equiv \text{Success} + \text{Failed} \equiv \text{Claimed} + \text{AlreadyClaimed} + \text{Failed}$$
  只要有一条数据在计算中漏计或双重计数，系统立刻抛出物理异常阻断。
