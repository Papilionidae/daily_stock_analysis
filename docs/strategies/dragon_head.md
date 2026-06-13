# 龙头策略 (Dragon Head)

## 基本信息

| 字段 | 值 |
|------|-----|
| 策略 ID | `dragon_head` |
| 名称 | 龙头策略 |
| 分类 | 趋势 (trend) |
| 优先级 | 90 |
| 默认激活 | ❌ |
| 关联理念 | 第 2 条（趋势交易）、第 7 条（强势趋势股放宽） |
| 市场状态 | `sector_hot` |
| 别名 | 龙头、龙头战法 |

## 核心逻辑

识别板块轮动周期中的**龙头股**。适用于板块启动或行业催化剂出现时。

### 判断链

1. **板块领涨地位**
   - 调用 `get_sector_rankings` 检查该股所在板块是否为近期涨幅前列
   - 确认该股是否在板块启动周期中率先上涨或涨停

2. **换手率与动能**
   - 调用 `get_realtime_quote` 检查换手率（龙头股通常 > 5%）
   - 量比 > 1.5 说明有活跃交易兴趣

3. **相对强度**
   - 对比个股涨跌幅与板块平均值
   - 真正的龙头在上涨日应跑赢板块 2% 以上

4. **新闻催化**
   - 调用 `search_stock_news` 搜索板块级催化剂（政策、事件、业绩）
   - 龙头行情常伴随板块整体催化

5. **乖离率检查**
   - 龙头股可适当放宽乖离率至 7%（但超过 10% 仍需谨慎）

### 评分调整

| 条件 | 调整 |
|------|------|
| 确认为龙头股 | `sentiment_score +10` |
| 板块正处于主动轮动期 | 额外 +5 |
| 在 `buy_reason` 注明"龙头策略" | — |

## 技术指标与数据依赖

| 数据/工具 | 用途 |
|-----------|------|
| `get_sector_rankings` | 板块排名与涨幅数据 |
| `get_realtime_quote` | 换手率、量比 |
| `search_stock_news` | 板块催化剂新闻 |
| 换手率 | 龙头活跃度判断（>5%） |
| 量比 | 交易兴趣确认（>1.5） |
| 相对强度 | 个股 vs 板块涨幅差（>2%） |

## 适用场景

- **适合**：板块启动期、行业催化剂出现时、热点轮动行情
- **不适合**：无明确板块效应、大盘系统性下跌、个股独立行情
- **市场阶段**：板块热点驱动的结构性行情中效果最佳

## 与上下游策略的关系

| 策略 | 关系 |
|------|------|
| `sector_rotation` | 互补：`sector_rotation` 关注板块级排名，本策略关注个股级龙头识别 |
| `hot_theme` | 补充：`hot_theme` 确认题材强度后，本策略用于锁定其中龙头 |
| `bull_trend` | 增强：在趋势基础上加龙头筛选 |

## 在管道中的角色

- **specialist 模式**：当市场状态为 `sector_hot` 时，`SkillRouter` 优先路由到本策略
- **Score 权重**：确认为龙头后可显著提高 sentiment_score，但受 `RiskAgent` 风险过滤约束
- **适用规则**：龙头股可突破常规乖离率限制（理念 7），但必须有止损

## YAML 配置原文

```yaml
# Dragon Head Strategy / 龙头策略
# Identifies sector leaders during sector rotation cycles.

name: dragon_head
display_name: 龙头策略
description: 板块轮动中识别龙头股。适用于板块启动或行业催化剂出现时。
category: trend
core_rules: [2, 7]
required_tools:
  - get_realtime_quote
  - get_sector_rankings
  - search_stock_news
aliases: [龙头, 龙头战法]
default_priority: 90
market_regimes: [sector_hot]

instructions: |
  **龙头策略（Dragon Head Strategy）**

  评估标准：

  1. **板块领涨地位**：
     - 使用 `get_sector_rankings` 检查该股所在板块是否为近期涨幅前列。
     - 确认该股是否在板块启动周期中率先上涨或涨停。

  2. **换手率与动能**（关联理念7：强势趋势股放宽）：
     - 使用 `get_realtime_quote` 检查换手率。龙头股换手率通常 > 5%。
     - 量比 > 1.5 说明有活跃的交易兴趣。

  3. **相对强度**：
     - 对比个股涨跌幅与板块平均值。
     - 真正的龙头在上涨日应跑赢板块 2% 以上。

  4. **新闻催化**：
     - 使用 `search_stock_news` 搜索板块级催化剂（政策、事件、业绩）。
     - 龙头行情常伴随板块整体催化。

  5. **乖离率检查**（关联理念1：严进策略）：
     - 龙头股可适当放宽乖离率至 7%，但超过 10% 仍需谨慎。

  评分调整：
  - 确认为龙头股：sentiment_score +10
  - 板块正处于主动轮动期：额外 +5
  - 在 `buy_reason` 中注明"龙头策略"判断结果。
```

## 参见

- [行业轮动 (sector_rotation)](sector_rotation.md) — 板块层面排名
- [热点题材 (hot_theme)](hot_theme.md) — 题材强度确认
- [缩量回踩 (shrink_pullback)](shrink_pullback.md) — 龙头回踩时的入场配合
