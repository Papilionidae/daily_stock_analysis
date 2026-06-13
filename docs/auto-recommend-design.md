# AI 自动荐股方案设计

> **状态**：方案设计 / 头脑风暴
>
> **目标**：让系统能根据新闻热点、行情数据、情绪周期和量化策略，**主动扫描全市场**，自动推荐适合短期操作的股票并推送。

---

## 目录

1. [现状分析](#1-现状分析)
2. [核心概念](#2-核心概念)
3. [完整流水线](#3-完整流水线)
4. [候选股发现通道](#4-候选股发现通道)
5. [评分与排序](#5-评分与排序)
6. [深度分析](#6-深度分析)
7. [输出与通知](#7-输出与通知)
8. [调度策略](#8-调度策略)
9. [配置项](#9-配置项)
10. [文件变更清单](#10-文件变更清单)
11. [风险与控制](#11-风险与控制)
12. [开放问题](#12-开放问题)

---

## 1. 现状分析

### 已具备的模块

| 模块 | 位置 | 能做什么 |
|------|------|----------|
| AlphaSift 全市场扫描 | `src/services/alphasift_service.py` | 按策略扫全市场，输出候选股 + LLM 排名 |
| 多因子选股工具 | `src/agent/tools/factor_tools.py` | `get_universe_screen` 七因子打分，行业均衡 Top N |
| 个股分析流水线 | `src/core/pipeline.py` | 给定股票产出售卖信号、置信度、关键价位 |
| 定时调度 | `src/scheduler.py` | 每日定时执行任务 |
| 技术分析引擎 | `src/stock_analyzer.py` | MA/MACD/RSI/量价/支撑阻力全量计算 |
| 情报搜索 | `src/search_service.py` | 新闻/公告搜索 |
| 板块排名 | `data_provider/` | 行业板块涨跌幅排名 |
| 通知推送 | `src/notification.py` | 多渠道推送 |
| 决策信号持久化 | `src/services/decision_signal_service.py` | 分析结果落库 |
| YAML 策略体系 | `strategies/*.yaml` | 20 个可插拔交易策略 |
| 情绪周期分析 | `strategies/emotion_cycle.yaml` | 换手率+量价+新闻情绪判断 |
| 热点题材判断 | `strategies/hot_theme.yaml` | 政策/产业/市场热点跟踪 |

### 缺失的环节

```
[定时触发]
    ↓
  Phase 1: 市场上下文收集 (✅ 可复用 market_strategy / 行情接口)
    ↓
  Phase 2: 多通道候选股发现 → 初筛候选池  ← ❌ 核心缺失
    ↓
  Phase 3: 候选股去重排序 → Top N         ← ❌ 核心缺失
    ↓
  Phase 4: 深度分析 (✅ 可复用 pipeline)
    ↓
  Phase 5: 聚合报告 → 推送 (✅ 可复用 notification)
```

**一句话**：系统能分析你指定的股票，但不能自主从全市场挖掘机会。

---

## 2. 核心概念

### 2.1 发现通道

每个"发现通道"是一个独立的候选股来源，通过不同的策略扫描市场：

| 通道 | 输入 | 输出 | 扫描频率 |
|------|------|------|----------|
| 题材驱动 (theme) | 全网新闻 → 热点关键词 → 关联股票 | 题材受益股列表 | 每日/盘中 |
| 板块驱动 (sector) | 板块排名 → top 板块 → 板块内强势股 | 板块龙头/强势股 | 每日 |
| 因子驱动 (factor) | 全市场 → 七因子评分 → 行业中性化 | 多因子 Top N | 每日（盘后） |
| 技术面驱动 (technical) | 全市场 K 线 → 模式识别 | 金叉/突破/回踩/底部放量 | 每日/盘中 |
| AlphaSift 驱动 | 外部量化策略 | 策略定制候选股 | 按策略 |

### 2.2 候选股生命周期

```
初始候选池 (各通道合并) → 去重 → 基线过滤 → 评分排序 → Top N → 深度分析 → 输出
```

---

## 3. 完整流水线

```
┌─────────────────────────────────────────────────────────────────────┐
│  AutoRecommendEngine.run()                                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Phase 1: 市场上下文                                                  │
│  ┌─────────────────────────────────────────────────┐               │
│  │ ① 获取大盘指数 (沪深/港股/美股)                     │               │
│  │ ② 获取板块排名 (top 10 / bottom 10)               │               │
│  │ ③ 获取今日热门新闻 (market-wide news scan)         │               │
│  │ ④ 判断当前市场状态 (trending_up/down/sideways/    │               │
│  │    volatile/sector_hot)                            │               │
│  │ ⑤ 输出: MarketContext                              │               │
│  └─────────────────────────────────────────────────┘               │
│           │                                                         │
│           ▼                                                         │
│  Phase 2: 多通道候选股发现                                            │
│  ┌─────────────────────────────────────────────────┐               │
│  │ 并行执行各发现通道:                                │               │
│  │  ├─ ThemeSource.scan(market_context)             │               │
│  │  ├─ SectorSource.scan(market_context)            │               │
│  │  ├─ FactorSource.scan(market_context)            │               │
│  │  ├─ TechnicalSource.scan(market_context)         │               │
│  │  └─ AlphaSiftSource.scan(market_context)         │               │
│  │ 各通道返回 Candidate 列表 (含来源标签、原始评分)    │               │
│  └─────────────────────────────────────────────────┘               │
│           │                                                         │
│           ▼                                                         │
│  Phase 3: 合并 → 过滤 → 排序                                         │
│  ┌─────────────────────────────────────────────────┐               │
│  │ ① union 所有通道的候选股，按股票代码去重            │               │
│  │ ② 基线过滤:                                      │               │
│  │    - 排除 ST / *ST / 退市整理                     │               │
│  │    - 排除市值 < MIN_MARKET_CAP                   │               │
│  │    - 排除日均换手率 < MIN_TURNOVER               │               │
│  │    - 排除排除列表 (EXCLUDED_STOCKS)              │               │
│  │    - 同类通道同板块最多 N 只 (SECTOR_LIMIT)       │               │
│  │ ③ 多维度评分: 因子分 + 技术分 + 情绪分 + 题材分    │               │
│  │ ④ 加权综合排序 → 取 Top N_CANDIDATES             │               │
│  └─────────────────────────────────────────────────┘               │
│           │                                                         │
│           ▼                                                         │
│  Phase 4: 深度分析 (Top K 只)                                       │
│  ┌─────────────────────────────────────────────────┐               │
│  │ 对 Top K (如 5) 只候选股:                        │               │
│  │  ├─ 调用 StockAnalysisPipeline (复用现有流水线)  │               │
│  │  │   = 全量技术指标 + 新闻情报 + LLM 分析         │               │
│  │  │    + 可选 AgentOrchestrator 多 Agent 分析     │               │
│  │  └─ 或调用 GeminiAnalyzer (轻量, 跳过Agent)       │               │
│  └─────────────────────────────────────────────────┘               │
│           │                                                         │
│           ▼                                                         │
│  Phase 5: 聚合报告 & 推送                                            │
│  ┌─────────────────────────────────────────────────┐               │
│  │ ① 按 sentiment_score + confidence 排序          │               │
│  │ ② 生成 "今日荐股 Top N" 报告                     │               │
│  │    - 市场背景一句话                               │               │
│  │    - 每个股票: 信号/置信度/策略来源/核心逻辑/价位   │               │
│  │    - 风险提示                                     │               │
│  │ ③ 持久化为 DecisionSignal                        │               │
│  │ ④ 推送通知 (多渠道)                               │               │
│  └─────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. 候选股发现通道

### 4.1 题材驱动通道 (ThemeSource)

```
输入: 今日热门新闻 (market-wide news scan)
逻辑:
  1. 调用 search_service 搜索今日热点新闻 (不限股票)
  2. 提取热点主题关键词 (如 "AI芯片" "低空经济")
  3. 对每个热点主题，搜索相关股票
  4. 筛选: 新闻正面的、板块有共振的

评分维度:
  - 题材强度 (新闻热度 + 板块涨幅)
  - 个股相关性 (实质受益 vs 蹭概念)
  - 题材阶段 (启动/扩散/分化/退潮)

复用: strategies/hot_theme.yaml 的题材判断逻辑
```

### 4.2 板块驱动通道 (SectorSource)

```
输入: get_sector_rankings → 板块排名
逻辑:
  1. 获取板块排名 top 5
  2. 对每个 top 板块，获取成分股
  3. 筛选: 板块内涨幅 top 3、量比 > 1.2
  4. 验证: 板块持续走强 ≥ 3 日 (非一日游)

评分维度:
  - 板块动量得分 (5/20/60 日)
  - 板块资金流
  - 个股在板块中的相对强度

复用: strategies/sector_rotation.yaml 的四维评分
```

### 4.3 因子驱动通道 (FactorSource)

```
输入: get_factor_scores / get_universe_screen
逻辑:
  1. 调用 get_universe_screen 获取全市场因子评分 top 30
  2. 行业均衡: 每个行业最多 3 只
  3. 排除高波动、低流动性个股

评分维度:
  - 七因子加权综合分
  - 价值/质量/动量/反转/规模/波动/流动性

复用: src/agent/tools/factor_tools.py
```

### 4.4 技术面驱动通道 (TechnicalSource)

```
输入: 全市场 K 线扫描
数据源: tickflow 批量 K 线查询接口
  → 对接 tickflow 的批量日 K 接口 (如 batch_kline / daily_batch)
  → 支持一次性拉取全市场 N 日 K 线
  → 盘前扫描时使用昨日收盘数据，盘中扫描使用已生成的今日数据

逻辑:
  对每个股票检测:
  1. 均线多头排列 (MA5 > MA10 > MA20)
  2. 金叉信号 (MA5 × MA10 近 3 日上穿)
  3. 放量突破 (量比 > 2.0, 价格站上阻力位)
  4. 缩量回踩 (回踩 MA5/MA10, 量 < 0.7 均量)
  5. 底部放量 (跌幅 > 15% 后放量 3 倍)

盘前扫描行为:
  - 使用昨日收盘 K 线数据计算全部指标
  - 量比 = 昨日量 / 5 日均量
  - 突破判定基于已确认的昨日收盘价
  - 不包含盘中实时信号 (盘前无当日数据)

评分维度:
  - 信号强度 (多个信号叠加)
  - 趋势评分 (StockTrendAnalyzer 的 signal_score)
  - 乖离率位置

复用: src/stock_analyzer.py, strategies/*.yaml 的模式定义
```

### 4.5 AlphaSift 驱动通道 (AlphaSiftSource)

```
输入: AlphaSiftService.screen()
逻辑:
  1. 调用 alphasift_service.screen(market="cn", strategy="dual_low")
  2. 获取候选股及其 LLM 排名
  3. 做 DSA Enrichment (补充新闻、基本面)

评分维度:
  - AlphaSift 策略评分
  - LLM 排名

复用: src/services/alphasift_service.py
```

### 4.6 通道配置

```python
# 可配置启用/禁用
ENABLED_CHANNELS = {
    "theme": True,
    "sector": True,
    "factor": True,
    "technical": True,
    "alphasift": False,  # 需要外部包
}
```

---

## 5. 评分与排序

### 5.1 评分维度

每个候选股在 Phase 2 获得来源通道的原始评分，在 Phase 3 补充多维度评分：

| 维度 | 分数范围 | 来源 | 说明 |
|------|----------|------|------|
| 通道置信分 | 0-100 | 各发现通道自带 | 通道对该信号的置信程度 |
| 因子分 | -3 ~ +3 | `get_factor_scores` | 七因子行业中性化 Z-score |
| 技术分 | 0-100 | `StockTrendAnalyzer` | 趋势评分 signal_score |
| 情绪分 | -20 ~ +20 | `emotion_cycle.yaml` 逻辑 | 情绪周期阶段 |
| 题材分 | -15 ~ +15 | `hot_theme.yaml` 逻辑 | 题材强度和相关性 |
| 板块分 | -10 ~ +10 | `sector_rotation.yaml` 逻辑 | 板块排名和动量 |

### 5.2 加权合成

```python
COMPOSITE_WEIGHTS = {
    "channel_confidence": 0.15,
    "factor_score": 0.20,
    "technical_score": 0.25,
    "sentiment_score": 0.15,
    "theme_score": 0.15,
    "sector_score": 0.10,
}
# composite = Σ (维度分 × 权重)，需归一化到同一量纲
```

权重可随市场状态调整：

| 市场状态 | factor | technical | sentiment | theme | sector |
|----------|--------|-----------|-----------|-------|--------|
| trending_up | 0.20 | 0.30 | 0.10 | 0.15 | 0.25 |
| trending_down | 0.25 | 0.15 | 0.25 | 0.15 | 0.20 |
| sideways | 0.25 | 0.20 | 0.15 | 0.20 | 0.20 |
| sector_hot | 0.15 | 0.20 | 0.15 | 0.30 | 0.20 |
| volatile | 0.15 | 0.20 | 0.25 | 0.25 | 0.15 |

### 5.3 分数映射

```
综合分 > 70  → ⭐⭐⭐ 强烈推荐
综合分 50-70 → ⭐⭐ 推荐
综合分 30-50 → ⭐ 观察
综合分 < 30  → 剔除 (不进入深度分析)
```

---

## 6. 深度分析

对 Top K 候选股执行完整分析。有两种模式：

### 模式 A: 完整 Pipeline（默认）

```
StockAnalysisPipeline.process_single_stock()
  → 全量技术分析 + 情报搜索 + LLM 分析 (GeminiAnalyzer)
  → 输出: AnalysisResult (含 sentiment_score / operation_advice / 价位)
```

### 模式 B: Agent 模式（可选）

```
AgentOrchestrator 在 specialist 模式下运行
  → TechnicalAgent → IntelAgent → RiskAgent → SkillAgent × N → DecisionAgent
  → 输出: Decision Dashboard JSON
```

### 模式 C: 快速模式（盘中使用，预算敏感）

```
仅 GeminiAnalyzer (跳过 Agent)
  → 输出: AnalysisResult
  → 约 1/3 的耗时和 token 消耗
```

---

## 7. 输出与通知

### 7.1 报告格式

```
📊 今日 AI 荐股 Top 5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 2026-06-13 (盘后)
📈 市场背景: 上证 3250 (+0.8%)，主线板块: AI/半导体/新能源
🌡️ 情绪周期: 升温介入 (换手率 2.8%，近一年中位)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🥇 600XXX 某某股份  ⭐⭐⭐ 强烈推荐
  信号: 买入 | 置信度: 88%
  策略: 多头趋势 + 缩量回踩 MA5 + 题材共振
  逻辑: AI 芯片政策利好，缩量回踩 MA5 企稳，板块主线行情中
  价位: 支撑 25.6 / 现价 26.8 / 阻力 28.5
  止损: 24.8 (-7.5%)

🥈 000XXX 某某科技  ⭐⭐ 推荐
  信号: 买入 | 置信度: 75%
  策略: 行业轮动 + 放量突破
  逻辑: 板块排名 top 3，放量突破 20 日高点，量比 2.3
  价位: 支撑 18.2 / 现价 19.5 / 阻力 21.0
  止损: 17.5 (-10.3%)

...
```

### 7.2 通知渠道

| 渠道 | 格式 | 截断策略 |
|------|------|----------|
| WeChat | Markdown → 图片 | 4000 字 |
| Telegram | Markdown | 无限制 |
| Feishu | Markdown → 图片 | 4000 字 |
| Web UI | 原生 Dashboard | 无限制 |

### 7.3 数据持久化

每个推荐结果写入 `DecisionSignal` 表：

```python
DecisionSignal(
    stock_code="600XXX",
    action="buy",
    signal_source="auto_recommend",
    confidence=0.88,
    strategy_tags=["bull_trend", "shrink_pullback", "hot_theme"],
    analysis_summary="...",
    created_at=datetime.now(),
    expiry=datetime.now() + timedelta(days=1),  # 短线推荐有效期 1 天
)
```

---

## 8. 调度策略

### 8.1 时间窗口

分析模式根据时间阶段**自动切换**：

| 时段 | 时间 | 用途 | 通道重点 | 分析模式 | 原因 |
|------|------|------|----------|----------|------|
| 盘前扫描 | 09:00 | 隔夜新闻 + 昨日收盘技术面 | theme, sector, technical | **quick** (仅 GeminiAnalyzer，跳过 Agent) | 此时当日 K 线未生成，不需深度 LLM；快速出信号 |
| 午间扫描 | 12:00 | 上午盘面 + 午间新闻 | sector, technical, theme | **pipeline** (完整 Pipeline) | 半日数据可做技术分析，需基本面+新闻交叉验证 |
| 盘后分析 | 16:30 | 全日数据、全通道深度分析 | all channels | **agent** (AgentOrchestrator specialist 模式) | 数据完整，可做全量分析 + SkillAgent 策略评估 |

自动切换逻辑：

```python
def _resolve_analysis_mode(phase: str) -> str:
    """根据阶段返回分析模式: quick / pipeline / agent"""
    mapping = {
        "premarket": "quick",
        "intraday":  "pipeline",
        "postmarket": "agent",
    }
    return mapping.get(phase, "pipeline")
```

### 8.2 调度注册

```python
# scheduler.py
import schedule

def register_auto_recommend(engine: AutoRecommendEngine, config: Config):
    times = config.auto_recommend_schedule  # "09:00,12:00,16:30"
    for t in times.split(","):
        t = t.strip()
        schedule.every().day.at(t).do(
            engine.run, phase=_detect_phase(t)
        )
```

### 8.3 阶段感知

```python
def _detect_phase(time_str: str) -> str:
    hour = int(time_str.split(":")[0])
    if hour < 10:
        return "premarket"
    elif hour < 14:
        return "intraday"
    else:
        return "postmarket"
```

---

## 9. 配置项

### `.env` 新增

```bash
# AI 自动荐股开关
AUTO_RECOMMEND_ENABLED=false

# 调度时间 (逗号分隔)
AUTO_RECOMMEND_SCHEDULE=09:00,12:00,16:30

# 候选股参数
AUTO_RECOMMEND_MAX_CANDIDATES=30       # 去重后最大候选数
AUTO_RECOMMEND_DEEP_ANALYZE_TOP=5      # 深度分析前 N 名

# 通道开关 (逗号分隔 ID)
AUTO_RECOMMEND_CHANNELS=theme,sector,factor,technical

# 市场范围 (当前仅支持 cn，后续扩展)
AUTO_RECOMMEND_MARKET=cn

# 过滤参数
AUTO_RECOMMEND_MIN_MARKET_CAP=50       # 最小市值 (亿)
AUTO_RECOMMEND_MIN_PRICE=3              # 最低股价
AUTO_RECOMMEND_MIN_TURNOVER=0.5         # 最低日均换手率 (%)
AUTO_RECOMMEND_SECTOR_LIMIT=2           # 同类通道同板块最多
AUTO_RECOMMEND_EXCLUDE_ST=true          # 排除 ST
AUTO_RECOMMEND_EXCLUDED_STOCKS=         # 额外排除列表 (逗号分隔)

# 分析模式 (auto=按时间阶段自动切换 / quick / pipeline / agent)
AUTO_RECOMMEND_ANALYSIS_MODE=auto

# 通知推送
AUTO_RECOMMEND_NOTIFY=true
AUTO_RECOMMEND_NOTIFY_CHANNELS=wechat,telegram

# 权重配置 (初期固定，后期引入自适应)
AUTO_RECOMMEND_WEIGHT_MODE=fixed       # fixed / adaptive

# T+1 校验
AUTO_RECOMMEND_T1_VERIFY=true           # 次日自动校验推荐结果
AUTO_RECOMMEND_T1_DECAY_THRESHOLD=0.6   # 通道连续失败率 > 60% 时权重衰减
```

### `config.py` 新增字段

```python
# src/config.py
auto_recommend_enabled: bool = False
auto_recommend_schedule: str = "09:00,12:00,16:30"
auto_recommend_max_candidates: int = 30
auto_recommend_deep_analyze_top: int = 5
auto_recommend_channels: str = "theme,sector,factor,technical"
auto_recommend_min_market_cap: float = 50.0
auto_recommend_min_price: float = 3.0
auto_recommend_min_turnover: float = 0.5
auto_recommend_sector_limit: int = 2
auto_recommend_exclude_st: bool = True
auto_recommend_excluded_stocks: str = ""
auto_recommend_analysis_mode: str = "pipeline"
auto_recommend_notify: bool = True
auto_recommend_notify_channels: str = "wechat,telegram"
```

### CLI 参数

```bash
python main.py --recommend              # 立即执行一次荐股
python main.py --recommend-quick        # 快速模式 (仅 Phase 2-3, 不深度分析)
python main.py --recommend-serve        # 启动定时荐股 (结合 --serve)
```

---

## 10. 文件变更清单

### 新增文件

| 文件 | 职责 | 预估行数 |
|------|------|----------|
| `src/services/auto_recommend/engine.py` | 主编排器 | ~250 |
| `src/services/auto_recommend/candidate_discovery.py` | 多通道发现工厂 + 各通道实现 | ~400 |
| `src/services/auto_recommend/scorer.py` | 评分/排序逻辑 | ~200 |
| `src/services/auto_recommend/report.py` | 报告生成 + 通知格式化 | ~250 |
| `docs/auto-recommend-design.md` | 本文档 | — |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/config.py` | 新增 12 个配置字段 |
| `src/scheduler.py` | 注册自动荐股定时任务 |
| `main.py` | CLI 参数 `--recommend` `--recommend-quick` |
| `src/notification.py` | 新增 `generate_recommend_report()` |
| `.env.example` | 新增配置项模板 |
| `docs/CHANGELOG.md` | 追加 `[Unreleased]` 变更记录 |

---

## 11. 风险与控制

### 11.1 已知风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 画线噪声 (技术面假信号) | 推荐质量下降 | 多通道交叉验证，单通道不决定最终排位 |
| 题材一日游 (消息驱动) | 追高被套 | 板块持续 ≥ 3 日才确认为主线；热门追高必提示风险 |
| 流动性陷阱 (推荐的股买不到) | 无法执行 | 排除日均换手率 < 0.5%、成交额 < 5000 万的个股 |
| LLM 调用成本 (深度分析阶段) | Token 暴涨 | 提供 `quick` 模式跳过 Agent，`pipeline` 模式单次 LLM |
| 数据源依赖 (盘中使用实时数据) | 分析不完整 | 降级为仅技术分析 + 新闻 (跳过资金流/筹码) |
| 同质化推荐 (多通道找到同一股票) | 信息冗余 | 去重时保留最高分来源，标注多通道共振加分 |

### 11.2 质量护栏

1. **最低置信度门限**：sentiment_score < 50 的股票不进入深度分析
2. **多通道共振加分**：同时被 ≥ 2 个通道发现的股票，综合分 × 1.2
3. **结果验证**：荐股后 T+1 自动校验涨跌幅，记录到 DecisionSignal
4. **撤单阈值**：连续 5 次推荐失败（T+1 下跌 > 3%），通道权重自动衰减 20%
5. **人工复核**：Web UI 提供"确认/忽略"操作，反馈影响权重

### 11.3 回滚方式

```
1. 关闭 .env 开关: AUTO_RECOMMEND_ENABLED=false
2. 移除定时注册: scheduler.py 中注释相关行
3. 代码回滚: git revert <commit>
```

---

## 12. 已确认的设计决策

以下决策基于与用户的讨论确认：

### D1: 全市场批量 K 线数据 → 对接 tickflow

直接对接 `tickflow` 的批量 K 线查询接口（如 `batch_kline` / `daily_batch`），不再逐股调 `get_daily_history`。

- 实现位置：新增 `data_provider/auto_recommend_kline.py` 或直接扩展 `tickflow` 的 adapter
- 批量拉取全市场近 120 日日 K 数据，缓存在内存/临时 DB 中供全通道共享
- Tickflow 已有的批量接口可规避数据源限流问题

### D2: 盘前扫描数据策略

盘前 09:00 扫描时：

- **题材通道 (theme)**：基于隔夜新闻（美股收盘、政策发布、国际事件）
- **技术通道 (technical)**：基于**昨日收盘 K 线数据**计算全部指标
  - 量比 = 昨日量 / 5 日均量
  - 突破判定基于已确认的昨日收盘价
  - 不包含盘中实时信号（盘前无当日数据）
- **板块通道 (sector)**：基于昨日收盘板块排名

### D3: 分析模式自动切换

根据时间阶段自动切换：

| 阶段 | 模式 | 原因 |
|------|------|------|
| premarket (09:00) | `quick` | 当日 K 线未生成，快速出信号 |
| intraday (12:00) | `pipeline` | 半日数据可做技术分析 |
| postmarket (16:30) | `agent` (specialist) | 数据完整，全量深度分析 |

配置项 `AUTO_RECOMMEND_ANALYSIS_MODE=auto` 启用自动切换。

### D4: 权重策略

- **初期**：固定权重（参见 5.2 节的默认权重表）
- **后期**：根据 T+1 校验数据和通道历史胜率，引入自适应权重
- 切换时机：积累 ≥ 100 条推荐记录后

### D5: 市场范围

**当前仅支持 A 股 (cn)**。所有通道的股票池、过滤参数、板块分类均按 A 股规则。后续扩展港股/美股时需分市场配置。

### D6: 用户分组 A/B 测试

初始上线采用分组测试策略：

```
用户分组:
  A 组 (10%):  收到每日 AI 荐股推送
  B 组 (10%):  收到每日 AI 荐股推送 + Web UI 可查看详细报告
  C 组 (80%):  对照组，不推送荐股 (keep 现有体验)

衡量指标:
  - 用户次日查看推送率
  - 推荐股票的 T+1 实际涨跌幅 vs 基准
  - 用户主动点击/问股转化率
  - 用户反馈标签 (点赞/踩)
```

分组逻辑复用现有的 `config.auto_recommend_group` 字段（或基于用户 ID 哈希）：

```python
def _get_user_group(user_id: str) -> str:
    h = hash(f"auto_recommend_{user_id}") % 100
    if h < 10: return "A"       # 推送
    if h < 20: return "B"       # 推送 + Web UI
    return "C"                  # 对照组
```

### D7: T+1 自动校验与权重衰减

每次推荐后，T+1 交易日自动校验：

```python
@dataclass
class RecommendationRecord:
    stock_code: str
    channel: str                # 来源通道 (theme/sector/factor/technical)
    signal: str                 # buy / hold
    confidence: float           # 推荐时的置信度
    recommended_price: float    # 推荐时价格
    recommended_at: datetime    # 推荐时间
    verified: bool = False      # 是否已验证
    t1_price: float = 0.0       # T+1 收盘价
    t1_return: float = 0.0      # T+1 涨跌幅
    success: bool = False       # T+1 是否上涨
```

权重衰减逻辑：

```python
class AdaptiveWeights:
    """通道自适应权重管理器"""

    def __init__(self, window_size: int = 50):
        self.window_size = window_size

    def update_channel_weights(
        self,
        channel_records: Dict[str, List[RecommendationRecord]],
        current_weights: Dict[str, float],
        decay_threshold: float = 0.6,  # 连续失败率 > 60% 触发衰减
    ) -> Dict[str, float]:
        new_weights = dict(current_weights)

        for channel, records in channel_records.items():
            recent = records[-self.window_size:]
            if not recent or len(recent) < 10:
                continue  # 数据不足，保持权重

            failures = sum(1 for r in recent if not r.success)
            fail_rate = failures / len(recent)

            if fail_rate > decay_threshold:
                # 通道失效：权重 × 0.5，等比分配给其他通道
                penalty = new_weights[channel] * 0.5
                new_weights[channel] *= 0.5
                total_others = sum(v for k, v in new_weights.items() if k != channel)
                for k in new_weights:
                    if k != channel:
                        new_weights[k] += penalty * (new_weights[k] / total_others)

        return new_weights
```

---

## 附录 A：与现有模块的复用关系

```
AutoRecommendEngine
├── MarketContextCollector
│   ├── get_market_indices()         ← data_provider
│   ├── get_sector_rankings()        ← data_provider
│   └── market_strategy.py          ← src/core/market_strategy.py
├── CandidateDiscovery
│   ├── search_service.search()      ← src/search_service.py
│   ├── alphasift_service.screen()   ← src/services/alphasift_service.py
│   ├── factor_tools                 ← src/agent/tools/factor_tools.py
│   └── stock_analyzer               ← src/stock_analyzer.py
├── Scorer
│   ├── strategies/*.yaml            ← strategies/ 目录
│   └── skill_manager                ← src/agent/skills/
├── DeepAnalysis
│   ├── pipeline.process_single_stock() ← src/core/pipeline.py
│   └── agent_orchestrator.run()       ← src/agent/orchestrator.py
└── Output
    ├── decision_signal_service      ← src/services/decision_signal_service.py
    ├── notification_service         ← src/notification.py
    └── scheduler                    ← src/scheduler.py
```

## 附录 B：最小可行版本 (MVP) 裁剪

如果希望尽快上线，可以做以下裁剪：

```
MVP 范围:
├── 通道: 仅 sector + factor (不依赖新闻批量接口)
├── 阶段: 仅盘后 (16:30)，避开盘中数据依赖
├── 深度分析: pipeline 模式，不启用 Agent
├── 输出: 仅 Telegram 推送，不做持久化
└── 评分: 固定权重，不自适应

MVP 不做:
├── 盘中扫描
├── 题材/技术面批量扫描 (需要新数据接口)
├── Agent 模式深度分析
├── Web UI 页面
└── 自适应权重

MVP 工作量估算:
├── engine.py      ~150 行
├── candidates.py   ~200 行 (2 个通道)
├── scorer.py       ~100 行
├── report.py       ~150 行
├── scheduler.py      ~30 行 (修改)
├── config.py         ~20 行 (修改)
├── main.py           ~20 行 (修改)
└── notification.py   ~80 行 (修改)
└── 总估算: 约 750 行代码, 4-6 小时
```
