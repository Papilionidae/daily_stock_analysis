# 盈利公告漂移 (PEAD Drift)

## 基本信息

| 字段 | 值 |
|------|-----|
| 策略 ID | `pead_drift` |
| 名称 | 盈利公告漂移 |
| 分类 | 框架 (framework) |
| 优先级 | 20 |
| 默认激活 | ❌ |
| 关联理念 | 第 5 条（风险排查）、第 6 条（估值关注） |
| 市场状态 | `trending_up`, `sideways` |
| 别名 | PEAD、盈利漂移、财报漂移、公告后漂移 |

## 核心逻辑

Post-Earnings Announcement Drift (PEAD)：财报发布后 60 日内股价漂移效应。A 股散户主导，PEAD 比成熟市场更显著（财报发布后 60 日内漂移 3-8%）。

**出处**：Ball & Brown 1968；A 股 王化成 2004、张永任 2010。

### 判断链

1. **SUE 计算（Standardized Unexpected Earnings）**
   - 调用 `get_stock_info` 拉最近 4 个季度 EPS
   - SUE = (Q_t - Q_{t-4}) / σ(Q_{t-4}, Q_{t-3}, Q_{t-2}, Q_{t-1})

| SUE 范围 | 含义 |
|----------|------|
| > 1.0 | 强超预期 |
| 0.5 ~ 1.0 | 温和超预期 |
| < -1.0 | 强低于预期（反向 PEAD） |

2. **公告日确认**
   - 调用 `search_stock_news` 检索"{公司名} 业绩预告"或"{公司名} 财报"
   - 关注业绩预告/快报/正式财报三类公告的发布时间

3. **入场条件（同时满足）**
   - 距公告日 0-30 日（漂移最强窗口）
   - SUE > 0.5
   - 当前价格未提前透支（相对 60 日均线偏离 < 20%）
   - 排除 ST / 小市值（< 50 亿）/ 一次性损益占大头

4. **风险排查**
   - 公告日前股价已大涨 30%+ → "price in"，不再追
   - 同期行业已普涨 → alpha 已被消化
   - 公告日附近北向资金大幅流出 → 警惕
   - 业绩"看上去"超预期但现金流恶化 → 警惕"应收账款型超预期"

5. **出场规则**
   - 持有 30-60 日
   - 浮盈 > 15% 减半仓
   - SUE 修正（业绩兑现后）立即清仓
   - 反向 PEAD（SUE < -1）：公告日已跌停则不再追空

### 评分调整

PEAD 的评分调整不是直接的分数增减，而是影响 `buy_reason` 和 `risk_warning` 中的标注：

- 必须在 `buy_reason` 注明 "PEAD：SUE={value}, 距公告日={n}日, 漂移窗口={n}日"
- 必须明确给出持有期预期
- 在 `risk_warning` 中标注"如公告日后股价已大涨 30%+ 则放弃"

## 技术指标与数据依赖

| 数据/工具 | 用途 |
|-----------|------|
| `get_stock_info` | 最近 4 个季度 EPS |
| `search_stock_news` | 公告日确认 |
| `get_daily_history` | 60 日均线偏离 |
| `get_realtime_quote` | 当前价格、涨跌幅 |
| SUE | 超预期程度量化 |

## 适用场景

- **适合**：财报季、业绩预告期、季报/年报刚发布的个股
- **不适合**：财报信息已充分消化（距公告日 > 60 日）、公告日前已暴涨
- **市场阶段**：业绩驱动的风格中效果显著

## 与上下游策略的关系

| 策略 | 关系 |
|------|------|
| `event_driven` | 子集：PEAD 是事件驱动在财报场景的特化版本 |
| `momentum_12_1` | 互补：PEAD 是"基本面驱动"，动量是"技术面驱动" |
| `short_term_reversal` | 互补：PEAD 找趋势延续，反转找超跌反弹 |
| `growth_quality` | 验证：财报是验证成长判断的关键事件 |

## 在管道中的角色

- **specialist 模式**：当市场状态为 `trending_up` 或 `sideways` 时可选
- **时效性强**：漂移窗口仅有 60 天，最佳入场期在 0-30 天
- **风险限制**：对公告前已大涨的个股自动放弃（price in 保护）

## YAML 配置原文

```yaml
# 盈利公告漂移策略 / Post-Earnings Announcement Drift (PEAD)
name: pead_drift
display_name: 盈利公告漂移
description: 财报发布后 60 日内的股价漂移效应（PEAD），
  A 股散户主导市场效应显著。
category: framework
core_rules: [5, 6]
required_tools:
  - get_stock_info
  - search_stock_news
  - get_daily_history
  - get_realtime_quote
default_priority: 20
market_regimes: [trending_up, sideways]
aliases: [PEAD, 盈利漂移, 财报漂移, 公告后漂移]

instructions: |
  **盈利公告漂移（PEAD, Post-Earnings Announcement Drift）**

  出处：Ball & Brown 1968；A 股 王化成 2004、张永任 2010。
  A 股散户主导，PEAD 比成熟市场更显著（财报发布后 60 日内股价漂移 3-8%）。

  适用场景：
  - 个股在 60 日内发布过业绩预告/快报/年报/季报。
  - 业绩超预期（SUE > 0）时，股价存在 3-8% 的持续漂移。
  - 与动量/反转互补：PEAD 是"基本面驱动"，动量是"技术面驱动"。

  分析框架：

  1. **SUE 计算（Standardized Unexpected Earnings）**
     - 用 `get_stock_info` 拉最近 4 个季度 EPS。
     - SUE = (Q_t - Q_{t-4}) / σ(Q_{t-4}, Q_{t-3}, Q_{t-2}, Q_{t-1})
     - SUE > 1.0 为强超预期
     - 0.5 < SUE < 1.0 为温和超预期
     - SUE < -1.0 为强低于预期（反向 PEAD：业绩雷后 60 日仍会下跌）

  2. **公告日确认**
     - 用 `search_stock_news` 检索 "{公司名} 业绩预告" 或 "{公司名} 财报"。
     - 关注业绩预告/快报/正式财报三类公告的发布时间。

  3. **入场条件（同时满足）**
     - 距公告日 0-30 日（漂移最强窗口）。
     - SUE > 0.5。
     - 当前价格未提前透支（相对 60 日均线偏离 < 20%）。
     - 排除 ST / 小市值（< 50 亿）/ 一次性损益占大头。

  4. **风险排查（关联核心规则 5）**
     - 公告日前股价已大涨 30%+ → "price in"，不再追。
     - 同期行业已普涨 → alpha 已被消化。
     - 公告日附近北向资金大幅流出 → 警惕。
     - 业绩"看上去"超预期但现金流恶化 → 警惕"应收账款型超预期"。

  5. **出场规则**
     - 持有 30-60 日。
     - 浮盈 > 15% 减半仓。
     - SUE 修正（业绩兑现后）立即清仓。
     - 反向 PEAD（SUE < -1）：若公告日已跌停，不再追空，否则做空/回避。

  6. **输出规范**
     - 必须在 `buy_reason` 注明 "PEAD：SUE={value}, 距公告日={n}日, 漂移窗口={n}日"。
     - 必须明确给出持有期预期。
     - 在 `risk_warning` 中标注"如公告日后股价已大涨 30%+ 则放弃"。

  7. **风险与限制**
     - 财报数据有 1-2 月滞后（公司发布到数据库落库）。
     - 一次性损益（卖资产、汇兑收益）会污染 SUE。
     - 不同行业 PEAD 强度差异大：消费/医药强，钢铁/煤炭弱。
```

## 参见

- [事件驱动 (event_driven)](event_driven.md) — 事件驱动的通用框架
- [成长质量 (growth_quality)](growth_quality.md) — 财报验证成长性
- [12-1 动量 (momentum_12_1)](momentum_12_1.md) — 技术面驱动的互补策略
- [短期反转 (short_term_reversal)](short_term_reversal.md) — 业绩雷后的反转机会
