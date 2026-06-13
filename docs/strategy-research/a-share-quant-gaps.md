# A 股量化策略研究备忘：项目未收录的公开有效策略

> 状态：内部研究备忘 / 项目参考文档
> 版本：v0.1
> 日期：2025-06-07
> 维护：项目 AI 协作流程产出

## 0. 摘要

本备忘盘点 **A 股市场已被学术或民间研究验证为有效的量化策略**，对比项目当前内置的 15 个策略（个股择时 + 题材判断为主），识别未覆盖的能力空白。

- **项目现状**：15 个内置策略，覆盖"个股择时 + 题材/事件判断"够用，但**横截面选股 + 统计套利 + 组合管理是空白**。
- **未覆盖的 12 个候选策略**（按学术/民间证据强度分 3 个 Tier）。
- **本次新增**：5 个策略 YAML（多因子 / 行业轮动 / 短期反转 / 12-1 动量 / PEAD）+ 1 个因子工具模块（3 个工具）。
- **数据基础**：Tushare / AkShare 已就绪，主要是策略 YAML 编写 + 2-3 个新工具。

## 1. 项目覆盖边界

### 1.1 已有 15 个策略的能力图谱

| 类别 | 策略 | 评估 |
|---|---|---|
| 趋势 | bull_trend, ma_golden_cross, volume_breakout, shrink_pullback | ✅ 单标的择时覆盖完整 |
| 形态 | one_yang_three_yin | ✅ 经典形态 |
| 反转 | bottom_volume | ⚠️ 只有"放量见底"一种 |
| 框架 | chan_theory, wave_theory, dragon_head, hot_theme, emotion_cycle, event_driven, expectation_repricing, growth_quality, box_oscillation | ✅ 偏个股主观判断 |
| **缺口** | **多因子/横截面/统计套利/系统化再平衡** | ❌ **完全缺失** |

### 1.2 架构判断

- 引擎：LLM Agent + Tool Registry
- 工具：日线 / 实时 / 板块 / 新闻 / 财务
- 策略载体：YAML（可热加载）
- 调度：单标的问股 + 路由 fallback

**结论**：策略层做"个股择时 + 题材判断"够用，**做"选股 + 配对 + 组合管理"是空白的**。但工具基础（行情/财务/板块/资金流）基本就绪，主要是策略 YAML 缺失 + 部分新工具未封装。

## 2. Tier 1：学术界广泛验证、A 股论文支持

### 2.1 多因子选股（Fama-French 中国版）

- **出处**：Fama-French 1993/2015；中国市场三因子验证见 Carhart 1997、潘莉、徐建国 2011
- **核心因子**：价值（EP/BM） + 质量（ROE/ROA/毛利） + 动量（12-1 MOM） + 反转（REV_5） + 规模（LN_MV）
- **核心规则**：① 行业中性化 ② 因子去极值 + Z-score ③ 等权/IC 加权合成 ④ 排序选股 ⑤ 月度再平衡
- **A 股证据**：2005-2020 长期跑赢；2017 后价值 + 质量因子显著走强；2019-2021 规模因子失效（小盘股崩）
- **数据需求**：日线/财务 ✅ 行业分类（申万/SW2021）✅ 全 A 股横截面（3000+ 标的，依赖 Tushare 性能）
- **工具需求**：**已实现** `get_factor_universe` / `get_factor_scores` / `get_universe_screen`
- **实施难度**：中（YAML 100 行 + 工具 200-300 行）
- **推荐度**：⭐⭐⭐⭐⭐（A 股最经典、长期有效、最值得补）
- **风险**：因子过拟合 / 行业中性漂移 / 小盘股流动性风险

### 2.2 12-1 动量（MOM_12-1）

- **出处**：Asness 1995；A 股见高秋明&熊伟 2014、赵鹏 2018
- **核心规则**：过去 12 个月累计收益 - 过去 1 个月累计收益；等权加权；月度调仓
- **A 股证据**：2009-2015 显著正 alpha；2016-2020 衰减明显（监管 / 北向资金改变博弈结构）；2020-2022 又回升
- **数据需求**：日线复权收盘价 ✅
- **工具需求**：可纯 YAML（LLM 自行计算 250 交易日收益） — **已实现为 `momentum_12_1.yaml`**
- **实施难度**：低
- **推荐度**：⭐⭐⭐⭐（动量 + 反转组合长期稳健，但 A 股单用易崩）
- **风险**：alpha decay 明显 / 板块崩盘期无效 / 必须 6 月 IC 复检

### 2.3 短期反转（REV_5 / REV_10）

- **出处**：Jegadeesh 1990；A 股 王永宏&赵学军 2001、鲁臻&邹恒甫 2007
- **核心规则**：做多过去 5-10 日跌幅最大 / 卖出涨幅最大；周度调仓
- **A 股证据**：2005-2022 全周期显著有效（夏普 1.5+）；是 A 股最稳定的策略之一
- **数据需求**：日线收盘价 + 成交量 ✅
- **工具需求**：可纯 YAML — **已实现为 `short_term_reversal.yaml`**
- **实施难度**：低
- **推荐度**：⭐⭐⭐⭐⭐（与 12-1 动量互补，构成"双策略"基础）
- **风险**：不能止跌就抄底（要配合趋势/质量过滤）

### 2.4 配对交易（协整配对 / Pairs Trading）

- **出处**：Gatev, Goetzmann, Rouwenhorst 2006；中国见陈守东 2006
- **核心规则**：① 全 A 股 / 行业里找协整对（Engle-Granger 或 Johansen）② 计算价差 Z-score ③ |Z| > 2 开仓，< 0.5 平仓
- **A 股证据**：银行 / 食品饮料 / 房地产等行业内配对夏普 1-2；2017 后衰减
- **数据需求**：日线 + 行业分类 ✅
- **工具需求**：需新增 `get_pair_candidates` / `get_pair_spread_zscore`（本次未实现，作为 v2 工作量）
- **实施难度**：高
- **推荐度**：⭐⭐⭐
- **风险**：协整断裂 / 配对相关性失效 / 流动性差异 / 跨期与跨市场扩展需求

### 2.5 行业轮动（Sector Rotation）

- **出处**：申万 / 中信 / 长江行业研报多年积累
- **核心规则**：① 行业动量（过去 N 日收益率）② 行业景气度（PPI/库存/PMI）③ 行业资金流（北向 + 主力）④ 综合打分排序
- **A 股证据**：2019-2021 消费/医药/新能源轮动夏普 2+；2022-2023 周期/红利板块主导
- **数据需求**：板块榜 ✅ + 行业成分股 ✅ + 资金流 ✅
- **工具需求**：可纯 YAML — **已实现为 `sector_rotation.yaml`**
- **实施难度**：低
- **推荐度**：⭐⭐⭐⭐⭐
- **风险**：行业主题切换频繁 / 政策黑天鹅

### 2.6 红利低波 Smart Beta

- **出处**：中证红利指数 / 红利低波指数 / 红利 LV 因子（2017 兴起）
- **核心规则**：① 股息率 top 30% ② 波动率 bottom 30% ③ 等权 / 风险平价 ④ 季度再平衡
- **A 股证据**：2005-2024 长期夏普 1.2+；2020-2023 大幅跑赢（防御+分红新规）
- **数据需求**：财务（每股股利 / 派息日期）✅（Tushare `dividend`）+ 波动率 ✅
- **工具需求**：可纯 YAML（需 dividend 数据源）
- **实施难度**：中
- **推荐度**：⭐⭐⭐⭐（熊市/震荡市神器）
- **风险**：派息波动 / 红利陷阱（高股息可能是基本面恶化）

### 2.7 美林时钟中国版（资产配置）

- **核心规则**：① 经济增长 + 通胀二维分类 ② 衰退/复苏/过热/滞涨 四象限 ③ 配股票/债券/商品/现金
- **A 股证据**：2010-2020 整体有效；2022-2023 宏观失真（疫情扰动）
- **数据需求**：宏观指标（PMI/CPI/PPI/M2）✅（Tushare 宏观）
- **工具需求**：需新增 `get_macro_regime`
- **实施难度**：中（跨资产需补 ETF 工具）
- **推荐度**：⭐⭐⭐
- **风险**：指标滞后 / 政策托底打破规律
- **注意**：这是"资产配置"类，不是"选股"类，应与 Tier 1 选股类分开

### 2.8 PEAD 盈利公告漂移（Post-Earnings Announcement Drift）

- **出处**：Ball & Brown 1968；A 股 王化成 2004、张永任 2010
- **核心规则**：① SUE = (Q_t - Q_{t-4}) / σ(Q_{t-4}) 标准化超预期盈利 ② 公告日 0-30 日为漂移最强窗口 ③ 持有 30-60 日
- **A 股证据**：2010-2022 长期显著，财报发布后 60 日内股价漂移 3-8%（散户主导市场效应比成熟市场更显著）
- **数据需求**：EPS 季度数据 + 公告日
- **工具需求**：可纯 YAML — **已实现为 `pead_drift.yaml`**
- **实施难度**：中
- **推荐度**：⭐⭐⭐⭐
- **风险**：一次性损益污染 SUE / 财报滞后 / 行业差异（消费医药强，钢铁煤炭弱）

## 3. Tier 2：民间/卖方研究/知名战法

### 3.1 海龟交易法则强化

- **核心规则**：① 入场：20 日新高/新低突破 ② 止损：2N（2 倍 ATR）③ 仓位：风险 = 账户 1% / 2N ④ 加仓：每次突破 0.5N 加 1 单位
- **A 股证据**：2008-2018 全周期夏普 1.0+；2019-2023 因 A 股波动加剧表现改善
- **与项目现有**：`volume_breakout` 类似但缺 ATR 资金管理
- **实施方式**：升级 `volume_breakout` YAML，加 ATR 仓位计算；或新增 `turtle_enhanced.yaml`（本次未实现）
- **推荐度**：⭐⭐⭐⭐
- **风险**：震荡市反复打脸 / 突破失败需严格止损

### 3.2 网格交易（Grid Trading）

- **核心规则**：① 价格区间分 N 档（等差 / 等比）② 每档买入 X 金额 / 卖出 Y 份额 ③ 中枢价格重置
- **A 股证据**：ETF / 银行股 / 红利指数实战夏普 1.5+；可转债双低夏普 1.0-1.5
- **数据需求**：实时价格 + 历史波动率 ✅
- **工具需求**：需新增 `get_grid_levels` / `simulate_grid`
- **实施难度**：中（需"持仓 + 价格触发"状态机）
- **推荐度**：⭐⭐⭐（ETF 用户爱用，股票难度大）
- **风险**：单边行情爆仓 / 选股 / 资金管理

### 3.3 涨停板战法

- **核心规则**：① 首板涨停 + 板块共振 ② 二板分歧转强 ③ N 板接力 ④ 炸板率过滤 ⑤ 次日开盘价止盈/止损
- **A 股证据**：纯打板夏普低（盈亏比好但胜率 < 40%）；叠加"板块 + 量价"过滤后年化 20-50%（高风险）
- **数据需求**：涨停炸板日线 + 板块成分股 ✅
- **工具需求**：需新增 `get_limit_up_pool`
- **实施难度**：高
- **推荐度**：⭐⭐（争议大，alpha 衰减快，监管风险）
- **风险**：操纵认定 / 流动性枯竭 / 政策风险

### 3.4 龙虎榜机构席位策略

- **核心规则**：① 机构专用席位单日净买入 top 5 ② 后续 N 日持有 ③ 配合基本面过滤
- **A 股证据**：长期跑赢，但 2018 后机构席位合并 / 量化砸盘导致衰减
- **数据需求**：龙虎榜日表（tushare `top_list`）✅
- **工具需求**：需新增 `get_dragon_tiger_signals`
- **实施难度**：中
- **推荐度**：⭐⭐
- **风险**：滞后性 + 主力陷阱

### 3.5 北向资金因子

- **核心规则**：① 北向资金 20 日净流入 top 30 ② 持仓变化率 top 30 ③ 跟随策略
- **A 股证据**：2017-2020 显著 alpha；2021 后与主力资金趋同，alpha 减弱
- **数据需求**：北向日级 + 个股持仓 ✅（Tushare `moneyflow_hsgt`）
- **工具需求**：可纯 YAML（叠加在个股分析中）
- **实施难度**：低
- **推荐度**：⭐⭐⭐
- **风险**：北向数据有 1 日延迟 / 样本变化

## 4. Tier 3：争议 / 已衰减 / 需谨慎

| 策略 | 状态 | 备注 |
|---|---|---|
| 机器学习 Alpha（XGBoost / NN） | ⚠️ 2018 后衰减 | 维护成本高，建议作研究方向 |
| 高送转 / 限售解禁事件 | ⚠️ alpha decay | 已变成散户反向指标 |
| 重组/并购套利 | ⚠️ 政策变化 | 注册制后大幅减少 |
| ST 摘帽策略 | ⚠️ 高风险 | 小市值壳价值已被注册制抹平 |
| 可转债双低 | ✅ 跨资产 | 项目无转债支持，单独项目做 |

## 5. 数据源依赖 + Tushare 积分门槛

| 数据 | Tushare 积分 | 状态 | 备选数据源 |
|---|:-:|:-:|---|
| 日线（不复权） | 2000+ | ✅ | AkShare `stock_zh_a_hist` |
| 日线（后复权） | 2000+ | ✅ | AkShare `stock_zh_a_hist` `adjust='hfq'` |
| 实时行情 | 5000+ | ✅ Pro | AkShare `stock_zh_a_spot_em` |
| 财务三表（fina_indicator） | 2000+ | ✅ | AkShare `stock_financial_abstract_ths`（质量略差） |
| 板块（stock_basic industry） | 2000+ | ✅ 申万 2014 | 申万官网 / 中信指数 |
| 北向资金（moneyflow_hsgt） | 2000+ | ✅ | 东方财富 / Wind |
| 龙虎榜（top_list） | 2000+ | ✅ | 同花顺 / 东方财富 |
| 行业成分股 | 2000+ | ✅ | 中证指数 / 申万 |
| 概念板块（concept） | 5000+ | ✅ | 同花顺 / 东方财富 |
| 宏观（PMI/CPI/PPI） | 2000+ | ✅ | 国家统计局 |

**说明**：Tushare Pro 接口需要 2000+ 积分才稳定。本次新增工具对 PE_TTM、ROE、total_mv 的依赖 = 2000+ 积分门槛。降级方案：用 AkShare 实时行情（包含 PE/PB/总市值）+ 财务三表。

## 6. 工具与 YAML 设计

### 6.1 新增 3 个因子工具

| 工具 | 功能 | 关键参数 |
|---|---|---|
| `get_factor_universe` | A 股股票池 + 行业分类 | region / exclude_st / min_market_cap |
| `get_factor_scores` | 因子 Z-score + 行业中性化 | universe / factors / neutral / min_industry_size |
| `get_universe_screen` | 因子合成 + 排序选股 | factors (权重和=1.0) / top_n / industry_limit |

**关键设计决策**：
1. 因子计算顺序：log/signed-log 变换 → MAD 裁剪 → Z-score
2. `industry="未知"` 的股票被排除（不被纳入横截面）
3. 行业样本 < `min_industry_size`（默认 5）时回退到全局 Z-score（标 `small_group`）
4. 因子缺失时等比放大其他因子权重（不是简单填 0）
5. 输出 `factor_data_quality` 标志（ok / factor_missing / excluded / small_group）
6. 输出 `factor_quantiles`（行业内分位数排名 0-1）

### 6.2 新增 5 个策略 YAML

| 策略 | default_priority | market_regimes | 工具依赖 |
|---|:-:|---|---|
| `sector_rotation` | 12 | trending_up, sector_hot | 复用 `get_sector_rankings` + 4 个现有工具 |
| `short_term_reversal` | 14 | trending_down, sideways | 复用 `get_daily_history` + `analyze_trend` |
| `multi_factor` | 15 | trending_up, sideways | **新工具** `get_factor_scores` + `get_universe_screen` |
| `momentum_12_1` | 18 | trending_up | 复用 `get_daily_history` + `analyze_trend` |
| `pead_drift` | 20 | trending_up, sideways | 复用 `get_stock_info` + `search_stock_news` |

**与现有策略的边界**：
- `multi_factor` vs `growth_quality`：前者关注横截面（个股在同行业中的位置），后者单股质量评分。
- `sector_rotation` vs `dragon_head`：前者关注板块级排名，后者关注个股级龙头识别。
- `short_term_reversal` vs `bottom_volume`：前者强调 5-10 日超跌 + 趋势过滤（跌幅+趋势主导），后者强调"放量见底"（量能主导）。
- `momentum_12_1` vs `bull_trend`：前者偏 11 月长期动量（剔除最近 1 月），后者偏 5/10/20 日 MA 排列。
- `pead_drift` vs `event_driven`：前者特指"业绩超预期"基本面事件，后者覆盖所有事件（业绩/政策/订单/并购等）。

## 7. LLM Agent 与传统量化的差异边界

| 维度 | 经典量化 | LLM Agent |
|---|---|---|
| 决策模式 | 程序化规则 | 自然语言推理 |
| 上下文窗口 | 无限 | 8K-200K tokens |
| 计算精度 | 浮点 64 | 浮点 16-32 |
| 一致性 | 完全可重复 | 有随机性（temperature > 0） |
| 因子合成 | 严格加权 | 模糊推理 |

**结论**：
- ✅ 因子**计算**应该在工具层（精确、缓存）
- ✅ 因子**解读**可以让 LLM 自由发挥
- ⚠️ 横截面**排序**可以 LLM 决策（30 只内可控），但**持仓**和**调仓时机**应该规则化
- ⚠️ `multi_factor.yaml` 明确：只输出**个股的横截面评分**和**top N 选股建议**，不输出具体持仓比例

## 8. 如何在本项目验证策略

### 8.1 现有回测能力

项目已实现 `BACKTEST_ENABLED` 框架 + 多个 backtest 工具：
- `get_skill_backtest_summary`（单策略回测）
- `get_strategy_backtest_summary`（策略对比）
- `get_stock_backtest_summary`（单股历史回测）

**局限**：这些工具基于"历史分析记录"，不是"基于历史数据的纯量化回测"。新策略需要积累运行数据后才能回测。

### 8.2 推荐验证步骤

```bash
# 1. 离线验证：单元测试（已完成）
python -m pytest tests/test_factor_tools.py -v
# 应通过 7+ 个测试

# 2. 集成验证：启动后 /strategies 列表
python main.py --serve
# 钉钉/飞书发 /strategies，应列出 20 个策略（含本次新增 5 个）

# 3. 单股多因子评分验证
# /ask 600519 多因子
# 应调用 get_factor_scores，返回该股的 7 因子 Z-score

# 4. 选股验证
# /ask 多因子选股 top 30
# 应调用 get_universe_screen，返回 30 只股票 + 行业分散约束

# 5. 实盘跟踪
# 在 BACKTEST_ENABLED=true 模式下，让策略运行 1-3 月
# 每月初比较因子得分变化与实际股价表现
# 检验 IC（信息系数 = 因子得分 vs 收益的相关性）
```

### 8.3 数据源稳定性检查

新工具对 Tushare 2000 积分有依赖。在生产前需验证：
- `manager.get_stock_list()` 能拉到全 A 股（4000+ 标的）
- `manager.get_realtime_quote()` 能拿到 PE/PB/total_mv
- `manager.get_fundamental_context()` 能拿到 growth.roe

如有不稳定，需配置 `FACTOR_DATA_SOURCE_FALLBACK`（本期未实现）。

## 9. 风险与权衡

### 9.1 学术 / 工程双轨

- **学术**：每个策略配 1-2 篇一手论文（中文优先，列于 §2）
- **工程**：每个新工具配 7 个单元测试（已完成）
- **用户侧**：用 `BACKTEST_ENABLED` + `get_universe_screen` 自行验证

### 9.2 LLM 风险

| 风险 | 缓解 |
|---|---|
| LLM 改写因子权重 | 工具入参固定权重，LLM 不能改写 |
| LLM 自由编造数据 | 工具输出结构化 JSON，LLM 解读 |
| LLM token 超限 | `top_n` 默认 30 足够小，> 100 时警告 |
| LLM 一致性差 | 因子计算在工具层，LLM 仅做选择/解读 |

### 9.3 工程风险

| 风险 | 概率 | 缓解 |
|---|:-:|---|
| Tushare 2000 积分不足 | 中 | 文档化门槛，配置回退到 AkShare |
| 全 A 股拉 5000+ 行慢 | 中 | 1 小时缓存 + 默认排除 ST / 小市值 |
| 行业分类版本不统一 | 中 | 默认申万 2014，文档说明 |
| 重复注册工具 | 低 | 启动时检查 + warning + 跳过 |
| 缓存击穿 | 低 | Lock 保护 |

### 9.4 学术 / 民间争议

- 配对交易 / 涨停板 / 龙虎榜 类策略可能触碰短线操纵认定边界，使用者自负合规责任
- 量化策略在大盘系统性风险时可能集体失效
- 因子衰减不可避免，需定期复检

## 10. 未验证项声明

本次 v0.1 **明确未验证**的事项：

- ❌ 真实 Tushare 数据下因子计算的精度
- ❌ 行业中性化在 A 股 31 个申万一级行业的实际效果
- ❌ `get_universe_screen` 在 4000+ 标的上的执行时间（预估 < 30s，需实测）
- ❌ 7 个单元测试的覆盖率（仅核心逻辑，未覆盖所有边界）
- ❌ 工具的 LLM 兼容性（schema 是否被 LLM 正确理解）
- ❌ 5 个 YAML 策略的实战胜率（需 1-3 月实盘跟踪）

**这些未验证项是用户决策依据，请勿将本备忘视为"经实战验证的策略集"。**

## 11. 后续计划（v0.2+）

| 阶段 | 内容 | 预期时间 |
|:-:|---|:-:|
| v0.1（本次） | 5 个 YAML + 3 个工具 + 备忘 | 已完成 |
| v0.2 | 配对交易工具 + 海龟法则强化 | 1-2 月 |
| v0.3 | 红利低波 / 美林时钟 | 1-2 月 |
| v0.4 | 网格交易 / 北向资金因子 | 2-3 月 |
| v0.5 | 涨停板 / 龙虎榜（争议大，谨慎） | 视情况 |

## 12. 引用与参考

### 12.1 一手论文

1. Fama, E. F., & French, K. R. (1993). Common risk factors in the returns on stocks and bonds. *Journal of Financial Economics*, 33(1), 3-56.
2. Asness, C. S. (1995). The power of past stock returns to predict future stock returns. *Working paper*, Goldman Sachs Asset Management.
3. Jegadeesh, N. (1990). Evidence of predictable behavior of security returns. *Journal of Finance*, 45(3), 881-898.
4. Ball, R., & Brown, P. (1968). An empirical evaluation of accounting income numbers. *Journal of Accounting Research*, 6(2), 159-177.
5. Gatev, E., Goetzmann, W. N., & Rouwenhorst, K. G. (2006). Pairs trading: Performance of a relative-value arbitrage rule. *Review of Financial Studies*, 19(3), 797-827.
6. Carhart, M. M. (1997). On persistence in mutual fund performance. *Journal of Finance*, 52(1), 57-82.

### 12.2 A 股中文论文

1. 潘莉, 徐建国. (2011). A 股市场的三因子模型. *金融研究*.
2. 高秋明, 熊伟. (2014). 12-1 动量策略在中国 A 股市场. *数量经济技术经济研究*.
3. 王永宏, 赵学军. (2001). 中国股市"惯性策略"和"反转策略"的实证分析. *经济研究*.
4. 鲁臻, 邹恒甫. (2007). 中国股市的惯性与反转效应研究. *经济研究*.
5. 王化成. (2004). 盈利公告漂移. *会计研究*.
6. 张永任. (2010. PEAD 在中国 A 股的实证. *金融研究*.
7. 陈守东. (2006). 配对交易在中国股市的实证. *数量经济技术经济研究*.

### 12.3 卖方研究（行业实践）

- 申万宏源 / 中信证券 / 国泰君安 / 海通证券 行业轮动研报 2008-2023
- 集思录 可转债双低策略社区数据
- 淘股吧 涨停板战法社区共识

## 13. 文档元数据

- 创建：2025-06-07（路径 `docs/strategy-research/a-share-quant-gaps.md`）
- 关联改动：5 个策略 YAML + 1 个工具模块 + 7 个单元测试 + CHANGELOG/INDEX
- 维护：项目 AI 协作流程（用户审阅）
- 反馈：在项目 Issue 标记 `research` 标签

---

**免责说明**：本备忘仅供学习与研究使用，不构成投资建议。策略实施需用户自行承担合规与盈亏责任。
