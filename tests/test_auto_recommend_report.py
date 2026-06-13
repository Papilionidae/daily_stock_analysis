# -*- coding: utf-8 -*-
"""Tests for auto-recommend report generation."""

import unittest
from datetime import datetime, timezone

from src.services.auto_recommend.models import (
    ChannelType, SignalType,
    Candidate, MarketContext, RecommendationRecord, RecommendationResult,
)
from src.services.auto_recommend.report import generate_recommend_report


class TestGenerateReport(unittest.TestCase):
    def test_empty_result_returns_empty(self):
        r = RecommendationResult(success=False, error="no data")
        report = generate_recommend_report(r)
        self.assertIn("no data", report)

    def test_success_result_contains_header(self):
        ctx = MarketContext(indices={"SH": 3200}, market_state="trending_up")
        r = RecommendationResult(
            success=True,
            candidates=["600519"],
            recommendations=[
                RecommendationRecord(
                    stock_code="600519",
                    channel=ChannelType.SECTOR,
                    signal=SignalType.BUY,
                    confidence=0.85,
                    recommended_price=150.0,
                    recommended_at=datetime.now(timezone.utc),
                    summary="业绩稳健",
                ),
            ],
            total_scanned=50,
            market_context=ctx,
        )
        report = generate_recommend_report(r)
        self.assertIn("自动荐股报告", report)
        self.assertIn("600519", report)
        self.assertIn("BUY", report.upper())
        self.assertIn("50", report)  # total_scanned

    def test_multi_picks_ranked_by_confidence(self):
        recs = [
            RecommendationRecord(
                stock_code="000001", channel=ChannelType.FACTOR,
                signal=SignalType.BUY, confidence=0.90,
                recommended_price=10.0,
                recommended_at=datetime.now(timezone.utc),
            ),
            RecommendationRecord(
                stock_code="600519", channel=ChannelType.SECTOR,
                signal=SignalType.WATCH, confidence=0.60,
                recommended_price=150.0,
                recommended_at=datetime.now(timezone.utc),
            ),
        ]
        r = RecommendationResult(
            success=True,
            candidates=["000001", "600519"],
            recommendations=recs,
            total_scanned=100,
        )
        report = generate_recommend_report(r)
        # Higher confidence should appear first
        first_idx = report.index("000001")
        second_idx = report.index("600519")
        self.assertLess(first_idx, second_idx)

    def test_no_recs_shows_message(self):
        r = RecommendationResult(
            success=True, candidates=[], total_scanned=0,
        )
        report = generate_recommend_report(r)
        self.assertIn("无符合条件", report)

    def test_contains_channel_info(self):
        recs = [
            RecommendationRecord(
                stock_code="600519", channel=ChannelType.SECTOR,
                signal=SignalType.BUY, confidence=0.85,
                recommended_price=150.0,
                recommended_at=datetime.now(timezone.utc),
                strategy_tags=["auto:pipeline"],
            ),
        ]
        r = RecommendationResult(
            success=True, candidates=["600519"],
            recommendations=recs, total_scanned=30,
        )
        report = generate_recommend_report(r)
        self.assertIn("SECTOR", report.upper() or report)


if __name__ == "__main__":
    unittest.main()
