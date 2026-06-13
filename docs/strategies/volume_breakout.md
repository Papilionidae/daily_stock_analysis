# 放量突破 (Volume Breakout)

## 基本信息

| 字段 | 值 |
|------|-----|
| 策略 ID | `volume_breakout` |
| 名称 | 放量突破 |
| 分类 | 趋势 (trend) |
| 优先级 | 30 |
| 默认激活 | ❌ |
| 关联理念 | 第 1 条（严进不追高）、第 2 条（趋势交易）、第 3 条（筹码效率） |
| 市场状态 | `trending_up` |
| 别名 | 放量突破、突破 |

## 核心逻辑

检测**放量突破阻力位**信号。适用于股价接近已知阻力位时，判断是真突破还是假突破。

### 判断链

1. **阻力位识别**
   - 调用 `analyze_trend` → `resistance_levels` 获取阻力位
   - 通常为 20 日高点或前期震荡平台顶部

2. **量能确认**
   - 当日成交量 > 5 日均量的 2 倍
   - 调用 `get_realtime_quote` → `volume_ratio > 2.0` 确认
   - 调用 `get_daily_history` 计算均量交叉验证

3. **价格确认**
   - 收盘价必须站上阻力位
   - 收盘应在当日振幅上方 30%（强势收盘）
   - 突破后乖离率仍需 < 5%，避免追高

4. **后续验证**
   - 次日开盘应在突破位之上，区分真突破与假突破

5. **风险过滤**
   - 调用 `search_stock_news` 检查无重大利空
   - PE 不应过高（避免泡沫型突破）

### 评分调整

| 条件 | 调整 |
|------|------|
| 放量突破确认 | `sentiment_score +12` |
| 突破伴随板块共振 | 额外 +5 |
| 理想买点设在突破位附近 | 止损设在突破位下方 3% |

## 技术指标与数据依赖

| 数据/工具 | 用途 |
|-----------|------|
| `get_daily_history` | 计算均量、阻力位 |
| `analyze_trend` | 阻力位识别、趋势评分 |
| `get_realtime_quote` | 实时量比、价格位置 |
| 成交量 | 放量确认（> 2 倍均量） |
| 乖离率 | 防止追高（< 5%） |
| 板块共振 | 新闻搜索确认催化 |

## 适用场景

- **适合**：关键阻力位附近的蓄势、盘整后的突破初期
- **不适合**：连续涨停后的高乖离率、无量能支持的假突破
- **市场阶段**：上升趋势或盘整后启动行情中效果最可靠

## 与上下游策略的关系

| 策略 | 关系 |
|------|------|
| `bull_trend` | 增强：突破确认后进入趋势跟踪阶段 |
| `ma_golden_cross` | 配合：金叉 + 放量突破 = 最强趋势启动信号 |
| `shrink_pullback` | 互补：突破后回踩确认再入场的安全方案 |

## 在管道中的角色

- **specialist 模式**：当市场状态为 `trending_up` 时可选
- **信号强度**：`sentiment_score +12` 属于高强度加分，但需次日验证
- **风险控制**：严格止损在突破位下方 3%，避免假突破陷阱

## YAML 配置原文

```yaml
# Volume Breakout Strategy / 放量突破
# Price breaks above resistance on heavy volume (>2x average).

name: volume_breakout
display_name: 放量突破
description: 检测放量突破阻力位信号。适用于股价接近已知阻力位时。
category: trend
core_rules: [1, 2, 3]
required_tools:
  - get_daily_history
  - analyze_trend
  - get_realtime_quote
aliases: [放量突破, 突破]
default_priority: 30
market_regimes: [trending_up]

instructions: |
  **放量突破（Volume Breakout Strategy）**

  突破判定标准：

  1. **阻力位识别**：
     - 使用 `analyze_trend` → resistance_levels 获取阻力位。
     - 通常为 20 日高点或前期震荡平台顶部。

  2. **量能确认**（关联理念3：效率优先）：
     - 当日成交量 > 5 日均量的 2 倍。
     - 使用 `get_realtime_quote` → volume_ratio > 2.0 确认。
     - 使用 `get_daily_history` 计算均量进行交叉验证。

  3. **价格确认**（关联理念1：严进策略）：
     - 收盘价必须站上阻力位。
     - 收盘应在当日振幅上方 30%（强势收盘）。
     - 突破后乖离率检查：仍需 < 5%，避免追高。

  4. **后续验证**（如有数据）：
     - 次日开盘应在突破位之上，区分真突破与假突破。

  5. **风险过滤**（关联理念5：风险排查）：
     - 通过 `search_stock_news` 检查无重大利空。
     - PE 不应过高（避免泡沫型突破）。

  评分调整：
  - 放量突破确认：sentiment_score +12
  - 突破伴随板块共振（板块也走强）：额外 +5
  - 理想买点设在突破位附近，止损设在突破位下方 3%。
  - 在 `buy_reason` 和 `volume_analysis` 中注明"放量突破"。
```

## 参见

- [均线金叉 (ma_golden_cross)](ma_golden_cross.md) — 配合确认的趋势启动信号
- [缩量回踩 (shrink_pullback)](shrink_pullback.md) — 突破后回踩的安全入场方式
- [箱体震荡 (box_oscillation)](box_oscillation.md) — 突破前的箱体识别
