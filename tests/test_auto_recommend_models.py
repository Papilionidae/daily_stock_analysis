# -*- coding: utf-8 -*-
"""Tests for auto-recommend data models."""

import unittest
from datetime import datetime, timezone
from src.services.auto_recommend.models import (
    ChannelType,
    MarketPhase,
    AnalysisMode,
    SignalType,
    Candidate,
    MarketContext,
    RecommendationRecord,
    RecommendationResult,
)


class TestChannelType(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(ChannelType.THEME.value, "theme")
        self.assertEqual(ChannelType.SECTOR.value, "sector")
        self.assertEqual(ChannelType.FACTOR.value, "factor")
        self.assertEqual(ChannelType.TECHNICAL.value, "technical")
        self.assertEqual(ChannelType.ALPHASIFT.value, "alphasift")


class TestMarketPhase(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(MarketPhase.PREMARKET.value, "premarket")
        self.assertEqual(MarketPhase.INTRADAY.value, "intraday")
        self.assertEqual(MarketPhase.POSTMARKET.value, "postmarket")


class TestAnalysisMode(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(AnalysisMode.QUICK.value, "quick")
        self.assertEqual(AnalysisMode.PIPELINE.value, "pipeline")
        self.assertEqual(AnalysisMode.AGENT.value, "agent")


class TestSignalType(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(SignalType.BUY.value, "buy")
        self.assertEqual(SignalType.HOLD.value, "hold")
        self.assertEqual(SignalType.SELL.value, "sell")
        self.assertEqual(SignalType.WATCH.value, "watch")


class TestCandidate(unittest.TestCase):
    def test_minimal_candidate(self):
        c = Candidate(
            stock_code="600519",
            stock_name="贵州茅台",
            channel=ChannelType.SECTOR,
        )
        self.assertEqual(c.stock_code, "600519")
        self.assertEqual(c.stock_name, "贵州茅台")
        self.assertIs(c.channel, ChannelType.SECTOR)
        self.assertIsNone(c.channel_score)
        self.assertIsNone(c.sector)
        self.assertEqual(c.source_tags, [])

    def test_full_candidate(self):
        c = Candidate(
            stock_code="000001",
            stock_name="平安银行",
            channel=ChannelType.FACTOR,
            channel_score=85.0,
            sector="银行",
            source_tags=["factor_top10", "low_volatility"],
            extra={"factor_composite": 1.5},
        )
        self.assertEqual(c.channel_score, 85.0)
        self.assertEqual(c.sector, "银行")
        self.assertIn("factor_top10", c.source_tags)

    def test_multiple_channels_dedup_key(self):
        c1 = Candidate("600519", "贵州茅台", ChannelType.SECTOR)
        c2 = Candidate("600519", "贵州茅台", ChannelType.THEME)
        self.assertEqual(c1.dedup_key, c2.dedup_key)

    def test_different_stocks_dedup_key_differs(self):
        c1 = Candidate("600519", "贵州茅台", ChannelType.SECTOR)
        c2 = Candidate("000001", "平安银行", ChannelType.SECTOR)
        self.assertNotEqual(c1.dedup_key, c2.dedup_key)


class TestMarketContext(unittest.TestCase):
    def test_default_values(self):
        ctx = MarketContext()
        self.assertEqual(ctx.indices, {})
        self.assertEqual(ctx.sector_rankings, [])
        self.assertEqual(ctx.market_state, "unknown")
        self.assertIsNone(ctx.hot_themes)

    def test_custom_values(self):
        ctx = MarketContext(
            indices={"SH": 3200, "SZ": 10500},
            sector_rankings=[("半导体", 1), ("AI", 2)],
            market_state="trending_up",
            hot_themes=["AI芯片", "低空经济"],
        )
        self.assertEqual(ctx.indices["SH"], 3200)
        self.assertEqual(len(ctx.sector_rankings), 2)
        self.assertEqual(ctx.market_state, "trending_up")
        self.assertIn("AI芯片", ctx.hot_themes)


class TestRecommendationRecord(unittest.TestCase):
    def test_minimal_record(self):
        now = datetime.now(timezone.utc)
        r = RecommendationRecord(
            stock_code="600519",
            channel=ChannelType.SECTOR,
            signal=SignalType.BUY,
            confidence=0.85,
            recommended_price=150.0,
            recommended_at=now,
        )
        self.assertFalse(r.verified)
        self.assertIsNone(r.t1_return)
        self.assertFalse(r.success)

    def test_verified_success(self):
        now = datetime.now(timezone.utc)
        r = RecommendationRecord(
            stock_code="600519",
            channel=ChannelType.SECTOR,
            signal=SignalType.BUY,
            confidence=0.85,
            recommended_price=150.0,
            recommended_at=now,
            verified=True,
            t1_price=155.0,
            t1_return=0.0333,
            success=True,
        )
        self.assertTrue(r.verified)
        self.assertAlmostEqual(r.t1_return, 0.0333, places=4)
        self.assertTrue(r.success)


class TestRecommendationResult(unittest.TestCase):
    def test_default_values(self):
        r = RecommendationResult()
        self.assertFalse(r.success)
        self.assertIsNone(r.candidates)
        self.assertEqual(r.recommendations, [])
        self.assertEqual(r.total_scanned, 0)

    def test_with_recommendations(self):
        r = RecommendationResult(
            success=True,
            candidates=["600519", "000001"],
            recommendations=[
                RecommendationRecord(
                    stock_code="600519",
                    channel=ChannelType.SECTOR,
                    signal=SignalType.BUY,
                    confidence=0.85,
                    recommended_price=150.0,
                    recommended_at=datetime.now(timezone.utc),
                )
            ],
            total_scanned=50,
        )
        self.assertTrue(r.success)
        self.assertEqual(len(r.recommendations), 1)
        self.assertEqual(r.total_scanned, 50)


if __name__ == "__main__":
    unittest.main()
