# 底部放量 (Bottom Volume Surge)

## 基本信息

| 字段 | 值 |
|------|-----|
| 策略 ID | `bottom_volume` |
| 名称 | 底部放量 |
| 分类 | 反转 (reversal) |
| 优先级 | 60 |
| 默认激活 | ❌ |
| 关联理念 | 第 2 条（趋势交易）、第 5 条（风险排查） |
| 市场状态 | `trending_down` |
| 别名 | 地量见底、底部放量 |

## 核心逻辑

检测长期下跌后底部放量信号，潜在趋势反转信号。

### 与 `short_term_reversal` 的区别

| 维度 | 底部放量 | 短期反转 |
|------|----------|----------|
| 核心信号 | 放量 3 倍是关键 | 5-10 日跌幅 + 趋势过滤 |
| 量能角色 | 主导（放量确认底部） | 辅助（企稳信号之一） |
| 时间跨度 | 长期下跌后（>15%跌幅） | 短期超跌（5-10日） |
| 风险等级 | 更低（底部确认更充分） | 更高（抄底可能在半山腰） |

### 判断链

1. **持续下跌确认**
   - 调用 `get_daily_history`（30 日）
   - 股价从 20 日高点到近期低点跌幅 > 15%
   - `analyze_trend` → trend_status 应为 BEAR 或 STRONG_BEAR

2. **量能异动**
   - 当日成交量 > 5 日均量的 3 倍
   - 调用 `get_realtime_quote` → volume_ratio > 3.0
   - 该异动应出现在前期极度缩量之后

3. **价格企稳**
   - 当日 K 线收阳（收盘价 > 开盘价）
   - 价格守住近期低点
   - 最好出现长下影线，显示买方支撑

4. **确认因素**
   - 调用 `search_stock_news` 确认是否有基本面催化
   - 筹码分布：平均成本接近现价（成本收敛）

5. **风险提示**
   - 这是反转信号，风险高于趋势跟踪
   - 仓位建议较小（最多 2-3 成）
   - 止损必须严格（设在近期低点下方）

### 评分调整

| 条件 | 调整 |
|------|------|
| 底部放量确认 | `sentiment_score +8` |
| 配合阳线 + 新闻催化 | 额外 +5 |
| 止损设在近期低点 | — |

## 技术指标与数据依赖

| 数据/工具 | 用途 |
|-----------|------|
| `get_daily_history` | 跌幅计算、成交量均量、均线状态 |
| `analyze_trend` | 趋势评分、支撑位 |
| `get_realtime_quote` | 实时量比、价格位置 |
| `search_stock_news` | 基本面催化确认 |
| 成交量 | 放量 3 倍判定 |
| 筹码分布 | 平均成本 vs 现价 |

## 适用场景

- **适合**：长期下跌后的底部放量企稳、地量见底后的放量阳线
- **不适合**：下跌中继的放量反弹（可能是主力出货）、高位放量滞涨
- **市场阶段**：下跌末期、底部区域确认阶段

## 与上下游策略的关系

| 策略 | 关系 |
|------|------|
| `short_term_reversal` | 互补：本策略量能主导，反转策略跌幅主导 |
| `box_oscillation` | 延伸：底部确认后可能进入箱体震荡 |
| `bull_trend` | 转换：反转成功后应切换至趋势策略 |
| `emotion_cycle` | 验证：情绪恐慌底往往伴随底部放量 |

## 在管道中的角色

- **specialist 模式**：当市场状态为 `trending_down` 时可选
- **高风险信号**：反转信号的风险高于趋势跟踪，仓位建议更小
- **严格止损**：必须严格止损在近期低点下方

## YAML 配置原文

```yaml
# Bottom Volume Surge Strategy / 底部放量
# After extended decline, price stabilizes and volume spikes. Potential reversal.

name: bottom_volume
display_name: 底部放量
description: 检测长期下跌后底部放量信号，潜在趋势反转信号。
category: reversal
core_rules: [2, 5]
required_tools:
  - get_daily_history
  - analyze_trend
aliases: [地量见底, 底部放量]
default_priority: 60
market_regimes: [trending_down]

instructions: |
  **底部放量（Bottom Volume Surge Strategy）**

  反转判定标准：

  1. **持续下跌确认**：
     - 使用 `get_daily_history`（30日）。
     - 股价从 20 日高点到近期低点跌幅 > 15%。
     - `analyze_trend` → trend_status 应为 BEAR 或 STRONG_BEAR。

  2. **量能异动**：
     - 当日成交量 > 5 日均量的 3 倍。
     - 使用 `get_realtime_quote` → volume_ratio > 3.0。
     - 该异动应出现在前期极度缩量之后。

  3. **价格企稳**：
     - 当日K线收阳（收盘价 > 开盘价）。
     - 价格守住近期低点。
     - 最好出现长下影线，显示买方支撑。

  4. **确认因素**（关联理念5：风险排查）：
     - 通过 `search_stock_news` 确认是否有基本面催化。
     - 筹码分布：平均成本接近现价（成本收敛）。

  5. **风险提示**（关联理念2：趋势交易）：
     - 这是反转信号，风险高于趋势跟踪。
     - 仓位建议较小（最多 2-3 成）。
     - 止损必须严格（设在近期低点下方）。

  评分调整：
  - 底部放量确认：sentiment_score +8
  - 配合阳线 + 新闻催化：额外 +5
  - 在 `buy_reason` 和 `pattern_analysis` 中注明"底部放量"。
  - 止损设在近期低点。
```

## 参见

- [短期反转 (short_term_reversal)](short_term_reversal.md) — 跌幅主导的互补策略
- [箱体震荡 (box_oscillation)](box_oscillation.md) — 底部确认后的操作框架
- [情绪周期 (emotion_cycle)](emotion_cycle.md) — 底部放量时的情绪验证
- [默认多头趋势 (bull_trend)](bull_trend.md) — 反转成功后的趋势转换
