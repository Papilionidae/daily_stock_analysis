# 多因子选股 (Multi-Factor)

## 基本信息

| 字段 | 值 |
|------|-----|
| 策略 ID | `multi_factor` |
| 名称 | 多因子选股 |
| 分类 | 框架 (framework) |
| 优先级 | 15 |
| 默认激活 | ❌ |
| 关联理念 | 第 2 条（趋势交易）、第 6 条（估值关注）、第 7 条（强势趋势股放宽） |
| 市场状态 | `trending_up`, `sideways` |
| 别名 | 多因子、因子选股、量化选股、factor |

## 核心逻辑

价值 + 质量 + 动量 + 反转 + 规模 + 波动 + 流动性综合打分排序，行业中性化，适用于横截面选股与个股多维评估。

**与 `growth_quality` 的区别**：`growth_quality` 是单股质量评分；本策略关注个股在横截面（同行业同期所有股票）中的相对分位数。

### 判断链

1. **因子定义（七类）**

| 因子 | 计算方式 | 方向 |
|------|----------|------|
| 价值 (value) | EP = 1 / PE_TTM | 高 = 好 |
| 质量 (quality) | ROE_TTM | 高 = 好 |
| 动量 (momentum) | MOM_60 = 60 日累计收益 | 高 = 好 |
| 反转 (reversal) | -REV_5 = 过去 5 日跌幅取负 | 超跌 = 利好 |
| 规模 (size) | LN_MV = ln(总市值) | 大 = 好 |
| 波动 (volatility) | 20 日收益率波动率（取负） | 低 = 好 |
| 流动性 (liquidity) | 20 日均换手率（取负） | 高 = 好（A 股 alpha 来源） |

2. **数据获取**
   - 调用 `get_factor_scores(universe=<股票列表>, factors=[...], neutral="industry")`
   - 返回因子 Z-score（行业中性化、去极值后）
   - 自动处理缺失值（行业中位数填充）

3. **因子合成（必须显式传权重）**

推荐权重模板：

| 场景 | 价值 | 质量 | 动量 | 反转 | 规模 | 波动 | 流动性 |
|------|------|------|------|------|------|------|--------|
| 均衡 | 0.15 | 0.25 | 0.20 | 0.10 | 0.10 | 0.10 | 0.10 |
| 熊市 | 0.25 | 0.20 | 0.10 | 0.20 | 0.10 | 0.10 | 0.05 |
| 牛市 | 0.10 | 0.25 | 0.30 | 0.05 | 0.10 | 0.10 | 0.10 |

综合得分 = Σ (因子 Z-score × 权重)，结果为标准正态分布。

4. **个股评估评分映射**

| 综合分 | 评级 | 调整 |
|--------|------|------|
| > 1.5 | 高 alpha | `sentiment_score +15` |
| 0.5 ~ 1.5 | 中 alpha | `sentiment_score +8` |
| -0.5 ~ 0.5 | 中性 | `sentiment_score ±0` |
| -1.5 ~ -0.5 | 低 alpha | `sentiment_score -8` |
| < -1.5 | 负 alpha | `sentiment_score -15` |

5. **横截面选股**
   - 调用 `get_universe_screen(factors={...}, top_n=30, industry_limit=5)`
   - 返回 30 只股票，每行业最多 5 只

6. **再平衡机制**
   - 月度：每月第一个交易日重新计算因子
   - 调仓幅度：单股偏离目标权重 5% 才调整
   - 持仓上限：单股 ≤ 5%，单行业 ≤ 30%

## 技术指标与数据依赖

| 数据/工具 | 用途 |
|-----------|------|
| `get_factor_scores` | 七因子 Z-score 计算 |
| `get_universe_screen` | 横截面选股输出 |
| `get_daily_history` | 动量/反转/波动率计算 |
| `get_realtime_quote` | 实时市值、换手率 |

## 适用场景

- **适合**：低频组合管理、月度再平衡、选股池过滤
- **不适合**：日内/短线交易、因子衰减期的风格切换行情
- **市场阶段**：均衡或趋势市中稳定；极端风格切换时可能短期失效

## 与上下游策略的关系

| 策略 | 关系 |
|------|------|
| `growth_quality` | 互补：本策略只看横截面相对位置，`growth_quality` 做单股绝对质量评价 |
| `momentum_12_1` | 配合：动量因子可纳入本策略的多因子框架 |
| `expectation_repricing` | 补充：因子评分后需要预期分析来确认催化时机 |

## 在管道中的角色

- **specialist 模式**：当市场状态为 `trending_up` 或 `sideways` 时可选
- **横截面视角**：本策略提供独特的"个股在同行业中的相对位置"视角，与其他策略的纵向分析互补
- **低频定位**：适合作持仓组合的月度体检，不适合每日问股

## YAML 配置原文

```yaml
# 多因子选股 / Multi-Factor Stock Selection
name: multi_factor
display_name: 多因子选股
description: 价值+质量+动量+反转+规模+波动+流动性综合打分排序，
  行业中性化，适用于横截面选股与个股多维评估。
category: framework
core_rules: [2, 6, 7]
required_tools:
  - get_factor_scores
  - get_universe_screen
  - get_daily_history
  - get_realtime_quote
default_priority: 15
market_regimes: [trending_up, sideways]
aliases: [多因子, 因子选股, 量化选股, factor]

instructions: |
  **多因子选股策略（Multi-Factor Selection）**

  与 `growth_quality` 的差异：growth_quality 是单股质量评分；
  本策略关注个股在横截面（同行业同期所有股票）中的相对分位数。

  适用场景：
  - 对单一个股做"横截面位置评估"——不是孤立看它，而是看它在同行业
    同期所有股票中的相对分位数。
  - 用于发现被低估的高质量标的（低估值+高ROE+合理动量）。
  - 适合做"组合再平衡"——每月初评估持仓中个股的多因子得分变化。
  - **本策略只输出"个股的横截面评分"和"top N 选股建议"，不输出具体持仓比例。
    最终仓位/调仓时机由用户/其他工具决定。**

  分析框架：

  1. **因子定义（七类）**
     - 价值因子（value）：EP = 1 / PE_TTM。
     - 质量因子（quality）：ROE_TTM。
     - 动量因子（momentum）：MOM_60 = 60日累计收益。
     - 反转因子（reversal）：-REV_5 = 过去5日跌幅（取负即"超跌=利好"）。
     - 规模因子（size）：LN_MV = ln(总市值)。
     - 波动因子（volatility）：20日收益率波动率（取负）。
     - 流动性因子（liquidity）：20日均换手率（取负 = 越高越好，因为 A 股换手率是 alpha 来源之一）。

  2. **数据获取（使用 get_factor_scores 工具）**
     - 调用 `get_factor_scores(universe=<股票列表>, factors=["value","quality","momentum"], neutral="industry")`。
     - 工具会返回每只股票的因子 Z-score（行业中性化、去极值后）。
     - 工具自动处理缺失值（用行业中位数填充或标记 factor_missing）。
     - 工具输出同时包含 factor_quantiles（行业内分位数）和 data_quality 标志。

  3. **因子合成（必须显式传权重，工具不接受"默认等权"）**
     - 调用 `get_universe_screen` 时**必须**在 `factors` 参数中传完整权重（和=1.0）。
     - 推荐权重模板：
       - 价值 0.15 + 质量 0.25 + 动量 0.20 + 反转 0.10 + 规模 0.10 + 波动 0.10 + 流动性 0.10 = 1.0
       - 熊市：价值 0.25 + 质量 0.20 + 动量 0.10 + 反转 0.20 + 规模 0.10 + 波动 0.10 + 流动性 0.05 = 1.0
       - 牛市：价值 0.10 + 质量 0.25 + 动量 0.30 + 反转 0.05 + 规模 0.10 + 波动 0.10 + 流动性 0.10 = 1.0
     - 综合得分 = Σ (因子 Z-score × 权重)，结果为标准正态分布。
     - 因子缺失时自动等比放大其他因子权重。

  4. **个股评估流程（当 /ask 600519 多因子 时执行）**
     - Step 1：调用 `get_daily_history` 获取 60 日行情，确认数据完整性。
     - Step 2：调用 `get_factor_scores` 计算该股的七因子 Z-score。
     - Step 3：根据综合得分给出评级。
     - Step 4：在 `buy_reason` 中详细说明各因子得分。
     - Step 5：检查 data_quality 字段。

  5. **横截面选股流程（用 get_universe_screen 做组合再平衡）**
     - Step 1：调用 `get_universe_screen(factors={...}, top_n=30, industry_limit=5)`。
     - Step 2：用户可直接使用此列表做组合调整。

  6. **再平衡机制（推荐）**
     - 月度：每月第一个交易日重新计算因子。
     - 调仓幅度：单股偏离目标权重 5% 才调整（控制换手率）。
     - 持仓上限：单股 ≤ 5%，单行业 ≤ 30%。

  7. **风险与限制**
     - 因子合成依赖历史数据，存在 alpha decay 风险。
     - 行业中性化可能在风格切换期失效。
     - 该策略最适合"低频组合管理"，不适合"日内/短线"决策。
     - **本策略不输出具体仓位/调仓时机**，由用户决定。
```

## 参见

- [成长质量 (growth_quality)](growth_quality.md) — 单股绝对质量评分
- [12-1 动量 (momentum_12_1)](momentum_12_1.md) — 动量因子可纳入本框架
- [预期重估 (expectation_repricing)](expectation_repricing.md) — 因子评分后的催化时机判断
- `src/agent/tools/factor_tools.py` — 因子计算工具的具体实现
