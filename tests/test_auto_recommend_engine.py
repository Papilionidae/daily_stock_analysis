# -*- coding: utf-8 -*-
"""Tests for auto-recommend engine orchestrator."""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from src.services.auto_recommend.models import (
    ChannelType, MarketPhase, AnalysisMode,
    Candidate, MarketContext, RecommendationResult,
)
from src.services.auto_recommend.engine import AutoRecommendEngine


class TestEngineInit(unittest.TestCase):
    def test_default_config(self):
        engine = AutoRecommendEngine()
        self.assertEqual(engine.top_n, 10)
        self.assertEqual(engine.deep_analyze_top_n, 3)
        self.assertIsInstance(engine.scorer, object)

    def test_custom_config(self):
        engine = AutoRecommendEngine(top_n=20, deep_analyze_top_n=5)
        self.assertEqual(engine.top_n, 20)
        self.assertEqual(engine.deep_analyze_top_n, 5)

    def test_enabled_channels_default(self):
        engine = AutoRecommendEngine()
        expected_channels = [
            ChannelType.SECTOR,
            ChannelType.THEME,
            ChannelType.FACTOR,
            ChannelType.TECHNICAL,
        ]
        for ch in expected_channels:
            self.assertIn(ch, engine.enabled_channels)
        self.assertNotIn(ChannelType.ALPHASIFT, engine.enabled_channels)


class TestEnginePhaseDetection(unittest.TestCase):
    def setUp(self):
        self.engine = AutoRecommendEngine()

    def test_premarket_before_0930(self):
        phase = self.engine.detect_phase(
            datetime(2026, 6, 15, 8, 30)
        )
        self.assertIs(phase, MarketPhase.PREMARKET)

    def test_intraday_1000(self):
        phase = self.engine.detect_phase(
            datetime(2026, 6, 15, 10, 0)
        )
        self.assertIs(phase, MarketPhase.INTRADAY)

    def test_postmarket_1600(self):
        phase = self.engine.detect_phase(
            datetime(2026, 6, 15, 16, 30)
        )
        self.assertIs(phase, MarketPhase.POSTMARKET)

    def test_weekend_always_postmarket(self):
        # Saturday
        phase = self.engine.detect_phase(
            datetime(2026, 6, 13, 10, 0)
        )
        self.assertIs(phase, MarketPhase.POSTMARKET)


class TestEngineAnalysisMode(unittest.TestCase):
    def setUp(self):
        self.engine = AutoRecommendEngine()

    def test_premarket_uses_quick(self):
        mode = self.engine.detect_analysis_mode(MarketPhase.PREMARKET)
        self.assertIs(mode, AnalysisMode.QUICK)

    def test_intraday_uses_pipeline(self):
        mode = self.engine.detect_analysis_mode(MarketPhase.INTRADAY)
        self.assertIs(mode, AnalysisMode.PIPELINE)

    def test_postmarket_uses_agent(self):
        mode = self.engine.detect_analysis_mode(MarketPhase.POSTMARKET)
        self.assertIs(mode, AnalysisMode.AGENT)


class TestEngineRun(unittest.TestCase):
    def setUp(self):
        self.mock_sector_source = MagicMock()
        self.mock_factor_source = MagicMock()
        self.mock_theme_source = MagicMock()
        self.mock_technical_source = MagicMock()

        self.engine = AutoRecommendEngine(
            top_n=10,
            deep_analyze_top_n=2,
            enabled_channels=[ChannelType.SECTOR, ChannelType.FACTOR],
            sources={
                ChannelType.SECTOR: self.mock_sector_source,
                ChannelType.FACTOR: self.mock_factor_source,
            },
        )

    def test_run_collects_candidates(self):
        self.mock_sector_source.discover.return_value = [
            Candidate("600519", "茅台", ChannelType.SECTOR, channel_score=80.0),
        ]
        self.mock_factor_source.discover.return_value = [
            Candidate("000001", "平安", ChannelType.FACTOR, channel_score=85.0),
        ]

        result = self.engine.run()
        self.assertTrue(result.success)
        self.assertGreater(len(result.recommendations), 0)

    def test_run_empty_candidates_returns_failure(self):
        self.mock_sector_source.discover.return_value = []
        self.mock_factor_source.discover.return_value = []

        result = self.engine.run()
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_run_total_scanned(self):
        self.mock_sector_source.discover.return_value = [
            Candidate("600519", "茅台", ChannelType.SECTOR, channel_score=80.0),
        ]
        self.mock_factor_source.discover.return_value = [
            Candidate("000001", "平安", ChannelType.FACTOR, channel_score=85.0),
        ]

        result = self.engine.run()
        self.assertEqual(result.total_scanned, 2)

    def test_run_limits_deep_analysis(self):
        self.mock_sector_source.discover.return_value = [
            Candidate(f"6005{i:02d}", f"Stock{i}", ChannelType.SECTOR,
                       channel_score=80.0 - i)
            for i in range(5)
        ]
        self.mock_factor_source.discover.return_value = []

        result = self.engine.run()
        # deep_analyze_top_n=2, so only 2 recommendations
        self.assertLessEqual(len(result.recommendations), 2)


if __name__ == "__main__":
    unittest.main()
