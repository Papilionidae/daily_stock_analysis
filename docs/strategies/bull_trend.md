# 默认多头趋势 (Bull Trend)

## 基本信息

| 字段 | 值 |
|------|-----|
| 策略 ID | `bull_trend` |
| 名称 | 默认多头趋势 |
| 分类 | 趋势 (trend) |
| 优先级 | 10 |
| 默认激活 | ✅ 是 |
| 默认路由 | ✅ 是 |
| 关联理念 | 第 1 条（严进不追高）、第 2 条（趋势交易）、第 3 条（筹码效率） |
| 市场状态 | `trending_up` |
| 别名 | 趋势、趋势分析、多头趋势 |

## 核心逻辑

本策略是系统的**默认策略**，优先寻找"趋势向上 + 风险可控 + 不追高"的机会。

### 判断链

1. **趋势确认（最高优先级）**
   - 调用 `analyze_trend` 判断 MA5/MA10/MA20 排列
   - MA5 >= MA10 >= MA20 且 MA20 斜率向上 → 多头结构
   - 价格显著跌破 MA20 → 降低看多权重

2. **位置与节奏**
   - 优先"回踩不破"而非"高位追涨"
   - 价格偏离 MA5/MA10 过远时提示等待回踩
   - 放量突破有效阻力时可提高胜率评级

3. **量价验证**
   - 调用 `get_daily_history` 检查突破日/反弹日是否放量
   - 缩量上涨需谨慎，放量滞涨需警惕分歧

4. **交易建议输出**
   - 输出明确的"买入/观望/减仓"倾向及触发条件
   - 必须给出止损参考（MA20 下方或结构低点）
   - 无清晰优势时明确写"暂不出手"

### 评分调整

| 条件 | 调整 |
|------|------|
| 多头排列 + 趋势强度良好 | `sentiment_score +12` |
| 回踩关键均线后企稳 | `sentiment_score +8` |
| 放量突破关键阻力 | `sentiment_score +10` |
| 跌破 MA20 或趋势转弱 | `sentiment_score -12` |

## 技术指标与数据依赖

| 数据/工具 | 用途 |
|-----------|------|
| `get_daily_history` | 获取日 K 数据，验证量价关系 |
| `analyze_trend` | 获取 MA 排列、趋势评分、支撑阻力 |
| MA5/MA10/MA20 | 多头排列判定 |
| 成交量 | 放量突破 / 缩量上涨的验证 |
| 乖离率 | 防止追高（>5% 不买入） |

## 适用场景

- **适合**：常规个股分析的默认策略，无明显特殊信号时的基线
- **不适合**：个股出现明确特殊信号（如事件驱动、预期重估）时，应切换到更针对性策略
- **市场阶段**：上升趋势中效果最佳；震荡市需结合其他策略；下跌市应降低权重

## 在管道中的角色

- **specialist 模式**：作为默认 SkillAgent 插入 DecisionAgent 之前
- **基线策略**：当 `SkillRouter` 无法匹配市场状态时，回退到本策略
- **与 DecisionAgent 交互**：输出趋势评分 + 支撑阻力位 + 买卖倾向，供 DecisionAgent 综合权重（技术面占 40%）

## YAML 配置原文

```yaml
# Default Bull Trend Strategy / 默认多头趋势

name: bull_trend
display_name: 默认多头趋势
description: 默认个股分析优先策略，识别多头排列、趋势延续与回踩低吸机会。
category: trend
core_rules: [1, 2, 3]
required_tools:
  - get_daily_history
  - analyze_trend
aliases: [趋势, 趋势分析, 多头趋势]
default_active: true
default_router: true
default_priority: 10
market_regimes: [trending_up]

instructions: |
  **默认多头趋势（Default Bull Trend Strategy）**

  适用场景：
  - 常规个股分析的默认策略。
  - 优先寻找"趋势向上 + 风险可控 + 不追高"的机会。

  分析框架：

  1. **趋势确认（优先级最高）**
     - 使用 `analyze_trend` 判断 MA5/MA10/MA20 排列。
     - MA5 >= MA10 >= MA20 且 MA20 斜率向上，视为多头结构。
     - 若价格显著跌破 MA20，则降低看多权重。

  2. **位置与节奏**
     - 优先"回踩不破"而非"高位追涨"。
     - 当价格距离 MA5/MA10 过远时，提示等待回踩。
     - 放量突破有效阻力时可提高胜率评级。

  3. **量价验证**
     - 使用 `get_daily_history` 检查突破日/反弹日是否放量。
     - 缩量上涨需谨慎，放量滞涨需警惕分歧。

  4. **交易建议输出**
     - 输出明确的"买入/观望/减仓"倾向及触发条件。
     - 必须给出止损参考（如 MA20 下方或结构低点）。
     - 若无清晰优势，明确写"暂不出手"，避免过度交易。

  评分调整建议：
  - 多头排列 + 趋势强度良好：`sentiment_score +12`
  - 回踩关键均线后企稳：`sentiment_score +8`
  - 放量突破关键阻力：`sentiment_score +10`
  - 跌破 MA20 或趋势转弱：`sentiment_score -12`
```

## 参见

- [均线金叉 (ma_golden_cross)](ma_golden_cross.md) — 更精细的均线交叉信号
- [缩量回踩 (shrink_pullback)](shrink_pullback.md) — 本策略的最佳入场子集
- `src/agent/skills/defaults.py` — `get_default_active_skill_ids()` 默认选中本策略
