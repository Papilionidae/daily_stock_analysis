# 均线金叉 (MA Golden Cross)

## 基本信息

| 字段 | 值 |
|------|-----|
| 策略 ID | `ma_golden_cross` |
| 名称 | 均线金叉 |
| 分类 | 趋势 (trend) |
| 优先级 | 20 |
| 默认激活 | ❌ |
| 关联理念 | 第 1 条（严进不追高）、第 2 条（趋势交易）、第 3 条（筹码效率） |
| 市场状态 | `trending_up` |
| 别名 | 均线金叉、金叉 |

## 核心逻辑

检测均线金叉配合量能确认信号，是经典的趋势反转 / 延续信号。

### 判断链

1. **金叉检测**
   - 调用 `analyze_trend` 检查均线排列和 MACD 状态
   - **主信号**：MA5 在最近 3 个交易日内上穿 MA10
   - **强信号**：MA10 上穿 MA20（更慢但更可靠）
   - 检查 MACD 状态是否为金叉或零轴上方金叉

2. **量能确认**
   - 金叉日成交量应高于 5 日均量
   - 调用 `get_daily_history` 验证
   - 金叉日量比 > 1.2 为积极信号

3. **趋势背景**
   - **盘整后金叉**：最强信号
   - **上升趋势中金叉**：延续信号
   - **深度下跌中金叉**：弱信号，需更多确认

4. **价格位置**
   - 价格应在交叉均线附近或上方
   - 乖离率 < 5% — 避免追高延迟入场

### 评分调整

| 条件 | 调整 |
|------|------|
| MA5 × MA10 金叉配合量能 | `sentiment_score +10` |
| MA10 × MA20 金叉 | `sentiment_score +8` |
| MACD 零轴上方金叉 | 额外 +5 |

## 技术指标与数据依赖

| 数据/工具 | 用途 |
|-----------|------|
| `get_daily_history` | 获取日 K 数据，计算均线与成交量 |
| `analyze_trend` | MA 排列、MACD 状态 |
| MA5/MA10/MA20 | 金叉判定 |
| MACD | 辅助确认（零轴上方金叉为强信号） |
| 成交量 | 量比 > 1.2 确认 |
| 乖离率 | 防止延迟入场（< 5%） |

## 适用场景

- **适合**：盘整后的突破初期、上升趋势中的均线交叉确认
- **不适合**：均线频繁交叉的震荡行情（容易产生假信号）、乖离率过高的追高
- **市场阶段**：趋势由跌转涨或盘整后启动时效果最佳

## 与上下游策略的关系

| 策略 | 关系 |
|------|------|
| `bull_trend` | 增强：金叉是趋势确认的量化指标之一 |
| `shrink_pullback` | 互补：金叉关注"刚突破"，回踩关注"确认后入场" |
| `volume_breakout` | 配合：金叉 + 放量突破阻力位 = 最强信号 |

## 在管道中的角色

- **specialist 模式**：当市场状态为 `trending_up` 时可选
- **信号层级**：属于趋势启动信号，与 `volume_breakout` 处于同一信号层级
- **Score 权重**：金叉 + 盘整后突破的综合评分最高

## YAML 配置原文

```yaml
# MA Golden Cross Strategy / 均线金叉
# MA5 crosses above MA10 (or MA10 above MA20) with volume confirmation.

name: ma_golden_cross
display_name: 均线金叉
description: 检测均线金叉配合量能确认信号，经典的趋势反转/延续信号。
category: trend
core_rules: [1, 2, 3]
required_tools:
  - get_daily_history
  - analyze_trend
aliases: [均线金叉, 金叉]
default_priority: 20
market_regimes: [trending_up]

instructions: |
  **均线金叉（MA Golden Cross Strategy）**

  信号判定标准：

  1. **金叉检测**（关联理念2：趋势交易）：
     - 使用 `analyze_trend` 检查均线排列和 MACD 状态。
     - 主信号：MA5 在最近 3 个交易日内上穿 MA10。
     - 强信号：MA10 上穿 MA20（更慢但更可靠）。
     - 检查 MACD 状态是否为金叉或零轴上方金叉。

  2. **量能确认**（关联理念3：效率优先）：
     - 金叉日成交量应高于 5 日均量。
     - 使用 `get_daily_history` 验证。
     - 金叉日量比 > 1.2 为积极信号。

  3. **趋势背景**：
     - 盘整后金叉：最强信号。
     - 上升趋势中金叉：延续信号。
     - 深度下跌中金叉：弱信号，需更多确认。

  4. **价格位置**（关联理念1：严进策略）：
     - 价格应在交叉均线附近或上方。
     - 乖离率 < 5% — 避免追高延迟入场。

  评分调整：
  - MA5 × MA10 金叉配合量能：sentiment_score +10
  - MA10 × MA20 金叉：sentiment_score +8
  - MACD 零轴上方金叉：额外 +5
  - 在 `ma_analysis` 和 `buy_reason` 中注明"均线金叉"。
  - 理想买点设在交叉均线水平附近。
```

## 参见

- [默认多头趋势 (bull_trend)](bull_trend.md) — 趋势框架基线
- [缩量回踩 (shrink_pullback)](shrink_pullback.md) — 金叉后回踩的入场时机
- [放量突破 (volume_breakout)](volume_breakout.md) — 配合金叉的最强确认信号
