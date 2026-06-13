# 缩量回踩 (Shrink Pullback)

## 基本信息

| 字段 | 值 |
|------|-----|
| 策略 ID | `shrink_pullback` |
| 名称 | 缩量回踩 |
| 分类 | 趋势 (trend) |
| 优先级 | 40 |
| 默认激活 | ❌ |
| 默认路由 | ✅ 是 |
| 关联理念 | 第 1 条（严进不追高）、第 2 条（趋势交易）、第 4 条（买点偏好） |
| 市场状态 | `trending_down`, `sideways` |
| 别名 | 缩量回踩、回踩 |

## 核心逻辑

检测**缩量回踩均线支撑**信号，寻找趋势延续的理想入场点。这是核心交易理念中"买点偏好"的具体实现。

### 判断链

1. **前提条件（必须满足）**
   - 股票必须处于上升趋势：MA5 > MA10 > MA20
   - 调用 `analyze_trend` 确认多头排列

2. **回踩检测**
   - 调用 `get_daily_history` 和 `get_realtime_quote`
   - 价格回踩至 MA5 附近（误差 1% 以内）或 MA10 附近（误差 2% 以内）
   - 回调期间成交量 < 5 日均量的 70%（缩量特征）
   - `analyze_trend` → volume_status 应显示缩量

3. **反弹信号**
   - 当前价格守住均线支撑位
   - MA5 乖离率 < 2% — 最佳买入区间

4. **确认条件**
   - `search_stock_news` 无利空消息
   - 筹码分布健康（获利比例 50-80%）

### 评分调整

| 条件 | 调整 |
|------|------|
| 缩量回踩 MA5 | `sentiment_score +10` |
| 缩量回踩 MA10 且量能 < 0.6 倍均量 | `sentiment_score +8` |
| 理想买点设在 MA5 水平 | 止损设在 MA20 |
| 次优买点设在 MA10 | — |

## 技术指标与数据依赖

| 数据/工具 | 用途 |
|-----------|------|
| `get_daily_history` | 获取日 K 数据，计算均线和成交量 |
| `analyze_trend` | MA 排列确认、volume_status |
| `get_realtime_quote` | 实时价格定位 |
| 成交量 | 缩量判定（< 70% 5日均量） |
| 乖离率 | 买入区间控制（< 2%） |
| 筹码分布 | 获利比例健康度检查 |

## 适用场景

- **适合**：上升趋势中的正常回调、均线支撑位附近企稳
- **不适合**：下跌趋势中的反弹（容易抄在半山腰）、高位放量暴跌
- **市场阶段**：趋势市中效果最佳；震荡市需降低仓位

## 与上下游策略的关系

| 策略 | 关系 |
|------|------|
| `bull_trend` | 本策略是 `bull_trend` 入场时机的最佳子集 |
| `ma_golden_cross` | 互补：金叉关注"刚突破"，回踩关注"突破后确认" |
| `short_term_reversal` | 区别：回踩不破 vs 超跌反弹，风险等级不同 |

## 在管道中的角色

- **specialist 模式**：当市场状态为 `sideways` 或 `trending_down` 时自动选入
- **入场信号**：系统核心理念 4 的直接实现 — "最佳买点：缩量回踩 MA5"
- **Score 权重**：由于是低风险入场点，评分调整较积极

## YAML 配置原文

```yaml
# Shrink Volume Pullback Strategy / 缩量回踩
# Volume shrinks during pullback to MA5/MA10, then price bounces.

name: shrink_pullback
display_name: 缩量回踩
description: 检测缩量回踩均线支撑信号，趋势延续的理想入场点。
category: trend
core_rules: [1, 2, 4]
required_tools:
  - get_daily_history
  - analyze_trend
  - get_realtime_quote
aliases: [缩量回踩, 回踩]
default_router: true
default_priority: 40
market_regimes: [trending_down, sideways]

instructions: |
  **缩量回踩（Shrink Volume Pullback Strategy）**

  入场判定标准：

  1. **前提条件**（关联理念2：趋势交易）：
     - 股票必须处于上升趋势（MA5 > MA10 > MA20）。
     - 使用 `analyze_trend` 确认多头排列。

  2. **回踩检测**（关联理念4：买点偏好）：
     - 使用 `get_daily_history` 和 `get_realtime_quote`。
     - 价格回踩至 MA5 附近（误差 1% 以内）或 MA10 附近（误差 2% 以内）。
     - 回调期间成交量 < 5 日均量的 70%（缩量特征）。
     - `analyze_trend` → volume_status 应显示缩量。

  3. **反弹信号**（关联理念1：严进策略）：
     - 当前价格守住均线支撑位。
     - MA5 乖离率 < 2% — 最佳买入区间。

  4. **确认条件**（关联理念5：风险排查）：
     - `search_stock_news` 无利空消息。
     - 筹码分布健康（获利比例 50-80%）。

  评分调整：
  - 缩量回踩 MA5：sentiment_score +10
  - 缩量回踩 MA10 且量能 < 0.6 倍均量：sentiment_score +8
  - 理想买点设在 MA5 水平，次优买点设在 MA10。
  - 止损设在 MA20 水平。
  - 在 `buy_reason` 中注明"缩量回踩"。
```

## 参见

- [默认多头趋势 (bull_trend)](bull_trend.md) — 本策略的上层趋势框架
- [均线金叉 (ma_golden_cross)](ma_golden_cross.md) — 趋势启动替代信号
- [短期反转 (short_term_reversal)](short_term_reversal.md) — 不同风险等级的入场策略
