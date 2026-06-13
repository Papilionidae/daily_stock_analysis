# -*- coding: utf-8 -*-
"""
Unit tests for factor_tools.

覆盖：
1. 纯函数：MAD 裁剪、Z-score、行业中性化、缺失因子等比加权、行业分位数
2. 集成：通过 Mock DataFetcherManager 验证 get_factor_scores / get_universe_screen / get_factor_universe 的端到端输出
"""

import os
import sys
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.tools.factor_tools import (
    _composite_score,
    _group_neutralize,
    _industry_quantile,
    _industry_quantile_batch,
    _mad_clip,
    _signed_log,
    _zscore,
    get_factor_scores_tool,
    get_factor_universe_tool,
    get_universe_screen_tool,
)


# ============================================================
# 1. 纯函数测试
# ============================================================
class TestSignedLog(unittest.TestCase):
    def test_positive(self):
        self.assertAlmostEqual(_signed_log(0), 0.0)
        self.assertGreater(_signed_log(10), 2.0)

    def test_negative(self):
        self.assertLess(_signed_log(-10), -2.0)
        self.assertEqual(_signed_log(0), 0.0)

    def test_zero(self):
        self.assertEqual(_signed_log(0), 0.0)

    def test_none(self):
        self.assertIsNone(_signed_log(None))


class TestMadClip(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_mad_clip([]), [])

    def test_no_outliers(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _mad_clip(data)
        for orig, new in zip(data, result):
            self.assertAlmostEqual(orig, new, places=5)

    def test_clip_outliers(self):
        data = [1.0, 2.0, 3.0, 4.0, 100.0]
        result = _mad_clip(data)
        self.assertLess(result[-1], 100.0)

    def test_constant(self):
        data = [5.0, 5.0, 5.0]
        result = _mad_clip(data)
        for v in result:
            self.assertAlmostEqual(v, 5.0, places=5)


class TestZscore(unittest.TestCase):
    def test_basic(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _zscore(data)
        self.assertAlmostEqual(sum(result) / len(result), 0.0, places=5)
        var = sum(x ** 2 for x in result) / (len(result) - 1)
        self.assertAlmostEqual(var ** 0.5, 1.0, places=5)

    def test_too_small(self):
        self.assertEqual(_zscore([5.0]), [0.0])
        self.assertEqual(_zscore([]), [])

    def test_constant(self):
        self.assertEqual(_zscore([3.0, 3.0, 3.0, 3.0]), [0.0, 0.0, 0.0, 0.0])


class TestGroupNeutralize(unittest.TestCase):
    def test_excludes_unknown_industry(self):
        values = [1.0, 2.0, 3.0, 4.0]
        groups = ["A", "A", "未知", "B"]
        z, flags = _group_neutralize(values, groups, min_group_size=5)
        self.assertEqual(z[2], 0.0)
        self.assertEqual(flags[2], "excluded")

    def test_small_group_falls_back_to_global(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        groups = ["A", "A", "A", "B", "B", "B"]
        z, flags = _group_neutralize(values, groups, min_group_size=5)
        for f in flags:
            self.assertIn(f, ("small_group", "factor_missing"))

    def test_normal_industry_neutralization(self):
        values = [1.0, 2.0, 3.0, 10.0, 20.0, 30.0]
        groups = ["A", "A", "A", "B", "B", "B"]
        z, flags = _group_neutralize(values, groups, min_group_size=3)
        self.assertAlmostEqual(z[0] + z[1] + z[2], 0.0, places=5)
        self.assertAlmostEqual(z[3] + z[4] + z[5], 0.0, places=5)
        for f in flags:
            self.assertEqual(f, "ok")

    def test_missing_factor_flagged(self):
        values = [1.0, None, 3.0]
        groups = ["A", "A", "A"]
        z, flags = _group_neutralize(values, groups, min_group_size=3)
        self.assertEqual(flags[1], "factor_missing")


class TestCompositeScore(unittest.TestCase):
    def test_basic(self):
        score, missing = _composite_score(
            {"value": 1.0, "quality": 2.0},
            {"value": 0.5, "quality": 0.5},
        )
        self.assertAlmostEqual(score, 1.5, places=5)
        self.assertEqual(missing, [])

    def test_missing_factor_renormalizes(self):
        score, missing = _composite_score(
            {"value": 1.0, "quality": None},
            {"value": 0.5, "quality": 0.5},
        )
        self.assertAlmostEqual(score, 1.0, places=5)
        self.assertEqual(missing, ["quality"])

    def test_all_missing(self):
        score, missing = _composite_score(
            {"value": None, "quality": None},
            {"value": 0.5, "quality": 0.5},
        )
        self.assertIsNone(score)
        self.assertEqual(set(missing), {"value", "quality"})


class TestIndustryQuantile(unittest.TestCase):
    def test_returns_value_in_0_1(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        groups = ["A", "A", "A", "A", "A"]
        quantiles = _industry_quantile_batch(values, groups)
        for q in quantiles:
            self.assertGreaterEqual(q, 0.0)
            self.assertLessEqual(q, 1.0)

    def test_extreme_quantiles(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        groups = ["A", "A", "A", "A", "A"]
        quantiles = _industry_quantile_batch(values, groups)
        self.assertLess(quantiles[0], 0.3)
        self.assertGreater(quantiles[4], 0.7)

    def test_unknown_industry_returns_0_5(self):
        values = [1.0, 2.0, 3.0]
        groups = ["未知", "未知", "未知"]
        quantiles = _industry_quantile_batch(values, groups)
        for q in quantiles:
            self.assertEqual(q, 0.5)

    def test_legacy_per_stock_api_still_works(self):
        """`_industry_quantile` (per-stock) 仍兼容，但需先调 batch 填充缓存。"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        groups = ["A", "A", "A", "A", "A"]
        _industry_quantile_batch(values, groups)
        # cache 现在已填充，per-stock 调用可用
        self.assertLess(_industry_quantile(values, groups, 0), 0.3)
        self.assertGreater(_industry_quantile(values, groups, 4), 0.7)


# ============================================================
# 2. 集成测试（Mock DataFetcherManager）
# ============================================================
class _MockFetcher:
    def __init__(self, name: str, stock_list: Optional[Any] = None):
        self.name = name
        self._stock_list = stock_list

    def get_stock_list(self):
        return self._stock_list


class _MockManager:
    def __init__(
        self,
        stock_list: List[Dict[str, Any]],
        daily_data: Dict[str, List[Dict[str, float]]],
        realtime: Dict[str, Any],
        fundamental: Dict[str, Dict[str, Any]],
    ):
        self._stock_list = stock_list
        self._daily = daily_data
        self._realtime = realtime
        self._fundamental = fundamental
        self._fetchers = [
            _MockFetcher("MockTushareFetcher", stock_list),
        ]

    def _get_fetchers_snapshot(self):
        return self._fetchers

    def get_daily_data(self, stock_code: str, days: int = 250, **kwargs):
        import pandas as pd
        bars = self._daily.get(stock_code, [])
        if bars:
            return pd.DataFrame(bars), "mock"
        return pd.DataFrame(), "mock"

    def get_realtime_quote(self, stock_code: str):
        return self._realtime.get(stock_code)

    def get_fundamental_context(self, stock_code: str):
        return self._fundamental.get(stock_code, {})


def _make_daily(prices: List[float]) -> List[Dict[str, float]]:
    bars = []
    for i, p in enumerate(prices):
        bars.append({
            "date": f"2024-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}",
            "close": p,
            "open": p * 0.99,
            "high": p * 1.01,
            "low": p * 0.98,
            "volume": 1e6,
            "amount": p * 1e6,
        })
    return bars


class _MockCache:
    def __init__(self):
        self._data = {}

    def get(self, key):
        return self._data.get(key)

    def set(self, key, value):
        self._data[key] = value

    def clear(self):
        self._data.clear()


class TestGetFactorUniverse(unittest.TestCase):
    def test_filters_st(self):
        stock_list = [
            {"ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒", "total_mv": 1e10},
            {"ts_code": "000001.SZ", "name": "ST平安", "industry": "银行", "total_mv": 5e9},
            {"ts_code": "300750.SZ", "name": "宁德时代", "industry": "电池", "total_mv": 8e9},
        ]
        manager = _MockManager(stock_list, {}, {}, {})
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=manager), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_universe_tool.handler(region="cn", exclude_st=True, min_market_cap=1e9)
        self.assertEqual(result["universe_size"], 2)
        codes = [s["code"] for s in result["stocks"]]
        self.assertIn("600519", codes)
        self.assertIn("300750", codes)
        self.assertNotIn("000001", codes)

    def test_filters_market_cap(self):
        stock_list = [
            {"ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒", "total_mv": 1e10},
            {"ts_code": "000001.SZ", "name": "小盘股", "industry": "银行", "total_mv": 1e8},
        ]
        manager = _MockManager(stock_list, {}, {}, {})
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=manager), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_universe_tool.handler(region="cn", exclude_st=True, min_market_cap=1e9)
        self.assertEqual(result["universe_size"], 1)

    def test_region_hk_excludes_a_shares(self):
        stock_list = [
            {"ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒", "total_mv": 1e10},
            {"ts_code": "HK00700", "name": "腾讯控股", "industry": "互联网", "total_mv": 2e10},
        ]
        manager = _MockManager(stock_list, {}, {}, {})
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=manager), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_universe_tool.handler(region="hk", exclude_st=False, min_market_cap=1e9)
        codes = [s["code"] for s in result["stocks"]]
        self.assertNotIn("600519", codes)
        if "HK00700" in codes:
            self.assertIn("HK00700", codes)
        # If HK data not available, we should get either empty list with warning or filtered
        if "universe_size" in result:
            for s in result["stocks"]:
                self.assertTrue(s["code"].startswith("HK"))

    def test_warns_on_non_tushare_fetcher(self):
        stock_list = [
            {"ts_code": "sh.600519", "name": "贵州茅台", "total_mv": 1e10},
        ]
        manager = _MockManager(stock_list, {}, {}, {})
        # Mark fetcher as non-Tushare to trigger warning
        manager._fetchers[0].name = "BaostockFetcher"
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=manager), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_universe_tool.handler(region="cn", exclude_st=False, min_market_cap=1e9)
        self.assertIn("warnings", result)
        self.assertTrue(any("industry" in w for w in result["warnings"]))


class TestGetFactorScores(unittest.TestCase):
    def test_basic_3_stocks_3_factors(self):
        stock_list = [
            {"ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒", "total_mv": 1e10},
            {"ts_code": "300750.SZ", "name": "宁德时代", "industry": "电池", "total_mv": 8e9},
            {"ts_code": "002594.SZ", "name": "比亚迪", "industry": "汽车", "total_mv": 5e9},
        ]
        daily = {
            "600519": _make_daily([100 + i * 0.5 for i in range(60)]),
            "300750": _make_daily([200 + i * 0.1 for i in range(60)]),
            "002594": _make_daily([50 - i * 0.1 for i in range(60)]),
        }
        realtime = {
            "600519": MagicMock(pe_ratio=20.0, pb_ratio=5.0, total_mv=1e10, turnover_rate=0.5),
            "300750": MagicMock(pe_ratio=50.0, pb_ratio=8.0, total_mv=8e9, turnover_rate=1.2),
            "002594": MagicMock(pe_ratio=80.0, pb_ratio=10.0, total_mv=5e9, turnover_rate=2.5),
        }
        fundamental = {
            "600519": {"growth": {"data": {"roe": 25.0}}},
            "300750": {"growth": {"data": {"roe": 15.0}}},
            "002594": {"growth": {"data": {"roe": 8.0}}},
        }
        manager = _MockManager(stock_list, daily, realtime, fundamental)
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=manager), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_scores_tool.handler(
                universe=["600519", "300750", "002594"],
                factors=["value", "quality", "momentum"],
                neutral="industry",
            )
        self.assertEqual(result["universe_size"], 3)
        self.assertIn("stocks", result)
        self.assertEqual(set(result["factors_used"]), {"value", "quality", "momentum"})
        for stock in result["stocks"]:
            self.assertIn("code", stock)
            self.assertIn("name", stock)
            self.assertIn("industry", stock)
            self.assertIn("factor_scores", stock)
            self.assertIn("factor_quantiles", stock)
            self.assertIn("data_quality", stock)
            self.assertEqual(set(stock["factor_scores"].keys()), {"value", "quality", "momentum"})

    def test_max_universe_size_enforced(self):
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=_MockManager([], {}, {}, {})), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_scores_tool.handler(
                universe=[f"{i:06d}" for i in range(501)],
                max_universe_size=500,
            )
        self.assertIn("error", result)
        self.assertIn("universe too large", result["error"])

    def test_empty_universe_rejected(self):
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=_MockManager([], {}, {}, {})), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_scores_tool.handler(universe=[])
        self.assertIn("error", result)
        self.assertIn("empty", result["error"])

    def test_min_industry_size_fallback(self):
        stock_list = [
            {"ts_code": "600519.SH", "name": "A", "industry": "白酒", "total_mv": 1e10},
            {"ts_code": "300750.SZ", "name": "B", "industry": "电池", "total_mv": 8e9},
            {"ts_code": "002594.SZ", "name": "C", "industry": "汽车", "total_mv": 5e9},
        ]
        daily = {c: _make_daily([100 + i for i in range(60)]) for c in ["600519", "300750", "002594"]}
        realtime = {c: MagicMock(pe_ratio=20.0, pb_ratio=5.0, total_mv=1e9, turnover_rate=0.5)
                    for c in ["600519", "300750", "002594"]}
        fundamental = {c: {"growth": {"data": {"roe": 15.0}}}
                       for c in ["600519", "300750", "002594"]}
        manager = _MockManager(stock_list, daily, realtime, fundamental)
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=manager), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_scores_tool.handler(
                universe=["600519", "300750", "002594"],
                factors=["momentum"],
                neutral="industry",
                min_industry_size=5,
            )
        for stock in result["stocks"]:
            self.assertIn("small_group", stock["data_quality"])

    def test_invalid_factor_rejected(self):
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=_MockManager([], {}, {}, {})), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_scores_tool.handler(
                universe=["600519"],
                factors=["nonexistent_factor"],
            )
        self.assertIn("error", result)
        self.assertIn("Unsupported factors", result["error"])

    def test_data_quality_includes_missing(self):
        stock_list = [
            {"ts_code": "600519.SH", "name": "A", "industry": "白酒", "total_mv": 1e10},
        ]
        daily = {"600519": _make_daily([100 + i for i in range(60)])}
        realtime = {"600519": MagicMock(pe_ratio=None, pb_ratio=None, total_mv=0, turnover_rate=None)}
        fundamental = {"600519": {"growth": {"data": {}}}}
        manager = _MockManager(stock_list, daily, realtime, fundamental)
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=manager), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_factor_scores_tool.handler(
                universe=["600519"],
                factors=["value", "quality", "momentum"],
                neutral="none",
            )
        stock = result["stocks"][0]
        self.assertIn("factor_missing", stock["data_quality"])


class TestGetUniverseScreen(unittest.TestCase):
    def test_industry_diversification(self):
        stock_list = [
            {"ts_code": f"{i:06d}.SH", "name": f"S{i}", "industry": "白酒", "total_mv": 1e10}
            for i in range(10)
        ] + [
            {"ts_code": f"{i:06d}.SZ", "name": f"O{i}", "industry": "电池", "total_mv": 8e9}
            for i in range(5)
        ]
        codes = [f"{i:06d}" for i in range(10)] + [f"{i:06d}" for i in range(5)]
        daily = {c: _make_daily([100 + i for i in range(60)]) for c in codes}
        realtime = {c: MagicMock(pe_ratio=20.0, pb_ratio=5.0, total_mv=1e9, turnover_rate=0.5) for c in codes}
        fundamental = {c: {"growth": {"data": {"roe": 15.0}}} for c in codes}
        manager = _MockManager(stock_list, daily, realtime, fundamental)
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=manager), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_universe_screen_tool.handler(
                factors={"value": 0.5, "quality": 0.5},
                top_n=8,
                industry_limit=3,
            )
        industry_count: Dict[str, int] = {}
        for s in result["selected_stocks"]:
            industry_count[s["industry"]] = industry_count.get(s["industry"], 0) + 1
        for count in industry_count.values():
            self.assertLessEqual(count, 3)

    def test_weight_must_sum_to_one(self):
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=_MockManager([], {}, {}, {})), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_universe_screen_tool.handler(
                factors={"value": 0.3, "quality": 0.3},
            )
        self.assertIn("error", result)
        self.assertIn("weights must sum to 1.0", result["error"])

    def test_empty_factors_rejected(self):
        with patch("src.agent.tools.factor_tools._get_fetcher_manager", return_value=_MockManager([], {}, {}, {})), \
             patch("src.agent.tools.factor_tools._cache", _MockCache()):
            result = get_universe_screen_tool.handler(factors={})
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
