# 技术报告：深度研究与完整报告的实现机制

> 本文档深入分析项目中两条核心分析轨道的架构、流程、策略参与度与设计取舍。
>
> - 深度研究 (Deep Research) — `/research` 命令
> - 完整报告 (Full Report) — `/analyze full` / `report_type=full`
>
> 编写日期：2026-06-13

---

## 目录

1. [概述](#1-概述)
2. [深度研究](#2-深度研究-deep-research)
3. [完整报告](#3-完整报告-full-report)
4. [双轨对比](#4-双轨对比)
5. [策略/Skill 的参与度](#5-策略skill-的参与度)
6. [设计取舍与演进方向](#6-设计取舍与演进方向)

---

## 1. 概述

当前项目存在两条**独立**的分析轨道，服务于不同用户场景：

| 维度 | 深度研究 (Deep Research) | 完整报告 (Full Report) |
|------|------------------------|----------------------|
| 入口 | `/research` 命令 / `POST /api/v1/agent/research` | `/analyze <code> full` / `POST /api/v1/analysis/analyze` |
| 核心类 | `ResearchAgent` | `StockAnalysisPipeline` + `GeminiAnalyzer` |
| 是否需 Agent 模式 | 是 (`AGENT_MODE=true`) | 否 |
| 输出格式 | 自由 Markdown 研究报告 | 结构化 JSON Dashboard + 格式化通知 |
| YAML 策略/Skill 体系 | **不使用** | **不使用**（Agent 模式叠加时可间接使用） |
| 典型耗时 | ~30-180s | ~10-60s |

---

## 2. 深度研究 (Deep Research)

### 2.1 涉及文件

| 文件 | 行号 | 职责 |
|------|------|------|
| `bot/commands/research.py` | 全文件 | Bot 命令入口，参数解析、结果组装与截断 |
| `api/v1/endpoints/agent.py` | — | REST API 入口 `POST /api/v1/agent/research` |
| `src/agent/research.py` | 全文件 | **核心** — `ResearchAgent` 三阶段管道 |
| `src/agent/runner.py` | — | 共享 `run_agent_loop()` ReAct 循环 |
| `src/agent/llm_adapter.py` | — | `LLMToolAdapter` 多供应商 LLM 调用 |
| `src/agent/factory.py` | — | `get_tool_registry()` 构建全局工具注册表 |

### 2.2 架构：独立三阶段管道

`ResearchAgent` **不**属于 `AgentOrchestrator` 多 Agent 管道体系。它是一个独立的、自包含的 Agent，拥有自己的三阶段流程：

```
┌──────────────────────────────────────────────────────────────┐
│  Phase 1: 查询分解 (Decompose)                                │
│  纯文本 LLM 调用                                              │
│  Prompt: "将查询分解为 3-5 个可搜索的子问题"                    │
│  输出: JSON {"questions": ["q1", "q2", ...]}                  │
│  超时: 15s | temperature: 0.3 | max_tokens: 400              │
├──────────────────────────────────────────────────────────────┤
│  Phase 2: 逐子问题研究 (循环, 最多 5 个)                       │
│  每个子问题:                                                  │
│  1. 构建 system prompt（含剩余 token budget 作为上下文）       │
│  2. 过滤工具注册表 → 仅暴露 7 个工具                            │
│  3. 调用 run_agent_loop()，最多 4 步 ReAct                     │
│  4. 收集 finding + token 用量                                  │
│  5. 检查 token 预算 & 墙钟超时                                  │
├──────────────────────────────────────────────────────────────┤
│  Phase 3: 综合报告 (Synthesize)                                │
│  纯文本 LLM 调用                                              │
│  输出结构: Executive Summary → Key Findings →                 │
│            Detailed Analysis → Risk Factors → Conclusion      │
│  超时: 30s | temperature: 0.3 | max_tokens: 2000             │
└──────────────────────────────────────────────────────────────┘
```

详细代码位置：

- 完整入口：`ResearchAgent.research()` (`src/agent/research.py:70-211`)
- 分解实现：`_decompose_query()` (`src/agent/research.py:292-338`)
- 子问题研究：`_research_sub_question()` (`src/agent/research.py:340-410`)
- 综合合成：`_synthesise_report()` (`src/agent/research.py:412-460`)

### 2.3 可用工具（固定 7 个）

定义在 `ResearchAgent.tool_names` (`src/agent/research.py:48-56`):

| 工具 | 用途 |
|------|------|
| `search_stock_news` | 搜索股票相关新闻 |
| `search_comprehensive_intel` | 综合情报检索 |
| `get_stock_info` | 股票基本信息 |
| `get_realtime_quote` | 实时行情 |
| `get_daily_history` | 日 K 历史数据 |
| `get_sector_rankings` | 板块排名 |
| `get_market_indices` | 市场指数 |

> **关键**：不包含 `analyze_trend`、`get_chip_distribution`、`analyze_pattern`、`get_factor_scores`、`calculate_ma` 等分析类工具。设计上聚焦"信息搜集"而非"技术计算"。

### 2.4 预算与超时机制

多层嵌套的预算管理：

```
ResearchAgent.research(timeout_seconds=180s)
  ├─ Phase 1: _decompose_query(clamp 15s)
  ├─ Phase 2: loop over sub-questions
  │   └─ _research_sub_question(remaining timeout)
  │       └─ run_agent_loop(max_steps=4, max_wall_clock=remaining)
  │           └─ per-step LLM: timeout kwarg
  │           └─ per-step tool batch: tool_call_timeout
  └─ Phase 3: _synthesise_report(clamp 30s)
```

| 参数 | 默认值 | 配置项 | 代码位置 |
|------|--------|--------|----------|
| token_budget | 30,000 | `agent_deep_research_budget` | `research.py:67` |
| overall_timeout | 180s | `agent_deep_research_timeout` | `research.py:105` |
| decompose timeout | clamp 15s | — | `research.py:316` |
| sub-question max_steps | 4 | — | `research.py:380` |
| synthesis timeout | clamp 30s | — | `research.py:444` |
| runner min_step_budget | 8s | — | `runner.py` |

Token 预算在 Phase 2 循环中逐子问题检查：`if tokens_used >= self.token_budget: break`。

### 2.5 输出结构

`ResearchResult` (`src/agent/research.py:472-483`):

```python
@dataclass
class ResearchResult:
    success: bool          # 是否成功
    report: str            # Markdown 研究报告全文
    sub_questions: [str]   # 分解出的子问题列表
    findings_count: int    # 收集到的发现数量
    total_tokens: int      # 全部阶段消耗 tokens
    duration_s: float      # 墙钟耗时
    error: str | None      # 错误信息
    timed_out: bool        # 是否超时终止
```

Bot 响应组装 (`bot/commands/research.py:121-137`):

```
🔬 Deep Research Report
Stock: 600519
Sub-questions: 4 | Sources: 4
Time: 45s | Tokens: 12,345
────────────────────────────────────────

[Markdown report 内容]

(超过 4000 字符时截断)
```

---

## 3. 完整报告 (Full Report)

### 3.1 涉及文件

| 层 | 文件 | 行号 | 职责 |
|----|------|------|------|
| 入口 | `main.py` | — | CLI 触发 |
| 入口 | `src/scheduler.py` | — | 定时任务触发 |
| 入口 | `bot/commands/analyze.py` | — | Bot 命令 (`/analyze full`) |
| 入口 | `api/v1/endpoints/analysis.py` | — | REST API |
| 调度 | `src/core/pipeline.py` | 全文件 | 流程编排、并发、异常处理 |
| 调度 | `src/services/analysis_service.py` | — | API 层 wrapper |
| 数据 | `data_provider/` | — | 多源数据获取与 fallback |
| 技术分析 | `src/stock_analyzer.py` | 全文件 | `StockTrendAnalyzer` |
| LLM | `src/analyzer.py` | 2664 | `GeminiAnalyzer.analyze()` |
| 后处理 | `src/analyzer.py` | 多处 | 字段填充、校验、稳定化 |
| 上下文 | `src/services/analysis_context_builder.py` | — | `AnalysisContextPack` 组装 |
| 渲染 | `src/notification.py` | 1020-1337 | `generate_dashboard_report()` |
| Schema | `src/schemas/report_schema.py` | — | JSON Schema |
| 报告语言 | `src/report_language.py` | — | 中英双语标签 |
| 推送 | `src/notification_sender/` | — | 各渠道派发 |

### 3.2 完整流水线

```
┌──────────────────────────────────────────────────────────────────┐
│  StockAnalysisPipeline.process_single_stock()                     │
│  pipeline.py:2163                                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ① 数据收集（并发执行）                                            │
│  ├─ DataFetcherManager.get_realtime_quote()                       │
│  ├─ DataFetcherManager.get_daily_history()                        │
│  ├─ DataFetcherManager.get_chip_distribution()                    │
│  ├─ SearchService.search_news()                                   │
│  └─ SearchService.search_comprehensive_intel()                    │
│                                                                   │
│  ② 技术分析                                                       │
│  └─ StockTrendAnalyzer.analyze()                                  │
│     ├─ 均线: MA5/10/20/60                                        │
│     ├─ MACD: DIF/DEA/Histogram                                   │
│     ├─ RSI: RSI6/12/24                                           │
│     ├─ 量价分析: volume_ratio, volume_status                     │
│     ├─ 支撑/阻力: 自动推导                                        │
│     ├─ 乖离率: bias_ma5/ma10                                     │
│     └─ 信号评分: signal_score (0-100)                            │
│                                                                   │
│  ③ Agent 模式分支 (config.agent_mode)                             │
│  ├─ agent_mode=True → AgentOrchestrator.run()                    │
│  │   (Technical → Intel → Risk → Decision)                       │
│  └─ agent_mode=False → GeminiAnalyzer.analyze() (单次 LLM)        │
│                                                                   │
│  ④ LLM 分析 (GeminiAnalyzer.analyze)                              │
│  ├─ System Prompt: Decision Dashboard v2.0 JSON schema            │
│  ├─ User Prompt: 拼接所有数据源 (行情/技术/筹码/资金流/新闻)       │
│  ├─ 模型调用: _call_litellm() — 多模型 fallback 链               │
│  ├─ JSON 校验: _validate_json_response()                         │
│  └─ 重试: max 2 次 + 完整性检查                                    │
│                                                                   │
│  ⑤ 结果后处理                                                     │
│  ├─ normalize_chip_structure_availability()                       │
│  ├─ fill_price_position_if_needed()                              │
│  ├─ stabilize_decision_with_structure()                          │
│  └─ check_content_integrity()                                    │
│                                                                   │
│  ⑥ 报告类型分支 (render layer only)                                │
│  ├─ ReportType.FULL  → generate_dashboard_report()               │
│  ├─ ReportType.SIMPLE → generate_single_stock_report()           │
│  └─ ReportType.BRIEF → generate_brief_report()                   │
│                                                                   │
│  ⑦ 通知推送                                                       │
│  └─ NotificationService 各渠道派发                                │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 LLM 分析是单次调用

`GeminiAnalyzer.analyze()` (`src/analyzer.py:2664`) — 核心方法。

**关键发现**：无论 `report_type` 为何值，LLM 调用的 prompt **完全一致**。报告类型的差异仅存在于通知渲染层（`generate_*` 方法）。

LLM 调用的完整流程：

1. **System Prompt 选择**：
   - 优先：`SYSTEM_PROMPT` (`analyzer.py:1843`) — Decision Dashboard v2.0
   - 降级：`LEGACY_DEFAULT_SYSTEM_PROMPT` (`analyzer.py:1674`)

2. **User Prompt 组装** (`_format_prompt()`, `analyzer.py:2877`)：
   - `market_phase_context` — 市场阶段（开盘/盘中/盘后）
   - `technical_data` — 均线/MACD/RSI/量价/支撑阻力
   - `realtime_quote` — 最新行情
   - `fundamentals` — 财务数据（若有）
   - `chip_distribution` — 筹码分布
   - `capital_flow` — 资金流
   - `news_context` — 新闻摘要
   - `trend_analysis_preview` — 趋势分析预览
   - `output_requirements` — JSON schema 约束

3. **模型调用** (`_call_litellm()`, `analyzer.py:2450`)：
   - 多模型 fallback 链
   - `simple-shuffle` 路由策略
   - 2 次自动重试

4. **JSON 校验与修复**：
   - `_validate_json_response()` — 语法校验
   - `check_content_integrity()` — 字段完整性检查 (`analyzer.py:195`)
   - `_build_integrity_complement_prompt()` — 缺失字段自动补全
   - 最多 2 次完整性补全重试

### 3.4 技术分析引擎

`StockTrendAnalyzer` (`src/stock_analyzer.py`) 计算以下指标：

| 指标组 | 具体指标 | 用途 |
|--------|----------|------|
| 均线 | MA5/10/20/60 | 趋势判断 |
| 均线排列 | bullish/cross/neutral/bearish | 多空判断 |
| MACD | DIF/DEA/BAR | 动量确认 |
| RSI | RSI6/12/24 | 超买超卖 |
| 乖离率 | bias_ma5/bias_ma10 | 偏离程度（>5%禁止追高） |
| 量价 | volume_ratio/volume_status | 量能配合 |
| 支撑阻力 | support_levels/resistance_levels | 关键价位 |
| 信号评分 | signal_score (0-100) | 综合评分 |

这些计算结果被序列化为 `trend_analysis_preview` 注入 LLM prompt。

### 3.5 完整报告 vs 精简报告的差异

LLM 输出相同的 JSON Dashboard，差异仅在渲染层。

`generate_dashboard_report()` (`src/notification.py:1020-1337`) 包含的板块：

| 板块 | 完整报告 (FULL) | 精简报告 (SIMPLE) |
|------|:---------------:|:-----------------:|
| 汇总统计表（多股时） | ✅ | ✅ |
| 核心结论 (Core Conclusion) | ✅ | ✅ |
| 市场快照 (OHLC) | ✅ | ✅ |
| 情报 (Intelligence) | ✅ | ✅（字段截断 60-100 字） |
| 狙击点 (Sniper Points) | ✅ 完整表格 | ✅ 简化表格 |
| 持仓建议 (Position Advice) | ✅ | ✅ |
| **数据视角 (Data Perspective)** | **✅** | ❌ |
| ├─ trend_status | ✅ | ❌ |
| ├─ price_position (MA/乖离率/支撑阻力) | ✅ | ❌ |
| ├─ volume_analysis | ✅ | ❌ |
| └─ chip_structure | ✅ | ❌ |
| **作战计划 (Battle Plan)** | **✅ 完整版** | **❌ 仅 sniper_points** |
| ├─ position_strategy | ✅ | ❌ |
| └─ action_checklist | ✅ | ❌ |
| 基本面 (financial/return/sectors) | ✅ | ✅ |

### 3.6 Agent 模式叠加

当 `config.agent_mode=True` 时，分析可走 Agent 管道：

```
StockAnalysisPipeline._analyze_with_agent() (pipeline.py:968)
  → AgentOrchestrator.run()
    → 模式: quick / standard / full / specialist
  → 输出: AgentResult.dashboard (与 GeminiAnalyzer 同结构)
  → 降级: Agent 失败时回退到 GeminiAnalyzer
```

四种 Agent 模式：

| 模式 | Agent 链 | 适用 |
|------|----------|------|
| `quick` | Technical → Decision | 最快，2 次 LLM 调用 |
| `standard` | Technical → Intel → Decision | 默认 |
| `full` | Technical → Intel → Risk → Decision | 含风险扫描 |
| `specialist` | 以上 + SkillAgent × 最多 3 个 | 含策略技能评估 |

> 注意：Agent 模式不是完整报告的固有特性。即使 `agent_mode=True`，完整报告与精简报告在 Agent 层的行为完全一致 —— 差异依然仅在渲染层。

---

## 4. 双轨对比

| 对比维度 | 深度研究 | 完整报告 |
|---------|---------|---------|
| **核心目标** | 自由形式信息调研，挖掘事实和上下文 | 标准化诊股，产生可操作的买卖信号 |
| **架构** | 独立三阶段 Agent | 数据管道 + 单次/多次 LLM 调用 |
| **归属** | `ResearchAgent` 独立运行 | `StockAnalysisPipeline` + AgentOrchestrator（可选） |
| **技术分析** | ⛔ 不计算指标 | ✅ 全量 MA/MACD/RSI/量价/支撑阻力 |
| **筹码分析** | ⛔ 无 | ✅ 筹码分布、集中度、获利比例 |
| **资金流** | ⛔ 无 | ✅ 资金流入流出 |
| **基本面** | ⛔ 无 | ✅ 财务数据（若有） |
| **策略/Skill** | ⛔ 完全不使用 | ⛔ 默认不使用（Agent 模式叠加时可用） |
| **输出格式** | 自由 Markdown | 结构化 JSON Dashboard |
| **买卖信号** | ⛔ 无 | ✅ buy/hold/sell + 置信度 + 价格位 |
| **Token 预算** | 硬限制 30K | 隐式（max_steps 控制） |
| **墙钟超时** | 180s | 600s（ORCHESTRATOR_TIMEOUT_S） |
| **重试/降级** | 失败即返回 | 多级降级（数据源→模型→分析模式） |
| **通知推送** | ⛔ 不推送 | ✅ 多渠道推送 + 聚合报告 |
| **多股批量** | ⛔ 不支持 | ✅ 并发执行 + 汇总统计 |
| **市场阶段感知** | ⛔ 否 | ✅ 是（开/盘中/盘后不同约束） |
| **风险否决** | ⛔ 否 | ✅ Agent 模式时 RiskAgent 可否决 |
| **历史/记忆** | ⛔ 无状态 | ✅ 有历史校准 + 对话上下文 |
| **典型用户** | 需要深度背景调研的投资者 | 需要每日标准化跟踪的投资者 |

---

## 5. 策略/Skill 的参与度

| 场景 | YAML Skill 参与？ | 具体路径 |
|------|:-----------------:|----------|
| `/research` | **⛔ 否** | ResearchAgent 固定使用 7 个工具，不加载 Skill |
| `/analyze full` (非 Agent 模式) | **⛔ 否** | GeminiAnalyzer 单次 LLM 调用，不涉及 Skill |
| `/analyze full` (Agent 模式) | **间接参与** | AgentOrchestrator 在 `specialist` 模式插入 SkillAgent；SkillRouter 根据市场状态选技能 |
| `/ask` (问股) | **✅ 是** | 默认激活 `bull_trend`；可通过参数指定任意 Skill |

Skill 体系当前是 Agent 模式的"可选增强"而非分析管线的必要组成部分。三条完全独立的路径：

```
路径 A: /research  →  ResearchAgent         →  Markdown 报告
路径 B: /analyze   →  Pipeline + GeminiAnalyzer → JSON Dashboard
路径 C: /ask       →  Pipeline + AgentOrchestrator → JSON Dashboard（含 Skill 评估）
```

---

## 6. 设计取舍与演进方向

### 6.1 已观察到的设计取舍

1. **Research 独立于 Skill 体系**：ResearchAgent 的设计目标不同于标准分析 —— 它做信息搜集和事实调研，而非交易信号生成。引入 Skill 体系反而会限制其灵活性。

2. **报告类型差异仅限于渲染层**：LLM 调用完全一致，无论 report_type 是 simple/full/brief。这是一个务实的选择 —— 复用一个高成本的 LLM 调用输出完整 JSON，再按需裁剪格式化输出。

3. **Agent 模式是独立开关**：与 report_type 正交。甚至 pipeline 层面的 "analyze_stock" 函数只有一个，同时服务于 SIMPLE 和 FULL 两种报告类型。

4. **"完整报告"不意味着"完整策略"**：即使 FULL REPORT，默认也不走 Skill 体系。要同时获得完整报告 + 策略评估，必须开启 `agent_mode` 且管道模式为 `specialist`。

### 6.2 潜在演进方向

| 方向 | 设想 | 影响面 |
|------|------|--------|
| Research 接入 Skill | 让 ResearchAgent 的 `tool_names` 可扩展，或支持注入 Skill | 后端 ResearchAgent |
| Full Report + Skill 默认联动 | `report_type=full` 时自动走 `specialist` Agent 模式 | pipeline、config |
| LLM 按 report_type 差异化 | 对 SIMPLE 用更短的 prompt，对 FULL 要求更详细的 JSON | analyzer.py |
| Strategy Notes 自动生成 | 从 YAML 配置生成文档 | scripts/ 工具链 |
| 策略回测结果注入 | 将 `agent_skill_backtest` 结果注入 SkillAgent 的系统 prompt | skill_agent.py、aggregator.py |

---

## 附录 A：关键代码快速索引

| 功能 | 文件 | 行号 |
|------|------|------|
| Research 入口 | `bot/commands/research.py` | 53 |
| Research 核心 | `src/agent/research.py` | 70 |
| 查询分解 | `src/agent/research.py` | 292 |
| 子问题研究 | `src/agent/research.py` | 340 |
| 综合合成 | `src/agent/research.py` | 412 |
| Pipeline 主入口 | `src/core/pipeline.py` | 2163 |
| LLM 分析 | `src/analyzer.py` | 2664 |
| 技术分析 | `src/stock_analyzer.py` | — |
| 完整报告渲染 | `src/notification.py` | 1020 |
| 精简报告渲染 | `src/notification.py` | 1641 |
| 简洁报告渲染 | `src/notification.py` | 1579 |
| 报告类型枚举 | `src/enums.py` | — |
| Agent 管道模式 | `src/agent/orchestrator.py` | 55 |
| Skill 选择路由 | `src/agent/skills/router.py` | 28 |
| Skill 默认配置 | `src/agent/skills/defaults.py` | 92-295 |
| 报告 Schema | `src/schemas/report_schema.py` | — |

## 附录 B：配置文件索引

| 配置项 | 默认值 | 影响 |
|--------|--------|------|
| `AGENT_MODE` | `false` | 是否启用 Agent 分析管道 |
| `AGENT_SKILLS` | `[]` | 手动指定激活的 Skill ID 列表 |
| `agent_deep_research_budget` | 30000 | 深度研究 token 预算 |
| `agent_deep_research_timeout` | 180 | 深度研究超时（秒） |
| `agent_skill_routing` | `"auto"` | Skill 路由模式 (auto/manual) |
| `REPORT_TYPE` | `"simple"` | 默认报告类型 |
| `ORCHESTRATOR_TIMEOUT_S` | 600 | Agent 管道超时（秒） |
| `agent_orchestrator_mode` | `"standard"` | Agent 管道模式 |
