# 完整部署与使用手册

本文是 A股自选股智能分析系统（DSA）的端到端实战手册，覆盖本地启动、钉钉机器人接入、LLM / 数据源 / 通知 / Agent 配置、Linux 云服务器 Docker 部署、GitHub Actions 零成本部署、运维排障与安全实践。

阅读对象：第一次接触项目、要把服务真正跑起来（含钉钉对话、每日定时推送、Web 工作台）的使用者。

> 与其他文档的关系：项目定位和快速开始看 [README.md](../README.md)，配置字段字典与功能细节看 [full-guide.md](full-guide.md)，通知渠道逐项说明看 [notifications.md](notifications.md)，Bot 命令与平台适配看 [bot-command.md](bot-command.md)，LLM 服务商选择看 [LLM_CONFIG_GUIDE.md](LLM_CONFIG_GUIDE.md) 与 [llm-providers.md](llm-providers.md)，云端 WebUI 域名 / HTTPS 看 [deploy-webui-cloud.md](deploy-webui-cloud.md)。

---

## 0. 目录

1. [项目能做什么](#1-项目能做什么)
2. [三种部署方式总览](#2-三种部署方式总览)
3. [本地 Windows 部署](#3-本地-windows-部署)
4. [钉钉机器人接入](#4-钉钉机器人接入)
5. [LLM 大模型配置](#5-llm-大模型配置)
6. [数据源配置](#6-数据源配置)
7. [通知渠道配置](#7-通知渠道配置)
8. [Agent 智能对话](#8-agent-智能对话)
9. [Web 工作台](#9-web-工作台)
10. [Linux 云服务器 Docker 部署](#10-linux-云服务器-docker-部署)
11. [GitHub Actions 零成本部署](#11-github-actions-零成本部署)
12. [安全实践](#12-安全实践)
13. [运维排障](#13-运维排障)
14. [升级与维护](#14-升级与维护)
15. [附录：环境变量速查](#15-附录环境变量速查)

---

## 1. 项目能做什么

| 能力 | 说明 | 入口 |
|---|---|---|
| 每日自动分析 | 工作日 18:00 跑自选股 + 大盘复盘，推送到企微 / 飞书 / 钉钉 / TG / 邮箱 | `--schedule` 模式 |
| AI 决策报告 | 核心结论、评分、趋势、买卖点、风险警报、催化因素 | 单股报告 |
| 多市场数据 | A 股、港股、美股、ETF；行情、K 线、技术指标、资金流、筹码、新闻 | 内置多源 fallback |
| 多源搜索 | Bocha / Tavily / Brave / SerpAPI / MiniMax / SearXNG / Anspire | 同上 |
| Web / 桌面 | 手动分析、历史报告、回测、持仓、智能导入、主题切换 | Web 工作台 |
| 钉钉 / 飞书 Bot | 私聊 / 群消息触发对话问股、自然语言路由 | Bot 模块 |
| 策略问股 | 20 种内置策略（缠论、波浪、均线、龙头、热点、多因子、行业轮动、PEAD 等） | Web `/chat` + Bot `/ask` |
| 回测 | 对历史分析做 N 日收益评估，验证报告质量 | Web 回测页 |

主流程：抓取数据 → 技术分析 + 新闻检索 → LLM 分析 → 生成报告 → 通知推送。

---

## 2. 三种部署方式总览

| 方式 | 一次性成本 | 运行成本 | 7×24 | 推荐场景 |
|---|---|---|---|---|
| **本地 Windows / macOS** | 0 | 电费 | 仅机器在线时 | 个人试用、调试 |
| **Linux 云服务器 + Docker** | 1C1G ≈ ¥30/月 | 服务器费 | 是 | 钉钉 bot 永远在线、定时推送 |
| **GitHub Actions** | 0 | 0（公共仓库免费 2000 分钟/月） | 否（cron 触发） | 零成本跑每日推送 |

> 三种方式共用同一份 `.env` 配置，可以无成本切换。

---

## 3. 本地 Windows 部署

### 3.1 准备环境

- Python 3.10+（推荐 3.11，Docker 镜像也是 3.11）
- pip 23+
- Git（可选）

### 3.2 拉代码

```bash
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis
```

### 3.3 装依赖

```bash
pip install -r requirements.txt
```

> 部分包（alphasift）从 GitHub 拉，国内网络可能超时。alphasift 在 .env 中默认 `ALPHASIFT_ENABLED=false`，可以临时从 requirements.txt 删掉那一行再装。

### 3.4 初始化 .env

```bash
cp .env.example .env
```

至少要填：

```env
STOCK_LIST=600519,300750,002594
# LLM（见第 5 节）
DEEPSEEK_API_KEY=sk-xxx
# 或自定义渠道
# LLM_CHANNELS=agnes
# LLM_AGNES_PROTOCOL=openai
# LLM_AGNES_BASE_URL=https://...
# LLM_AGNES_API_KEY=xxx
# LLM_AGNES_MODELS=xxx
# LITELLM_MODEL=openai/xxx
```

### 3.5 启动

| 模式 | 命令 |
|---|---|
| 单次分析 | `python main.py --stocks 600519,300750,002594` |
| 仅 Web + Bot | `python main.py --serve-only` |
| Web + Bot + 每日定时 | `python main.py --schedule --serve` |
| 模拟跑（不推送） | `python main.py --dry-run` |
| 大盘复盘 | `python main.py --market-review` |

启动成功的日志（Web + Bot 模式）：

```
[Main] A股自选股智能分析系统 启动
FastAPI 服务已启动: http://127.0.0.1:8000
[DingTalk Stream] 客户端已启动，等待消息...
[Main] Dingtalk Stream client started in background.
```

### 3.6 停止

```powershell
Get-Process -Name python | Stop-Process -Force
```

### 3.7 关键文件位置

| 路径 | 作用 |
|---|---|
| `logs/stock_analysis_YYYYMMDD.log` | 当日运行日志 |
| `data/stock_analysis.db` | SQLite 数据库（WAL 模式） |
| `reports/` | 报告产物（Markdown） |
| `.env` | 全部配置（已被 .gitignore 排除） |

---

## 4. 钉钉机器人接入

钉钉 Stream 模式走 WebSocket 长连接，**不需要公网 IP / 域名**。

### 4.1 准备企业组织

钉钉开放平台只接受「已加入组织」的账号登录。个人用户先在手机钉钉 App「通讯录 → 创建企业」建一个空壳组织（个人也能用）。

### 4.2 开放平台建应用

地址：https://open-dev.dingtalk.com

1. 「应用开发」→「企业内部开发」→「创建应用」
2. 应用名：`股票分析助手`
3. 应用能力 → 机器人 → 开启
4. 权限管理 → 开通：

| 权限 | 必须 |
|---|---|
| `Card.Instance.Write` | 是 |
| `Card.Streaming.Write` | 是 |
| `im:message` | 是 |
| `im:message.group_at_msg` | 是 |
| `im:message.p2p_msg` | 是 |

5. 基础信息 → 复制 **AppKey** 和 **AppSecret**（注意复制完整、不要带空格）
6. 版本管理与发布 → 提交一版 → 等审核通过

### 4.3 配置 .env

```env
DINGTALK_APP_KEY=dingxxxxxxxxxxxxx
DINGTALK_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
DINGTALK_STREAM_ENABLED=true
```

### 4.4 启动

```bash
python main.py --serve-only
```

启动后日志无 `401 / authFailed` 即鉴权通过。

### 4.5 在钉钉里使用

1. 工作台搜「股票分析助手」→ 私聊
2. 群聊：群设置 → 机器人 → 添加 → 搜应用名
3. 私聊/群里发 `/help` 看所有命令

### 4.6 Bot 命令清单

| 命令 | 别名 | 用途 |
|---|---|---|
| `/analyze` | `/a` | 触发单股分析（多股） |
| `/ask` | - | 策略问股（指定策略） |
| `/chat` | `/c` `/问` | 自由对话 |
| `/market` | `/m` | 大盘复盘 |
| `/strategies` | - | 列出 15 种内置策略 |
| `/history` | - | 查 / 清空对话历史 |
| `/status` | - | 系统状态 |
| `/help` | - | 帮助 |

### 4.7 自然语言路由（推荐开启）

开启后用户说人话就行：

```env
AGENT_MODE=true
AGENT_NL_ROUTING=true
```

工作流程（`bot/dispatcher.py:457-539`）：

1. 正则预筛选：检测到股票代码 / 财经关键词才进 LLM
2. LLM 意图解析：判断 `analysis` / `chat` / `none`
3. 自动路由到 `/ask` 或 `/chat`

### 4.8 排障

| 现象 | 原因 | 解决 |
|---|---|---|
| `401 authFailed` | AppKey/Secret 错或被截断 | 重新去开放平台点"复制"按钮 |
| `dingtalk-stream SDK 未安装` | 缺包 | `pip install "dingtalk-stream>=0.24.3"` |
| 群里 @ 机器人无反应 | `AGENT_NL_ROUTING=false` 或没 @ | 开启后必须 @ 触发 |
| Bot 没启动 | 没带 `--serve` | 改用 `python main.py --serve-only` |
| 鉴权通过但无回复 | 应用没发布 / 没开通权限 | 开放平台检查版本和权限 |

---

## 5. LLM 大模型配置

底层用 LiteLLM，支持 OpenAI 兼容、Anthropic、Gemini、DeepSeek、Ollama 等。配置三层优先级：

1. `LITELLM_CONFIG`（YAML 文件）— 最高
2. `LLM_CHANNELS`（多渠道）— 推荐
3. legacy provider keys — 兜底

### 5.1 极简模式（一个 Key 就跑）

```env
# DeepSeek
DEEPSEEK_API_KEY=sk-xxx
# 兼容提示：仅填这一行时默认用 deepseek/deepseek-chat，
# 2026-07-24 起官方弃用，建议显式写：
LITELLM_MODEL=deepseek/deepseek-v4-flash

# Gemini 免费
GEMINI_API_KEY=AIzac...

# Anspire Open（一站式 LLM + 搜索）
ANSPIRE_API_KEYS=sk-xxx
```

### 5.2 渠道模式（推荐，支持多 Key 轮询和 fallback）

#### 官方 DeepSeek

```env
LLM_CHANNELS=deepseek
LLM_DEEPSEEK_PROTOCOL=deepseek
LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_DEEPSEEK_MODELS=deepseek-v4-flash,deepseek-v4-pro
LITELLM_MODEL=deepseek/deepseek-v4-flash
LITELLM_FALLBACK_MODELS=deepseek/deepseek-v4-pro
```

#### 第三方 OpenAI 兼容平台（硅基流动 / Agnes / 自建代理）

```env
LLM_CHANNELS=agnes
LLM_AGNES_PROTOCOL=openai
LLM_AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
LLM_AGNES_API_KEY=sk-xxx
LLM_AGNES_MODELS=agnes-2.0-flash
LITELLM_MODEL=openai/agnes-2.0-flash
LITELLM_FALLBACK_MODELS=openai/agnes-2.0-flash
```

> 关键：`LITELLM_MODEL` 必须带 `openai/` 前缀（`docs/LLM_CONFIG_GUIDE.md:60`）。`BASE_URL` 写到 `/v1` 即可，不要再拼 `/chat/completions`。

#### 多渠道自动 fallback

```env
LLM_CHANNELS=deepseek,agnes
LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_DEEPSEEK_MODELS=deepseek-v4-flash
LLM_AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
LLM_AGNES_API_KEY=sk-xxx
LLM_AGNES_MODELS=agnes-2.0-flash
LITELLM_MODEL=deepseek/deepseek-v4-flash
LITELLM_FALLBACK_MODELS=openai/agnes-2.0-flash
```

#### Ollama 本地（零成本）

```env
LLM_CHANNELS=ollama
LLM_OLLAMA_BASE_URL=http://localhost:11434
LLM_OLLAMA_MODELS=qwen3:8b
LITELLM_MODEL=ollama/qwen3:8b
```

> Ollama 必须用 `OLLAMA_API_BASE`，不要用 `OPENAI_BASE_URL`（LiteLLM 会错误拼接 URL）。

### 5.3 温度与采样

```env
LLM_TEMPERATURE=0.7
```

部分模型（GPT-5 / o 系列 / kimi-k2.6）有默认温度约束，LiteLLM 会自动适配。详见 `LLM_CONFIG_GUIDE.md` 第 130-141 行。

### 5.4 Agent 与 Vision 模型

```env
# Agent 策略问股专用模型（留空则继承主模型）
AGENT_LITELLM_MODEL=

# 图片识别股票代码
VISION_MODEL=openai/gpt-4o
```

### 5.5 快速连通性验证

```bash
python -c "from litellm import completion; import os; r = completion(model=os.environ.get('LITELLM_MODEL','openai/gpt-4o-mini'), messages=[{'role':'user','content':'hi'}], api_key=os.environ.get('OPENAI_API_KEY'), base_url=os.environ.get('OPENAI_BASE_URL'), timeout=30); print('OK:', r.choices[0].message.content[:80])"
```

返回 `OK: ...` 即正常。

---

## 6. 数据源配置

行情 fetcher 优先级（数字越小越优，`data_provider/base.py:303`）：

| 优先级 | 数据源 | 免费 | 覆盖 |
|---|---|---|---|
| -1（已配 Token 自动）| Tushare Pro | 有免费档 | A 股 + 部分港股 |
| 0 | Efinance | 是 | A 股 |
| 1 | AkShare | 是 | A 股 |
| 2 | Tushare / Pytdx | 是 | A 股 |
| 3 | Baostock | 是 | A 股历史 |
| 4 | YFinance | 是 | 美股 + 全球 |
| 5 | Longbridge | 否 | 港股量比/换手率 |

### 6.1 推荐配置（零成本）

```env
EFINANCE_PRIORITY=0
AKSHARE_PRIORITY=1
BAOSTOCK_PRIORITY=3
REALTIME_SOURCE_PRIORITY=tencent,akshare_sina,efinance
ENABLE_REALTIME_QUOTE=true
ENABLE_EASTMONEY_PATCH=true
PREFETCH_REALTIME_QUOTES=true
```

### 6.2 Tushare

```env
TUSHARE_TOKEN=1e20xxxx...
```

填了之后：

- 数据源优先级自动提升为 -1（`data_provider/tushare_fetcher.py:198-201`）
- 实时行情优先级自动把 `tushare` 加到首位（`src/config.py:2317-2323`）
- 项目内置 HTTP client，**不需要安装 tushare 包**（`docs/CHANGELOG.md:565`）

### 6.3 实时行情优先级

`tencent > akshare_sina > efinance > akshare_em > tushare`

- 腾讯、新浪是**单股查询**，稳定不封
- efinance / akshare_em 是**全量拉取**，单次拿到 5000+ 股行情，但易被东财封 IP
- 自选股 < 5 只时，关闭 `PREFETCH_REALTIME_QUOTES` 走逐个查询（`base.py:1407`）

### 6.4 性能与稳定性开关

| 变量 | 推荐 | 说明 |
|---|---|---|
| `ENABLE_CHIP_DISTRIBUTION` | 本地 true / 云端 false | 筹码接口不稳定 |
| `ENABLE_FUNDAMENTAL_PIPELINE` | true | 基本面 P0 |
| `FUNDAMENTAL_STAGE_TIMEOUT_SECONDS` | 8.0 | 超时降级 |
| `EFINANCE_CALL_TIMEOUT` | 30 | 单次请求超时（秒） |

---

## 7. 通知渠道配置

所有渠道**同时启用**互不影响，单一渠道失败不会拖垮主流程（`AGENTS.md:7`）。

### 7.1 企业微信

```env
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

### 7.2 飞书

```env
# 群机器人 Webhook
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
FEISHU_WEBHOOK_SECRET=xxx  # 如开启签名校验
FEISHU_WEBHOOK_KEYWORD=股票日报  # 如开启关键词

# 或飞书 App Bot
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_CHAT_ID=oc_xxx
FEISHU_RECEIVE_ID_TYPE=chat_id
```

### 7.3 Telegram

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

### 7.4 邮箱

```env
EMAIL_SENDER=your@qq.com
EMAIL_PASSWORD=授权码     # SMTP 授权码，不是登录密码
EMAIL_RECEIVERS=a@x.com,b@x.com  # 留空则发给自己
```

### 7.5 股票分组推送（Issue #268）

```env
STOCK_GROUP_1=600519,300750
EMAIL_GROUP_1=user1@x.com
STOCK_GROUP_2=002594,AAPL
EMAIL_GROUP_2=user2@x.com
```

> 仅邮件分组生效；企微/TG/钉钉 webhook 仍按完整 STOCK_LIST 推。

### 7.6 Markdown 转图片（飞书/企微有长度限制时）

```env
MARKDOWN_TO_IMAGE_CHANNELS=telegram,wechat
MARKDOWN_TO_IMAGE_MAX_CHARS=15000
MD2IMG_ENGINE=wkhtmltoimage  # 或 markdown-to-file
```

需要装 `wkhtmltopdf`（apt: `apt install wkhtmltopdf`）。

### 7.7 降噪机制

```env
NOTIFICATION_DEDUP_TTL_SECONDS=300      # 5 分钟内同 key 不重发
NOTIFICATION_COOLDOWN_SECONDS=60        # 限频
NOTIFICATION_QUIET_HOURS=23:00-07:30    # 静默时段
NOTIFICATION_TIMEZONE=Asia/Shanghai
NOTIFICATION_MIN_SEVERITY=warning       # 低于此级别不发
```

### 7.8 邮件合并

```env
MERGE_EMAIL_NOTIFICATION=true   # 个股 + 大盘合并成一封
```

---

## 8. Agent 智能对话

### 8.1 基础配置

```env
AGENT_MODE=true
AGENT_NL_ROUTING=true
```

### 8.2 内置策略（15 种）

`bull_trend` / `ma_golden_cross` / `volume_breakout` / `hot_theme` / `event_driven` / `growth_quality` / `expectation_repricing` / `shrink_pullback` / `bottom_volume` / `dragon_head` / `one_yang_three_yin` / `box_oscillation` / `chan_theory` / `wave_theory` / `emotion_cycle`

启用全部：

```env
AGENT_SKILLS=all
```

启用指定：

```env
AGENT_SKILLS=bull_trend,ma_golden_cross,shrink_pullback
```

### 8.3 架构模式

```env
AGENT_ARCH=single      # 单 Agent（默认）
AGENT_ARCH=multi       # 多 Agent 编排
```

multi 模式细分：

| 模式 | 流程 | LLM 调用次数 |
|---|---|---|
| quick | 技术→决策 | 2 |
| standard | 技术→情报→决策 | 3 |
| full | 技术→情报→风控→决策 | 4 |
| specialist | 技术→情报→风控→策略专家→决策 | 5+ |

```env
AGENT_ORCHESTRATOR_MODE=standard
AGENT_ORCHESTRATOR_TIMEOUT_S=300
```

### 8.4 记忆与权重

```env
AGENT_MEMORY_ENABLED=false          # 追踪历史准确率，省 LLM 费用
AGENT_SKILL_AUTOWEIGHT=true         # 按回测表现自动加权
AGENT_RISK_OVERRIDE=true            # 风控 Agent 否决买入
```

### 8.5 自定义策略目录

```env
AGENT_SKILL_DIR=./strategies
```

支持 YAML 自定义策略文件。

---

## 9. Web 工作台

### 9.1 启动

```env
WEBUI_ENABLED=true
WEBUI_HOST=127.0.0.1   # 本地；Docker 部署必须 0.0.0.0
WEBUI_PORT=8000
WEBUI_AUTO_BUILD=true  # 启动前自动 npm build
```

### 9.2 主要页面

| 路径 | 功能 |
|---|---|
| `/` | 工作台首页 |
| `/chat` | Agent 策略问股 |
| `/history` | 历史报告 |
| `/portfolio` | 持仓管理 |
| `/backtest` | 回测 |
| `/settings` | 系统设置（LLM、通知、数据源） |
| `/api/docs` | FastAPI OpenAPI 文档 |

### 9.3 密码保护

```env
ADMIN_AUTH_ENABLED=true
# 首次访问在网页设置初始密码
# 忘记密码：python -m src.auth reset_password
```

### 9.4 公网访问

需要 Nginx 反代 + 域名 + HTTPS，详见 [deploy-webui-cloud.md](deploy-webui-cloud.md)。

---

## 10. Linux 云服务器 Docker 部署

### 10.1 一键部署（推荐）

```bash
# 在云服务器上跑（一行命令）
curl -fsSL https://raw.githubusercontent.com/ZhuLinsen/daily_stock_analysis/main/scripts/deploy-to-cloud.sh | sudo bash

# 或下载后跑
wget -O deploy.sh https://raw.githubusercontent.com/ZhuLinsen/daily_stock_analysis/main/scripts/deploy-to-cloud.sh
chmod +x deploy.sh
sudo ./deploy.sh
```

脚本自动完成：

1. 装 Docker + Docker Compose v2
2. 配置镜像加速（`DOCKER_MIRROR` 环境变量）
3. 克隆/更新代码到 `/opt/daily_stock_analysis`
4. 准备 `.env`（自动把 `WEBUI_HOST=127.0.0.1` 改成 `0.0.0.0`，这是容器必需）
5. 构建镜像
6. 启动 `stock-server`（Web + 钉钉）+ `stock-analyzer`（每日定时）
7. 验证：容器状态 + Web 健康 + 钉钉鉴权

可调环境变量：

| 变量 | 默认 |
|---|---|
| `INSTALL_DIR` | `/opt/daily_stock_analysis` |
| `REPO_BRANCH` | `main` |
| `DOCKER_MIRROR` | 空 |
| `ENV_SOURCE` | 空（手动建） |
| `SKIP_DOCKER_INSTALL` | `0` |
| `SKIP_BUILD` | `0` |
| `SKIP_GIT` | `0` |

### 10.2 手工部署

```bash
# 1. 装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 重连 SSH

# 2. 拉代码
cd /opt
sudo git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
sudo chown -R $USER:$USER daily_stock_analysis
cd daily_stock_analysis

# 3. 配 .env
cp .env.example .env
nano .env  # 填入所有真实配置

# 4. 构建
docker compose -f docker/docker-compose.yml build

# 5. 启动
docker compose -f docker/docker-compose.yml up -d server
docker compose -f docker/docker-compose.yml up -d analyzer

# 6. 看状态
docker compose -f docker/docker-compose.yml ps
```

### 10.3 docker-compose.yml 解析

`docker/docker-compose.yml` 定义了两个服务（`x-common` 共享配置）：

- `server`（容器名 `stock-server`）：`--serve-only` 模式，跑 Web + 钉钉 bot
- `analyzer`（容器名 `stock-analyzer`）：`--schedule` 模式，每日 18:00 自动分析推送

挂载卷：

| 宿主机 | 容器 | 用途 |
|---|---|---|
| `./data` | `/app/data` | SQLite 数据库 |
| `./logs` | `/app/logs` | 运行日志 |
| `./reports` | `/app/reports` | 报告产物 |
| `./strategies` | `/app/strategies` | 自定义策略（只读） |
| `./longbridge_tokens` | `/home/dsa/.longbridge` | 长桥 OAuth 缓存 |

容器以非 root 用户 `dsa` (UID 1000) 运行，`docker/entrypoint.sh:44-86` 自动修复挂载目录权限。

### 10.4 防火墙

| 云控制台安全组 | 入方向 8000 端口 |
| Ubuntu ufw | `sudo ufw allow 8000/tcp` |

钉钉 Stream 是**出站 WebSocket**，不需要放行进站。

### 10.5 日常管理

```bash
# 状态
docker compose -f docker/docker-compose.yml ps

# 日志
docker logs -f stock-server
docker logs -f stock-analyzer

# 重启
docker compose -f docker/docker-compose.yml restart server

# 停服（保留数据）
docker compose -f docker/docker-compose.yml stop

# 删容器（保留数据卷）
docker compose -f docker/docker-compose.yml down

# 进容器排查
docker exec -it -u dsa stock-server bash

# 更新
cd /opt/daily_stock_analysis
git pull
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
```

### 10.6 本地访问服务器 Web

SSH 端口转发：

```powershell
# 本地 Windows PowerShell
ssh -L 8000:127.0.0.1:8000 user@<server-ip>
# 然后浏览器开 http://127.0.0.1:8000
```

---

## 11. GitHub Actions 零成本部署

适合：只跑每日定时推送，不需要钉钉 bot 长连接、不需要 Web 长期在线。

### 11.1 准备

1. Fork 仓库到自己的 GitHub 账号
2. Settings → Secrets and variables → Actions → New repository secret

#### AI 模型 Secret（至少一个）

| Secret | 用途 |
|---|---|
| `ANSPIRE_API_KEYS` | Anspire 一站式 |
| `DEEPSEEK_API_KEY` | DeepSeek 官方 |
| `GEMINI_API_KEY` | Gemini（免费额度） |
| `ANTHROPIC_API_KEY` | Claude |
| `OPENAI_API_KEY` + `OPENAI_BASE_URL` + `OPENAI_MODEL` | OpenAI 兼容 |

#### 通知 Secret（至少一个）

| Secret | 用途 |
|---|---|
| `WECHAT_WEBHOOK_URL` | 企业微信 |
| `FEISHU_WEBHOOK_URL` | 飞书 |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Telegram |
| `EMAIL_SENDER` + `EMAIL_PASSWORD` | 邮件 |

#### 必填

| Secret | 用途 |
|---|---|
| `STOCK_LIST` | 自选股代码 |

#### 可选

| Secret | 用途 |
|---|---|
| `TUSHARE_TOKEN` | 数据源增强 |
| `TAVILY_API_KEYS` / `SERPAPI_API_KEYS` / `BOCHA_API_KEYS` | 搜索 |

### 11.2 启用 Actions

仓库 → Actions 标签 → 「I understand my workflows, go ahead and enable them」

### 11.3 触发

- 自动：工作日 UTC 10:00 = 北京时间 18:00（`.github/workflows/00-daily-analysis.yml:6`）
- 手动：Actions → 每日股票分析 → Run workflow

### 11.4 限制

- 公共仓库每月 2000 分钟免费
- 单次任务 6 小时硬上限
- 无法跑钉钉 bot（Stream 是长连接，Actions 容器用完即销毁）

---

## 12. 安全实践

### 12.1 凭据管理

- `.env` 在 `.gitignore` 中，**不会**被 git 跟踪
- 永远不要把凭据贴到 issue / PR / 对话 / 截图里
- 凭据泄露后**立刻重置**：
  - 钉钉 AppSecret（开放平台）
  - Tushare Token
  - LLM API Key
  - 邮箱授权码
  - Webhook URL（重新签发）

### 12.2 端口与访问控制

| 场景 | 建议 |
|---|---|
| 本地 Windows | `WEBUI_HOST=127.0.0.1`，仅本机 |
| Docker 部署（仅内网用） | `WEBUI_HOST=0.0.0.0` + `ADMIN_AUTH_ENABLED=true` |
| 公网 Web | Nginx + 域名 + Let's Encrypt + `ADMIN_AUTH_ENABLED=true` |
| 公网 + 多用户 | Nginx Basic Auth + ADMIN_AUTH 双层 |

### 12.3 WebHook 签名校验

```env
WEBHOOK_VERIFY_SSL=true   # 默认开启，自签名证书才关
```

企业微信 / 钉钉 webhook 都应开启签名校验。

### 12.4 数据备份

- `./data/stock_analysis.db` 是核心资产，定期 `cp` 备份
- `./data/*.db-wal` / `*.db-shm` 也要一起复制（SQLite WAL 文件）
- 备份前停止服务或用 `sqlite3 .backup` API

### 12.5 Dockerfile 安全

- 容器以 UID 1000 非 root 用户运行（`docker/Dockerfile:39-41`）
- `entrypoint.sh` 自动修复挂载权限
- 不在镜像里固化任何凭据

---

## 13. 运维排障

### 13.1 启动失败

| 现象 | 排查 |
|---|---|
| `ModuleNotFoundError` | 重新 `pip install -r requirements.txt` |
| 启动后 5 秒退出 | `docker logs stock-server` 或 `logs/stock_analysis_*.log` 看具体报错 |
| `KeyError: 'LITELLM_MODEL'` | .env 没填 LLM 配置 |
| `Permission denied: data/stock_analysis.db` | SQLite 目录无写权限 |

### 13.2 钉钉 Bot 排障

| 现象 | 解决 |
|---|---|
| `401 authFailed` | AppKey 复制截断 / AppSecret 错配 |
| Stream 反复重试 | AppKey/Secret 完全不正确 |
| 群消息无反应 | 没 @ / `AGENT_NL_ROUTING=false` |
| 私聊无反应 | 应用未发布 / 权限未开通 |

### 13.3 LLM 排障

| 现象 | 原因 | 解决 |
|---|---|---|
| `404 model not found` | 缺 `openai/` 前缀或模型名错 | 核对 `LITELLM_MODEL` |
| `401 unauthorized` | API Key 错 | 重置 Key |
| `429 rate limit` | 限流 | 启用 `LLM_FALLBACK_MODELS` |
| `temperature not supported` | kimi/GPT-5 等有约束 | LiteLLM 自动适配（详见 `LLM_CONFIG_GUIDE.md:130-141`） |
| 慢 / 超时 | 30s 内没回 | 调整 `LLM_TIMEOUT_SEC=60` |

### 13.4 数据源排障

| 现象 | 解决 |
|---|---|
| 东财接口 `RemoteDisconnected` | 开启 `ENABLE_EASTMONEY_PATCH=true` |
| 实时行情一直空 | 关闭 `PREFETCH_REALTIME_QUOTES` 改单股查询 |
| Tushare 报错 token | 核对 Token / 是否有 2000 积分 |
| `database is locked` | SQLite 锁，提高 `SQLITE_BUSY_TIMEOUT_MS` |

### 13.5 通知排障

```bash
python main.py --check-notify
# 输出每个渠道的健康状态
```

详见 `docs/run-diagnostics-p0.md` / `p1` / `p2` / `p3`。

### 13.6 性能调优

| 现象 | 调优 |
|---|---|
| 并发太高被封 IP | `MAX_WORKERS=2`、`ANALYSIS_DELAY=5` |
| 慢查询 | 关 `ENABLE_CHIP_DISTRIBUTION` |
| 日志太大 | 加 logrotate 规则：`/app/logs/*.log { daily rotate 7 }` |
| 内存爆 | 关 `ENABLE_FUNDAMENTAL_PIPELINE` 暂缓；Docker 提升到 1G |

---

## 14. 升级与维护

### 14.1 更新代码

| 部署方式 | 命令 |
|---|---|
| 本地 | `git pull && pip install -r requirements.txt` |
| Docker | `cd /opt/daily_stock_analysis && git pull && docker compose -f docker/docker-compose.yml build && docker compose -f docker/docker-compose.yml up -d` |
| Actions | push 到 main 分支自动触发（无 daily 任务时） |

### 14.2 数据迁移

升级时**保留**：

- `.env`
- `data/`、`logs/`、`reports/`
- `longbridge_tokens/`
- `strategies/`（自定义策略）

可清理：

- `__pycache__/`、`*.pyc`
- 旧版本构建缓存：`docker builder prune`

### 14.3 数据库升级

`SQLITE_WAL_ENABLED=true` 时升级：

```bash
# 容器外
sqlite3 data/stock_analysis.db ".backup data/backup.db"
# 或进容器
docker exec -u dsa stock-server python -m src.storage.migrate
```

### 14.4 版本回退

```bash
git log --oneline -10
git checkout <commit-hash>
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
```

数据兼容性问题先在 `docs/CHANGELOG.md` 查 migration notes。

---

## 15. 附录：环境变量速查

### 必填

| 变量 | 含义 | 示例 |
|---|---|---|
| `STOCK_LIST` | 自选股代码 | `600519,300750,002594` |
| LLM 配置（任一） | 见第 5 节 | - |

### 钉钉 Bot

| 变量 | 默认 | 说明 |
|---|---|---|
| `DINGTALK_APP_KEY` | - | 开放平台获取 |
| `DINGTALK_APP_SECRET` | - | 开放平台获取 |
| `DINGTALK_STREAM_ENABLED` | `false` | 开启 Stream 模式 |

### LLM

| 变量 | 默认 | 说明 |
|---|---|---|
| `LITELLM_MODEL` | - | 主模型（含 provider 前缀） |
| `LITELLM_FALLBACK_MODELS` | - | 逗号分隔 fallback |
| `LLM_TEMPERATURE` | `0.7` | 0-2 |
| `LLM_TIMEOUT_SEC` | `60` | 单次请求超时 |
| `LLM_CHANNELS` | - | 多渠道配置 |
| `LLM_<CHANNEL>_PROTOCOL` | - | openai / anthropic / gemini / deepseek |
| `LLM_<CHANNEL>_BASE_URL` | - | 兼容端点 |
| `LLM_<CHANNEL>_API_KEY` | - | |
| `LLM_<CHANNEL>_MODELS` | - | 逗号分隔模型列表 |

### 数据源

| 变量 | 默认 |
|---|---|
| `TUSHARE_TOKEN` | 空 |
| `EFINANCE_PRIORITY` | `0` |
| `AKSHARE_PRIORITY` | `1` |
| `BAOSTOCK_PRIORITY` | `3` |
| `YFINANCE_PRIORITY` | `4` |
| `REALTIME_SOURCE_PRIORITY` | `tencent,akshare_sina,efinance` |
| `ENABLE_REALTIME_QUOTE` | `true` |
| `ENABLE_EASTMONEY_PATCH` | `false` |
| `PREFETCH_REALTIME_QUOTES` | `true` |
| `ENABLE_CHIP_DISTRIBUTION` | `true` |
| `ENABLE_FUNDAMENTAL_PIPELINE` | `true` |

### 通知

| 变量 | 说明 |
|---|---|
| `WECHAT_WEBHOOK_URL` | 企业微信 |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书 App Bot |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram |
| `EMAIL_SENDER` / `EMAIL_PASSWORD` / `EMAIL_RECEIVERS` | 邮件 |
| `CUSTOM_WEBHOOK_URLS` | 自定义 Webhook（钉钉/Discord/Slack/Bark） |
| `MERGE_EMAIL_NOTIFICATION` | `true` 合并邮件 |
| `MARKDOWN_TO_IMAGE_CHANNELS` | 长报告转图片 |

### Agent

| 变量 | 默认 | 说明 |
|---|---|---|
| `AGENT_MODE` | `false` | 开启 Agent |
| `AGENT_NL_ROUTING` | `false` | 自然语言路由 |
| `AGENT_SKILLS` | 默认 | 策略列表 / `all` |
| `AGENT_ARCH` | `single` | `single` / `multi` |
| `AGENT_ORCHESTRATOR_MODE` | `standard` | multi 模式子选项 |
| `AGENT_ORCHESTRATOR_TIMEOUT_S` | `600` | 超时 |
| `AGENT_RISK_OVERRIDE` | `true` | 风控 Agent 否决权 |
| `AGENT_MEMORY_ENABLED` | `false` | 记忆与校准 |
| `AGENT_SKILL_AUTOWEIGHT` | `false` | 自动加权 |

### 调度

| 变量 | 默认 |
|---|---|
| `SCHEDULE_ENABLED` | `false` |
| `SCHEDULE_TIME` | `18:00` |
| `SCHEDULE_RUN_IMMEDIATELY` | `true` |
| `RUN_IMMEDIATELY` | `true` |
| `MARKET_REVIEW_ENABLED` | `true` |
| `MARKET_REVIEW_REGION` | `cn` |

### Web / 服务

| 变量 | 默认 |
|---|---|
| `WEBUI_ENABLED` | `false` |
| `WEBUI_HOST` | `127.0.0.1` |
| `WEBUI_PORT` | `8000` |
| `ADMIN_AUTH_ENABLED` | `false` |
| `DATABASE_PATH` | `./data/stock_analysis.db` |
| `LOG_DIR` | `./logs` |
| `LOG_LEVEL` | `INFO` |
| `MAX_WORKERS` | `3` |
| `ANALYSIS_DELAY` | `0` |

### 搜索

| 变量 | 说明 |
|---|---|
| `TAVILY_API_KEYS` | 多 Key 轮询 |
| `SERPAPI_API_KEYS` |  |
| `BOCHA_API_KEYS` | 中文优化 |
| `BRAVE_API_KEYS` |  |
| `MINIMAX_API_KEYS` |  |
| `SEARXNG_BASE_URLS` | 自建实例 |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | `true` |
| `NEWS_STRATEGY_PROFILE` | `short` |
| `NEWS_MAX_AGE_DAYS` | `3` |

---

## 附：常用命令速记

| 操作 | 命令 |
|---|---|
| 单次分析 | `python main.py --stocks 600519,300750,002594` |
| 仅 Web + Bot | `python main.py --serve-only` |
| Web + Bot + 定时 | `python main.py --schedule --serve` |
| 大盘复盘 | `python main.py --market-review` |
| 模拟跑 | `python main.py --dry-run` |
| 通知诊断 | `python main.py --check-notify` |
| 查 LLM 状态 | Web `/settings` 或 Bot `/status` |
| 看日志 | `Get-Content logs\stock_analysis_$(Get-Date -Format yyyyMMdd).log -Wait` |
| 停服（本地） | `Get-Process -Name python \| Stop-Process -Force` |
| Docker 看状态 | `docker compose -f docker/docker-compose.yml ps` |
| Docker 跟踪日志 | `docker logs -f stock-server` |
| Docker 重启 | `docker compose -f docker/docker-compose.yml restart server` |
| Docker 更新 | `git pull && docker compose -f docker/docker-compose.yml build && docker compose -f docker/docker-compose.yml up -d` |
| 一键云部署 | `curl -fsSL https://raw.githubusercontent.com/ZhuLinsen/daily_stock_analysis/main/scripts/deploy-to-cloud.sh \| sudo bash` |

---

文档结束。如有更新请关注 `docs/CHANGELOG.md`。
