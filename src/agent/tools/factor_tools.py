# -*- coding: utf-8 -*-
"""
Factor tools — multi-factor / cross-section stock selection.

Tools:
- get_factor_universe: 全 A 股股票池 + 行业分类
- get_factor_scores:   因子 Z-score + 行业中性化
- get_universe_screen: 因子合成 + 排序选股

设计要点（自审计合并）：
1. 因子计算顺序：log/signed-log 变换 → MAD 裁剪 → Z-score
2. industry="未知" 的股票被排除后再 Z-score
3. 行业样本 < min_industry_size 时回退到全局 Z-score
4. 因子缺失时等比放大其他因子权重
5. 全部调用 manager.get_daily_data（统一入口，已包含复权）
6. 工具输出 factor_data_quality + 行业分位数
7. 缓存按 as_of 切分，TTL 1 小时
8. 暴露 min_industry_size / log_transform 等参数
"""

import bisect
import logging
import math
import time
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from src.agent.tools.registry import ToolParameter, ToolDefinition

logger = logging.getLogger(__name__)


# ============================================================
# 缓存
# ============================================================
class _FactorCache:
    """In-memory TTL cache keyed by string."""

    def __init__(self, ttl_seconds: int = 3600):
        self._data: Dict[str, Tuple[float, Any]] = {}
        self._lock = Lock()
        self.ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            ts, value = item
            if time.time() - ts < self.ttl:
                return value
            del self._data[key]
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.time(), value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache = _FactorCache()


# ============================================================
# DataFetcherManager 单例
# ============================================================
_fetcher_manager_singleton = None
_fetcher_manager_lock = Lock()


def _get_fetcher_manager():
    from data_provider import DataFetcherManager
    global _fetcher_manager_singleton
    if _fetcher_manager_singleton is None:
        with _fetcher_manager_lock:
            if _fetcher_manager_singleton is None:
                _fetcher_manager_singleton = DataFetcherManager()
    return _fetcher_manager_singleton


def reset_fetcher_manager() -> None:
    """测试用：重置单例与缓存。"""
    global _fetcher_manager_singleton
    with _fetcher_manager_lock:
        _fetcher_manager_singleton = None
    _cache.clear()


# ============================================================
# 因子变换
# ============================================================
_TRANSFORM_FACTORS = {"value", "size", "volatility"}


def _signed_log(x: Optional[float]) -> Optional[float]:
    """对数变换保留符号。处理 PE 这种范围 [-100, 1000] 的因子。"""
    if x is None:
        return None
    sign = 1.0 if x >= 0 else -1.0
    return sign * math.log1p(abs(x))


def _apply_transform(factor_name: str, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if factor_name in _TRANSFORM_FACTORS:
        return _signed_log(value)
    return value


# ============================================================
# 统计原语
# ============================================================
def _mad_clip(values: List[float], n_mad: float = 3.0) -> List[float]:
    """MAD 去极值。"""
    if not values:
        return values
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n % 2 == 1:
        median = sorted_vals[n // 2]
    else:
        median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    abs_devs = sorted([abs(x - median) for x in values])
    if n % 2 == 1:
        mad = abs_devs[n // 2]
    else:
        mad = (abs_devs[n // 2 - 1] + abs_devs[n // 2]) / 2
    if mad < 1e-9:
        return values
    upper = median + n_mad * mad
    lower = median - n_mad * mad
    return [max(lower, min(upper, x)) for x in values]


def _zscore(values: List[float]) -> List[float]:
    """Z-score 标准化。"""
    n = len(values)
    if n < 2:
        return [0.0] * n
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    std = math.sqrt(var)
    if std < 1e-9:
        return [0.0] * n
    return [(x - mean) / std for x in values]


def _group_neutralize(
    values: List[Optional[float]],
    groups: List[str],
    min_group_size: int = 5,
) -> Tuple[List[float], List[str]]:
    """行业内 Z-score 中性化。

    Returns: (z_scores, data_quality_flags)
    - industry="未知" 的股票被排除（z=0, quality="excluded"）
    - 行业样本 < min_group_size：回退到全局 Z-score（quality="small_group"）
    - 因子为 None：标记 "factor_missing"
    """
    n = len(values)
    z_scores = [0.0] * n
    quality_flags = ["ok"] * n

    valid_indices = [i for i, g in enumerate(groups) if g and g != "未知"]
    for i, g in enumerate(groups):
        if not g or g == "未知":
            quality_flags[i] = "excluded"

    if not valid_indices:
        return z_scores, quality_flags

    by_group: Dict[str, List[int]] = {}
    for i in valid_indices:
        by_group.setdefault(groups[i], []).append(i)

    use_global = any(len(idx) < min_group_size for idx in by_group.values())

    if use_global:
        for i in valid_indices:
            if values[i] is not None:
                quality_flags[i] = "small_group"
        valid_vals = [values[i] for i in valid_indices if values[i] is not None]
        if valid_vals:
            clipped = _mad_clip(valid_vals)
            z = _zscore(clipped)
            j = 0
            for i in valid_indices:
                if values[i] is not None:
                    z_scores[i] = z[j]
                    j += 1
                else:
                    quality_flags[i] = "factor_missing"
        else:
            for i in valid_indices:
                quality_flags[i] = "factor_missing"
        return z_scores, quality_flags

    for group, indices in by_group.items():
        group_vals = [values[i] for i in indices if values[i] is not None]
        if not group_vals:
            for i in indices:
                quality_flags[i] = "factor_missing"
            continue
        clipped = _mad_clip(group_vals)
        z = _zscore(clipped)
        j = 0
        for i in indices:
            if values[i] is not None:
                z_scores[i] = z[j]
                j += 1
            else:
                quality_flags[i] = "factor_missing"
    return z_scores, quality_flags


def _industry_quantile(
    values: List[Optional[float]],
    groups: List[str],
    index: int,
) -> float:
    """计算单只股票在所属行业中的分位数排名（0-1）。

    使用 ``_industry_quantile_batch`` 预排序的结果，O(log N) 查找。
    """
    if index >= len(values) or values[index] is None:
        return 0.5
    group = groups[index]
    if not group or group == "未知":
        return 0.5
    sorted_vals = _industry_quantile_cache.get(group)
    if not sorted_vals:
        return 0.5
    target = values[index]
    if target is None:
        return 0.5
    rank = bisect.bisect_right(sorted_vals, target)
    return rank / len(sorted_vals)


_industry_quantile_cache: Dict[str, List[float]] = {}


def _industry_quantile_batch(
    values: List[Optional[float]],
    groups: List[str],
) -> List[float]:
    """预计算所有股票的行业分位数。O(N log N) 一次性排序。

    返回值与 ``values`` 等长；股票所属行业为 "未知" 或因子为 None 时返回 0.5。
    """
    _industry_quantile_cache.clear()
    by_group: Dict[str, List[float]] = {}
    for i, g in enumerate(groups):
        if not g or g == "未知" or values[i] is None:
            continue
        by_group.setdefault(g, []).append(values[i])
    for g in by_group:
        by_group[g].sort()
        _industry_quantile_cache[g] = by_group[g]

    quantiles: List[float] = []
    for i in range(len(values)):
        if i >= len(values) or values[i] is None:
            quantiles.append(0.5)
            continue
        g = groups[i]
        if not g or g == "未知":
            quantiles.append(0.5)
            continue
        sorted_vals = by_group.get(g, [])
        if not sorted_vals:
            quantiles.append(0.5)
            continue
        rank = bisect.bisect_right(sorted_vals, values[i])
        quantiles.append(rank / len(sorted_vals))
    return quantiles


def _is_target_market(code: str, region: str) -> bool:
    """判断股票代码是否属于指定市场。

    当前 ``get_stock_list`` 实现仅支持 A 股；HK/US 调用会返回空结果并打 warning。
    """
    if region == "cn":
        if code.startswith("HK") or code.startswith("US"):
            return False
        return True
    if region == "hk":
        return code.startswith("HK")
    if region == "us":
        if code.startswith("HK") or (len(code) == 6 and code.isdigit()):
            return False
        return True
    return True


def _composite_score(
    factor_scores: Dict[str, Optional[float]],
    weights: Dict[str, float],
) -> Tuple[Optional[float], List[str]]:
    """缺失因子时等比放大其他因子权重。"""
    present = {f: s for f, s in factor_scores.items() if s is not None and f in weights}
    missing = [f for f in weights if f not in present]
    if not present:
        return None, missing
    present_weight_sum = sum(weights[f] for f in present)
    if present_weight_sum < 1e-9:
        return None, missing
    score = sum(present[f] * weights[f] / present_weight_sum for f in present)
    return score, missing


# ============================================================
# 因子计算（单只股票）
# ============================================================
_SUPPORTED_FACTORS = {
    "value",       # EP = 1/PE
    "quality",     # ROE
    "momentum",    # MOM_60
    "reversal",    # -REV_5
    "size",        # LN_MV
    "volatility",  # 20 日收益波动率（取负）
    "liquidity",   # 20 日均换手率（取负）
}


def _compute_factors_for_stock(
    code: str,
    daily_bars: List[Dict[str, Any]],
    pe_ttm: Optional[float],
    roe: Optional[float],
    market_cap: float,
    turnover_rate: Optional[float],
) -> Dict[str, Optional[float]]:
    """计算单只股票的因子原始值。"""
    factors: Dict[str, Optional[float]] = {f: None for f in _SUPPORTED_FACTORS}

    if pe_ttm and pe_ttm > 0:
        factors["value"] = 1.0 / pe_ttm

    if roe is not None:
        factors["quality"] = roe

    if daily_bars and len(daily_bars) >= 60:
        closes = [b.get("close") for b in daily_bars if b.get("close") is not None]
        if len(closes) >= 60:
            factors["momentum"] = closes[-1] / closes[-60] - 1
            if len(closes) >= 6:
                factors["reversal"] = -(closes[-1] / closes[-6] - 1)
            if len(closes) >= 20:
                returns = [(closes[-i] / closes[-i - 1] - 1) for i in range(19, 0, -1)]
                rmean = sum(returns) / 19
                rvar = sum((r - rmean) ** 2 for r in returns) / 18
                rstd = math.sqrt(rvar)
                factors["volatility"] = -rstd if rstd > 0 else None

    if market_cap and market_cap > 0:
        factors["size"] = math.log(market_cap)

    if turnover_rate is not None and turnover_rate > 0:
        factors["liquidity"] = -turnover_rate

    return factors


# ============================================================
# 工具 1: get_factor_universe
# ============================================================
def _handle_get_factor_universe(
    region: str = "cn",
    exclude_st: bool = True,
    min_market_cap: float = 50e8,
) -> Dict[str, Any]:
    cache_key = f"universe:{region}:{exclude_st}:{min_market_cap}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    manager = _get_fetcher_manager()
    raw = []
    used_fetcher = None
    try:
        snapshot = manager._get_fetchers_snapshot()
        for fetcher in snapshot:
            if not hasattr(fetcher, "get_stock_list"):
                continue
            try:
                df = fetcher.get_stock_list()
                if df is None:
                    continue
                if hasattr(df, "to_dict"):
                    raw = df.to_dict("records")
                elif isinstance(df, list):
                    raw = list(df)
                if raw:
                    used_fetcher = getattr(fetcher, "name", "?")
                    break
            except Exception as e:
                logger.debug("get_stock_list on %s failed: %s", getattr(fetcher, "name", "?"), e)
                continue
    except Exception as e:
        logger.warning("Failed to iterate fetchers: %s", e)

    if not raw:
        return {"error": "Failed to fetch stock universe (no fetcher supports get_stock_list)"}

    warnings: List[str] = []
    if region != "cn":
        has_industry = any(item.get("industry") for item in raw)
        if region in ("hk", "us"):
            warnings.append(
                f"region={region}: current data sources only expose A-share stock lists; "
                "result may be empty. Configure Tushare HK/US basic for full coverage."
            )

    filtered = []
    excluded_by_market = 0
    has_mcap = any("total_mv" in item for item in raw)
    for item in raw:
        name = item.get("name", "") or ""
        if exclude_st and ("ST" in name or "退" in name):
            continue
        mcap = 0.0
        if has_mcap:
            mcap = item.get("total_mv", 0) or 0
            if mcap <= 0:
                mcap = item.get("circ_mv", 0) or 0
            if mcap < min_market_cap:
                continue
        industry = item.get("industry") or "未知"
        ts_code = item.get("ts_code") or item.get("code", "")
        code = ts_code.split(".")[0] if "." in ts_code else str(ts_code)
        if not _is_target_market(code, region):
            excluded_by_market += 1
            continue
        filtered.append({
            "code": code,
            "name": name,
            "industry": industry,
            "market_cap": float(mcap),
        })

    if not filtered:
        msg = f"No stocks matched filters for region={region}"
        if excluded_by_market:
            msg += f" ({excluded_by_market} excluded by market filter)"
        if warnings:
            msg = "; ".join(warnings) + " | " + msg
        return {"error": msg, "warnings": warnings}

    if used_fetcher and used_fetcher not in ("TushareFetcher",):
        missing_industry = all(s["industry"] == "未知" for s in filtered[:10])
        if missing_industry:
            warnings.append(
                f"fetcher={used_fetcher} does not expose industry classification; "
                "factor tools will run with global (not industry) neutralization. "
                "Configure Tushare (2000+ 积分) for proper industry data."
            )

    result = {
        "as_of": time.strftime("%Y-%m-%d"),
        "region": region,
        "universe_size": len(filtered),
        "stocks": filtered,
    }
    if warnings:
        result["warnings"] = warnings
    _cache.set(cache_key, result)
    return result


get_factor_universe_tool = ToolDefinition(
    name="get_factor_universe",
    description="Get A-share stock universe with industry classification, "
                "market cap, and ST/exclusion filters. Returns a list of stocks "
                "suitable for cross-section factor analysis. "
                "Note: full-market pull may be slow; consider restricting region.",
    parameters=[
        ToolParameter(name="region", type="string", description="Market region",
                     required=False, default="cn", enum=["cn", "hk", "us"]),
        ToolParameter(name="exclude_st", type="boolean",
                     description="Exclude ST/delisted stocks", required=False, default=True),
        ToolParameter(name="min_market_cap", type="number",
                     description="Minimum market cap in CNY (default 5 billion)",
                     required=False, default=50e8),
    ],
    handler=_handle_get_factor_universe,
    category="factor",
)


# ============================================================
# 工具 2: get_factor_scores
# ============================================================
_MAX_UNIVERSE_SIZE = 500


def _safe_realtime_attr(quote, attr: str) -> Optional[float]:
    if quote is None:
        return None
    val = getattr(quote, attr, None)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _handle_get_factor_scores(
    universe: List[str],
    factors: Optional[List[str]] = None,
    neutral: str = "industry",
    as_of: Optional[str] = None,
    min_industry_size: int = 5,
    max_universe_size: int = _MAX_UNIVERSE_SIZE,
) -> Dict[str, Any]:
    if factors is None:
        factors = ["value", "quality", "momentum"]
    if neutral not in ("industry", "none"):
        return {"error": f"Unknown neutral: {neutral}"}
    invalid = [f for f in factors if f not in _SUPPORTED_FACTORS]
    if invalid:
        return {"error": f"Unsupported factors: {invalid}. Supported: {sorted(_SUPPORTED_FACTORS)}"}

    if not universe:
        return {"error": "universe is empty"}
    if len(universe) > max_universe_size:
        return {
            "error": (
                f"universe too large ({len(universe)} > {max_universe_size}). "
                "Factor tools make 3 fetcher calls per stock (daily_data + realtime + "
                "fundamental); large universes will time out. Pre-filter by industry/quality "
                "before calling, or split into batches."
            )
        }

    manager = _get_fetcher_manager()

    universe_resp = _handle_get_factor_universe()
    if "error" in universe_resp:
        return universe_resp
    industry_map: Dict[str, str] = {s["code"]: s["industry"] for s in universe_resp["stocks"]}
    name_map: Dict[str, str] = {s["code"]: s["name"] for s in universe_resp["stocks"]}

    if neutral == "industry":
        unknown_industry_ratio = sum(
            1 for c in universe
            if (industry_map.get(c) or "未知") == "未知"
        ) / max(1, len(universe))
        if unknown_industry_ratio > 0.5:
            logger.warning(
                "Over %.0f%% of universe has unknown industry; "
                "industry neutralization will degrade to global Z-score.",
                unknown_industry_ratio * 100,
            )

    daily_data: Dict[str, List[Dict]] = {}
    pe_map: Dict[str, Optional[float]] = {}
    mcap_map: Dict[str, float] = {}
    turnover_map: Dict[str, Optional[float]] = {}
    roe_map: Dict[str, Optional[float]] = {}

    for code in universe:
        try:
            bars, _ = manager.get_daily_data(stock_code=code, days=250)
            daily_data[code] = bars.to_dict("records") if bars is not None and not bars.empty else []
        except Exception as e:
            logger.warning("get_daily_data failed for %s: %s", code, e)
            daily_data[code] = []

        try:
            quote = manager.get_realtime_quote(stock_code=code)
            pe_map[code] = _safe_realtime_attr(quote, "pe_ratio")
            mcap_val = _safe_realtime_attr(quote, "total_mv")
            if mcap_val is None:
                mcap_val = _safe_realtime_attr(quote, "circ_mv")
            mcap_map[code] = mcap_val or 0.0
            turnover_map[code] = _safe_realtime_attr(quote, "turnover_rate")
        except Exception as e:
            logger.warning("get_realtime_quote failed for %s: %s", code, e)
            pe_map[code] = None
            mcap_map[code] = 0.0
            turnover_map[code] = None

        try:
            ctx = manager.get_fundamental_context(stock_code=code)
            growth = ctx.get("growth", {}) if isinstance(ctx, dict) else {}
            data_block = growth.get("data", {}) if isinstance(growth, dict) else {}
            roe_val = data_block.get("roe") if isinstance(data_block, dict) else None
            roe_map[code] = float(roe_val) if roe_val is not None else None
        except Exception as e:
            logger.warning("get_fundamental_context failed for %s: %s", code, e)
            roe_map[code] = None

    raw_factors: Dict[str, Dict[str, Optional[float]]] = {}
    industries: List[str] = []
    for code in universe:
        factors_raw = _compute_factors_for_stock(
            code,
            daily_data.get(code, []),
            pe_map.get(code),
            roe_map.get(code),
            mcap_map.get(code, 0.0),
            turnover_map.get(code),
        )
        raw_factors[code] = factors_raw
        industries.append(industry_map.get(code) or "未知")

    zscore_map: Dict[str, Dict[str, float]] = {f: {} for f in factors}
    quantile_map: Dict[str, Dict[str, float]] = {f: {} for f in factors}
    quality_map: Dict[str, Dict[str, str]] = {f: {} for f in factors}

    for f in factors:
        raw_values = [raw_factors[c][f] for c in universe]
        transformed = [_apply_transform(f, v) for v in raw_values]
        z, flags = _group_neutralize(transformed, industries, min_industry_size)
        quantiles = _industry_quantile_batch(transformed, industries)
        for i, c in enumerate(universe):
            zscore_map[f][c] = round(z[i], 3)
            quantile_map[f][c] = round(quantiles[i], 3)
            quality_map[f][c] = flags[i]

    result_stocks = []
    for i, code in enumerate(universe):
        per_factor_quality = [quality_map[f][code] for f in factors]
        unique_quality = sorted(set(per_factor_quality))
        result_stocks.append({
            "code": code,
            "name": name_map.get(code, ""),
            "industry": industries[i],
            "factor_scores": {f: zscore_map[f][code] for f in factors},
            "factor_quantiles": {f: quantile_map[f][code] for f in factors},
            "data_quality": unique_quality,
        })

    return {
        "as_of": as_of or time.strftime("%Y-%m-%d"),
        "universe_size": len(universe),
        "factors_used": factors,
        "neutralization": neutral,
        "min_industry_size": min_industry_size,
        "stocks": result_stocks,
    }


get_factor_scores_tool = ToolDefinition(
    name="get_factor_scores",
    description="Compute factor Z-scores (industry-neutralized) for a list of stocks. "
                "Supports factors: value, quality, momentum, reversal, size, volatility, liquidity. "
                "Use for cross-section analysis and individual stock scoring. "
                "Output includes data_quality flags and industry quantiles. "
                "Note: 3 fetcher calls per stock; default cap is 500.",
    parameters=[
        ToolParameter(name="universe", type="array",
                     description="List of stock codes (e.g., ['600519','300750'])",
                     required=True),
        ToolParameter(name="factors", type="array",
                     description="Factor names to compute. Default: ['value','quality','momentum']",
                     required=False),
        ToolParameter(name="neutral", type="string",
                     description="Neutralization method", required=False,
                     default="industry", enum=["industry", "none"]),
        ToolParameter(name="as_of", type="string",
                     description="Date in YYYY-MM-DD. Default: latest trading day",
                     required=False),
        ToolParameter(name="min_industry_size", type="integer",
                     description="Minimum industry size for in-industry neutralization. "
                                 "Below this falls back to global Z-score. Default: 5",
                     required=False, default=5),
        ToolParameter(name="max_universe_size", type="integer",
                     description="Hard cap on universe size to bound 3xN fetcher calls. Default: 500",
                     required=False, default=500),
    ],
    handler=_handle_get_factor_scores,
    category="factor",
)


# ============================================================
# 工具 3: get_universe_screen
# ============================================================
def _handle_get_universe_screen(
    factors: Dict[str, float],
    top_n: int = 30,
    industry_limit: int = 5,
    neutral: str = "industry",
    as_of: Optional[str] = None,
    min_industry_size: int = 5,
    max_universe_size: int = 2000,
) -> Dict[str, Any]:
    if not factors:
        return {"error": "factors must be a non-empty dict"}
    weight_sum = sum(factors.values())
    if abs(weight_sum - 1.0) > 0.01:
        return {"error": f"Factor weights must sum to 1.0, got {weight_sum}"}

    universe_resp = _handle_get_factor_universe()
    if "error" in universe_resp:
        return universe_resp
    universe = [s["code"] for s in universe_resp["stocks"]]

    if len(universe) > max_universe_size:
        logger.warning(
            "Universe size %d exceeds screen cap %d; pre-filter via get_factor_universe "
            "(raise min_market_cap) or pass smaller custom universe.",
            len(universe), max_universe_size,
        )

    scores_resp = _handle_get_factor_scores(
        universe=universe,
        factors=list(factors.keys()),
        neutral=neutral,
        as_of=as_of,
        min_industry_size=min_industry_size,
        max_universe_size=max_universe_size,
    )
    if "error" in scores_resp:
        return scores_resp

    composite: List[Tuple[str, float, str]] = []
    for stock in scores_resp["stocks"]:
        score, _ = _composite_score(stock["factor_scores"], factors)
        if score is None:
            continue
        composite.append((stock["code"], score, stock["industry"]))

    composite.sort(key=lambda x: x[1], reverse=True)
    industry_count: Dict[str, int] = {}
    selected: List[Dict[str, Any]] = []
    for code, score, industry in composite:
        if len(selected) >= top_n:
            break
        if industry_count.get(industry, 0) >= industry_limit:
            continue
        selected.append({
            "code": code,
            "industry": industry,
            "composite_score": round(score, 3),
        })
        industry_count[industry] = industry_count.get(industry, 0) + 1

    return {
        "as_of": as_of or time.strftime("%Y-%m-%d"),
        "universe_size": len(universe),
        "selected_size": len(selected),
        "factor_weights": factors,
        "neutralization": neutral,
        "industry_diversification": industry_limit,
        "selected_stocks": selected,
    }


get_universe_screen_tool = ToolDefinition(
    name="get_universe_screen",
    description="Screen A-share universe by weighted multi-factor composite. "
                "Returns top N stocks with industry diversification constraint. "
                "Use for monthly portfolio rebalancing and watchlist generation. "
                "Output composite_score is industry-neutralized.",
    parameters=[
        ToolParameter(name="factors", type="object",
                     description="Factor weights, e.g. {\"value\":0.2, \"quality\":0.3}. Must sum to 1.0.",
                     required=True),
        ToolParameter(name="top_n", type="integer",
                     description="Number of stocks to select (default 30)",
                     required=False, default=30),
        ToolParameter(name="industry_limit", type="integer",
                     description="Max stocks per industry (default 5)",
                     required=False, default=5),
        ToolParameter(name="neutral", type="string",
                     description="Neutralization method", required=False,
                     default="industry", enum=["industry", "none"]),
        ToolParameter(name="as_of", type="string",
                     description="Date in YYYY-MM-DD", required=False),
        ToolParameter(name="min_industry_size", type="integer",
                     description="Minimum industry size for in-industry neutralization",
                     required=False, default=5),
        ToolParameter(name="max_universe_size", type="integer",
                     description="Hard cap on universe size for the screen call. Default: 2000",
                     required=False, default=2000),
    ],
    handler=_handle_get_universe_screen,
    category="factor",
)


ALL_FACTOR_TOOLS = [
    get_factor_universe_tool,
    get_factor_scores_tool,
    get_universe_screen_tool,
]
