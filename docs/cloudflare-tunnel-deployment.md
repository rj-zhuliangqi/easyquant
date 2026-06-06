# Cloudflare Tunnel 部署记录 — easyquant.vip

> 日期：2026-06-06
> 项目：easyquant（板块资金监控面板）
> 服务：FastAPI + Vue 3，运行在 `127.0.0.1:8010`
> 机器：macOS (Apple Silicon arm64)，常开，NAT 后无公网 IP

---

## 一、整体架构

```
用户浏览器 → https://easyquant.vip → Cloudflare 边缘节点 → Cloudflare Tunnel → 本地 Mac 127.0.0.1:8010
```

- 无需公网 IP、无需端口转发、无需 VPS
- Cloudflare 提供 TLS + CNAME 扁平化
- Tunnel 出站连接，不暴露本地端口

---

## 二、前置条件

| 条件 | 说明 |
|------|------|
| Cloudflare 账号 | 免费注册 dash.cloudflare.com |
| 域名 | 阿里云购买 `easyquant.vip`，NS 改为 Cloudflare |
| 本地服务 | FastAPI 运行在 `127.0.0.1:8010`（绑定 127.0.0.1 不要改 0.0.0.0） |

---

## 三、步骤详解

### 3.1 购买域名 & 配置 NS

1. **阿里云购买域名**：easyquant.vip（支付宝支付，¥1 首年）
2. **Cloudflare 添加域名**：登录 dash.cloudflare.com → Add a site → 输入 `easyquant.vip` → 选 Free 计划
3. **Cloudflare 分配 NS**：得到两个 NS 地址，例如：
   ```
   plato.ns.cloudflare.com
   sandra.ns.cloudflare.com
   ```
4. **阿里云修改 NS**：阿里云控制台 → 域名管理 → DNS 修改 → 替换为 Cloudflare 的 NS
5. **等待生效**：Cloudflare 面板显示 **Active** 即可（通常几分钟到几小时）

> ⚠️ NS 生效前，`cloudflared tunnel route dns` 创建的 CNAME 记录无法被解析。
> 验证方法：`dig easyquant.vip @1.1.1.1 +short`，返回 Cloudflare IP 即表示生效。

### 3.2 安装 cloudflared

macOS (Apple Silicon) 直接从 GitHub 下载很慢（被墙限速），推荐用 npm 包安装：

```bash
# 安装 npm 版 cloudflared（会自动下载二进制）
npm install -g cloudflared

# 等待 postinstall 完成后，二进制在此路径：
# /Users/jwkj/.hermes/node/lib/node_modules/cloudflared/bin/cloudflared

# 复制到用户 bin 目录
cp /Users/jwkj/.hermes/node/lib/node_modules/cloudflared/bin/cloudflared /Users/jwkj/.local/bin/cloudflared
chmod +x /Users/jwkj/.local/bin/cloudflared

# 清除 macOS 隔离属性（否则会被 macOS 杀掉，exit code 137）
xattr -cr /Users/jwkj/.local/bin/cloudflared

# 验证
/Users/jwkj/.local/bin/cloudflared version
# 输出: cloudflared version 2026.5.2
```

> **踩坑记录**：
> - GitHub 直接下载 `cloudflared-darwin-arm64.tgz` 在国内极慢（18MB 下了 2 分钟还没完）
> - `pkg.cloudflare.com` 的二进制链接返回 404
> - npm 安装的二进制有 macOS `com.apple.provenance` 扩展属性，运行会被 SIGKILL（exit 137），必须 `xattr -cr` 清除
> - Homebrew 未安装，`/opt/homebrew/bin/brew` 不存在
> - `sudo cp` 到 `/usr/local/bin/` 需要密码，改用 `~/.local/bin/` 更方便

### 3.3 授权 cloudflared

```bash
/Users/jwkj/.local/bin/cloudflared tunnel login
```

- 自动打开浏览器，选择 `easyquant.vip` 域名授权
- 授权成功后凭证保存到 `~/.cloudflared/cert.pem`
- 输出：`You have successfully logged in.`

### 3.4 创建 Tunnel

```bash
/Users/jwkj/.local/bin/cloudflared tunnel create easyquant
```

输出：
```
Tunnel credentials written to /Users/jwkj/.cloudflared/0a40446d-2c4a-4372-8255-5119163a1a25.json
Created tunnel easyquant with id 0a40446d-2c4a-4372-8255-5119163a1a25
```

> 记录 Tunnel ID：`0a40446d-2c4a-4372-8255-5119163a1a25`

### 3.5 创建配置文件

文件路径：`~/.cloudflared/config.yml`

```yaml
tunnel: 0a40446d-2c4a-4372-8255-5119163a1a25
credentials-file: /Users/jwkj/.cloudflared/0a40446d-2c4a-4372-8255-5119163a1a25.json

ingress:
  - hostname: easyquant.vip
    service: http://127.0.0.1:8010
  - hostname: www.easyquant.vip
    service: http://127.0.0.1:8010
  - service: http_status:404
```

要点：
- `ingress` 规则从上到下匹配，最后一条必须是 catch-all
- `service` 指向本地 FastAPI 地址
- 支持 `easyquant.vip` 和 `www.easyquant.vip` 两个域名

验证配置：
```bash
/Users/jwkj/.local/bin/cloudflared tunnel ingress validate
# 输出: OK
```

### 3.6 绑定 DNS

```bash
# 根域名
/Users/jwkj/.local/bin/cloudflared tunnel route dns easyquant easyquant.vip
# 输出: Added CNAME easyquant.vip which will route to this tunnel

# www 子域名
/Users/jwkj/.local/bin/cloudflared tunnel route dns easyquant www.easyquant.vip
# 输出: Added CNAME www.easyquant.vip which will route to this tunnel
```

这会在 Cloudflare DNS 中自动创建 CNAME 记录，指向 `<TUNNEL_ID>.cfargotunnel.com`，橙色云朵（Proxy）默认开启。

验证：
```bash
dig easyquant.vip @1.1.1.1 +short
# 输出: 104.21.83.3  172.67.166.116  （Cloudflare 的 anycast IP）
```

### 3.7 测试 Tunnel

```bash
# 1. 确保 FastAPI 在运行
curl -s http://127.0.0.1:8010/api/status
# 应返回 JSON

# 2. 前台启动 tunnel 测试
/Users/jwkj/.local/bin/cloudflared tunnel run easyquant
# 观察 Registered tunnel connection 日志，4 个连接都成功即可

# 3. 另一个终端测试公网访问
curl -s --max-time 15 https://easyquant.vip/api/status
# 应返回相同的 JSON

# 4. Ctrl+C 停止测试
```

### 3.8 设置开机自启（launchd）

#### FastAPI 开机自启

文件：`~/Library/LaunchAgents/com.easyquant.server.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.easyquant.server</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/jwkj/.local/bin/uv</string>
        <string>run</string>
        <string>uvicorn</string>
        <string>app.main:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8010</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/jwkj/easyquant</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/jwkj/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/jwkj/easyquant/data/uvicorn-launchd.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/jwkj/easyquant/data/uvicorn-launchd.error.log</string>
</dict>
</plist>
```

要点：
- `uv` 路径是 `/Users/jwkj/.local/bin/uv`（不是 `/opt/homebrew/bin/`）
- 不使用 `start.sh`，因为其 PID 管理与 launchd 冲突
- `KeepAlive: SuccessfulExit: false` 实现崩溃自动重启
- uvicorn 绑定 `127.0.0.1`，**不要改为 0.0.0.0**

#### Cloudflared Tunnel 开机自启

文件：`~/Library/LaunchAgents/com.cloudflare.cloudflared.easyquant.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.cloudflared.easyquant</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/jwkj/.local/bin/cloudflared</string>
        <string>tunnel</string>
        <string>--config</string>
        <string>/Users/jwkj/.cloudflared/config.yml</string>
        <string>run</string>
        <string>easyquant</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/jwkj/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/jwkj/easyquant/data/cloudflared.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/jwkj/easyquant/data/cloudflared.error.log</string>
</dict>
</plist>
```

要点：
- `cloudflared` 路径是 `/Users/jwkj/.local/bin/cloudflared`（不是 `/opt/homebrew/bin/`）
- 如果换了 Homebrew 安装，路径需改为 `/opt/homebrew/bin/cloudflared`

#### 加载 & 管理命令

```bash
# 加载服务（开机自启）
launchctl load ~/Library/LaunchAgents/com.easyquant.server.plist
launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.easyquant.plist

# 卸载服务（取消开机自启）
launchctl unload ~/Library/LaunchAgents/com.easyquant.server.plist
launchctl unload ~/Library/LaunchAgents/com.cloudflare.cloudflared.easyquant.plist

# 查看状态
launchctl list | grep -E "easyquant|cloudflared"

# 查看日志
tail -20 /Users/jwkj/easyquant/data/cloudflared.error.log
tail -20 /Users/jwkj/easyquant/data/uvicorn-launchd.error.log
```

---

## 四、文件清单

| 文件 | 用途 |
|------|------|
| `~/.cloudflared/config.yml` | Tunnel 配置（Tunnel ID、域名、后端服务） |
| `~/.cloudflared/cert.pem` | Cloudflare 授权凭证（登录时生成） |
| `~/.cloudflared/0a40446d-2c4a-4372-8255-5119163a1a25.json` | Tunnel 凭证（创建时生成） |
| `~/Library/LaunchAgents/com.easyquant.server.plist` | FastAPI 开机自启 |
| `~/Library/LaunchAgents/com.cloudflare.cloudflared.easyquant.plist` | Tunnel 开机自启 |
| `/Users/jwkj/.local/bin/cloudflared` | cloudflared 二进制 |

---

## 五、验证清单

```bash
# 1. 本地服务
curl -s http://127.0.0.1:8010/api/status

# 2. DNS 解析
dig easyquant.vip @1.1.1.1 +short
# 期望: Cloudflare IP (如 104.21.x.x)

# 3. 公网 HTTPS
curl -s https://easyquant.vip/api/status

# 4. launchd 服务状态
launchctl list | grep -E "easyquant|cloudflared"

# 5. 手机 4G 访问 https://easyquant.vip

# 6. Cloudflare 面板 → Tunnels → 状态应为 Up
```

---

## 六、踩坑记录

### 问题 1：GitHub 下载极慢

- 现象：`curl -L` 下载 `cloudflared-darwin-arm64.tgz` 速度 ~25KB/s，2 分钟只下了 2MB
- 解决：通过 `npm install -g cloudflared` 安装，npm 包内含二进制下载逻辑

### 问题 2：cloudflared 被 macOS SIGKILL (exit 137)

- 现象：从 npm 包解压的二进制运行即被杀，exit code 137
- 原因：macOS 对非签名下载文件添加 `com.apple.provenance` 扩展属性，Gatekeeper 拦截
- 解决：`xattr -cr /Users/jwkj/.local/bin/cloudflared`

### 问题 3：DNS CNAME 不生效

- 现象：`cloudflared tunnel route dns` 显示成功，但 `dig` 查不到记录
- 原因：阿里云 NS 还没改完 / Cloudflare 还没验证 NS 变更
- 解决：等待 Cloudflare 面板显示 Active，NS 变更通常几分钟到几小时生效

### 问题 4：根域名 CNAME

- 现象：根域名 (`easyquant.vip`) 的 CNAME 需要特殊处理
- 说明：Cloudflare 支持 CNAME 扁平化（CNAME Flattening），根域名 CNAME 会自动转为 A 记录返回 IP，无需特殊配置

### 问题 5：sudo 无法使用

- 现象：`sudo cp` 需要 TTY 密码输入，Claude Code 环境无法交互
- 解决：使用 `~/.local/bin/` 替代 `/usr/local/bin/`

---

## 七、安全建议（待实施）

当前应用无认证，外网可直接访问。建议配置 Cloudflare Zero Trust Access：

1. 登录 [one.dash.cloudflare.com](https://one.dash.cloudflare.com)
2. Access → Applications → Add an application → Self-hosted
3. 域名填 `easyquant.vip` 和 `www.easyquant.vip`
4. 策略选 **One-time PIN**，填你的邮箱
5. 免费，支持最多 50 个用户

效果：访问 `https://easyquant.vip` 时需邮箱验证码登录，零代码改动。

---

## 八、常用运维命令

```bash
# 手动启动 tunnel（调试用）
/Users/jwkj/.local/bin/cloudflared tunnel run easyquant

# 查看 tunnel 列表
/Users/jwkj/.local/bin/cloudflared tunnel list

# 查看 tunnel 详情
/Users/jwkj/.local/bin/cloudflared tunnel info easyquant

# 删除 tunnel（慎用）
/Users/jwkj/.local/bin/cloudflared tunnel delete easyquant

# 重启 FastAPI（通过 launchd）
launchctl kickstart -k gui/$(id -u)/com.easyquant.server

# 重启 Tunnel
launchctl kickstart -k gui/$(id -u)/com.cloudflare.cloudflared.easyquant

# 保护凭证文件
chmod 600 ~/.cloudflared/*.json ~/.cloudflared/cert.pem
```
