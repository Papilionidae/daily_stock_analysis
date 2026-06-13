# 策略笔记

本目录包含项目中所有 YAML 定义的可插拔交易技能（Trading Skill）的详细介绍笔记。

## 索引

| 策略 ID | 名称 | 分类 | 优先级 | 默认激活 |
|---------|------|------|--------|---------|
| `bull_trend` | 默认多头趋势 | 趋势 (trend) | 10 | ✅ 是 |
| `dragon_head` | 龙头策略 | 趋势 (trend) | 50 | ❌ |
| `shrink_pullback` | 缩量回踩 | 趋势 (trend) | 60 | ❌ |
| `ma_golden_cross` | 均线金叉 | 趋势 (trend) | 70 | ❌ |
| `volume_breakout` | 放量突破 | 趋势 (trend) | 80 | ❌ |
| `momentum_12_1` | 12-1 动量 | 趋势 (trend) | 90 | ❌ |
| `sector_rotation` | 行业轮动 | 框架 (framework) | 100 | ❌ |
| `hot_theme` | 热点题材 | 框架 (framework) | 100 | ❌ |
| `multi_factor` | 多因子选股 | 框架 (framework) | 100 | ❌ |
| `growth_quality` | 成长质量 | 框架 (framework) | 100 | ❌ |
| `expectation_repricing` | 预期重估 | 框架 (framework) | 100 | ❌ |
| `event_driven` | 事件驱动 | 框架 (framework) | 100 | ❌ |
| `emotion_cycle` | 情绪周期 | 框架 (framework) | 100 | ❌ |
| `pead_drift` | 盈利公告漂移 | 框架 (framework) | 100 | ❌ |
| `short_term_reversal` | 短期反转 | 反转 (reversal) | 100 | ❌ |
| `bottom_volume` | 底部放量 | 反转 (reversal) | 100 | ❌ |
| `box_oscillation` | 箱体震荡 | 框架 (framework) | 100 | ❌ |
| `chan_theory` | 缠论 | 框架 (framework) | 100 | ❌ |
| `wave_theory` | 波浪理论 | 框架 (framework) | 100 | ❌ |
| `one_yang_three_yin` | 一阳夹三阴 | 形态 (pattern) | 100 | ❌ |

## 笔记结构规范

每篇策略笔记统一按以下章节组织：

```markdown
# 策略名称

## 基本信息
- 策略 ID、分类、优先级、默认激活状态
- 关联的市场状态（regime tags）
- 用户是否可调用

## 核心逻辑
- 策略的核心判断条件
- 触发信号的完整条件链

## 技术指标与数据依赖
- 依赖哪些 MA/MACD/RSI/成交量等指标
- 依赖哪些外部数据源

## 适用场景
- 什么时候该用 / 不该用
- 适合什么市场阶段和行情特征

## 在管道中的角色
- 在 specialist 模式下如何被 SkillAgent 评估
- 与 DecisionAgent 的交互 / 评分权重

## YAML 配置原文
- 附上 `strategies/<id>.yaml` 的完整内容

## 参见
- 关联策略、上下游模块、相关测试
```

## 设计原则

- 所有策略以 YAML 定义，零 Python 代码即可新增
- 策略通过 `SkillRouter` 自动选择（用户请求 > 市场状态探测 > 默认 fallback）
- 在 `specialist` 管道模式中，最多并发 3 个 SkillAgent 分别评估
- 评估结果经 `SkillAggregator` 加权合成为统一信号
