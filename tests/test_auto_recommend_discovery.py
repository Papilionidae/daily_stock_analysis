# -*- coding: utf-8 -*-
"""Tests for auto-recommend candidate discovery channels."""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from typing import List

from src.services.auto_recommend.models import Candidate, ChannelType, MarketContext
from src.services.auto_recommend.candidate_discovery import (
    SectorSource,
    ThemeSource,
    FactorSource,
    TechnicalSource,
)


FAKE_TOP_SECTORS = [
    {"name": "白酒", "change_pct": 3.5},
    {"name": "半导体", "change_pct": 2.8},
]
FAKE_BOTTOM_SECTORS = [
    {"name": "房地产", "change_pct": -2.1},
]

FAKE_CONCEPTS = [
    {"name": "AI芯片", "change_pct": 4.2},
    {"name": "低空经济", "change_pct": 3.1},
]

FAKE_HOT_STOCKS = [
    {"code": "600519", "name": "贵州茅台", "rank": 1, "change_pct": 3.5},
    {"code": "000858", "name": "五粮液", "rank": 5, "change_pct": 2.8},
    {"code": "688981", "name": "中芯国际", "rank": 10, "change_pct": 1.2},
]

FAKE_FACTOR_RESULT = {
    "selected_stocks": [
        {"code": "600519", "industry": "白酒", "composite_score": 0.85},
        {"code": "000001", "industry": "银行", "composite_score": 0.72},
    ]
}

FAKE_DAILY_DFS = {
    "600519": MagicMock(
        # Simulate a DataFrame with technical indicators
        empty=False,
        iloc=MagicMock(),
    ),
}


class TestSectorSource(unittest.TestCase):
    def setUp(self):
        self.mock_data_manager = MagicMock()
        self.source = SectorSource(data_manager=self.mock_data_manager)

    def test_discover_returns_candidates(self):
        self.mock_data_manager.get_sector_rankings.return_value = (
            FAKE_TOP_SECTORS, FAKE_BOTTOM_SECTORS
        )
        self.mock_data_manager.get_hot_stocks.return_value = FAKE_HOT_STOCKS
        self.mock_data_manager.get_belong_boards.side_effect = (
            lambda code: [{"name": "白酒", "type": "行业"}]
            if code in ("600519", "000858")
            else [{"name": "半导体", "type": "行业"}]
        )

        candidates = self.source.discover(top_n=5)
        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)
        for c in candidates:
            self.assertIs(c.channel, ChannelType.SECTOR)
            self.assertIsNotNone(c.stock_code)

    def test_channel_type(self):
        self.assertIs(self.source.channel_type, ChannelType.SECTOR)


class TestThemeSource(unittest.TestCase):
    def setUp(self):
        self.mock_data_manager = MagicMock()
        self.source = ThemeSource(data_manager=self.mock_data_manager)

    def test_discover_from_concept_rankings(self):
        self.mock_data_manager.get_concept_rankings.return_value = (
            FAKE_CONCEPTS, []
        )
        self.mock_data_manager.get_hot_stocks.return_value = FAKE_HOT_STOCKS
        self.mock_data_manager.get_belong_boards.side_effect = (
            lambda code: [{"name": "AI芯片", "type": "概念"}]
        )

        candidates = self.source.discover(top_n=5)
        self.assertIsInstance(candidates, list)

    def test_channel_type(self):
        self.assertIs(self.source.channel_type, ChannelType.THEME)


class TestFactorSource(unittest.TestCase):
    def setUp(self):
        self.source = FactorSource()

    @patch("src.agent.tools.factor_tools.get_universe_screen_tool")
    def test_discover_returns_candidates(self, mock_tool):
        mock_tool.handler = MagicMock(return_value=FAKE_FACTOR_RESULT)

        candidates = self.source.discover(top_n=5)
        self.assertGreater(len(candidates), 0)
        for c in candidates:
            self.assertIs(c.channel, ChannelType.FACTOR)
            self.assertIn(c.stock_code, ["600519", "000001"])

    def test_channel_type(self):
        self.assertIs(self.source.channel_type, ChannelType.FACTOR)


class TestTechnicalSource(unittest.TestCase):
    def setUp(self):
        self.mock_data_manager = MagicMock()
        self.source = TechnicalSource(data_manager=self.mock_data_manager)

    def test_discover_scans_universe(self):
        mock_fetcher = MagicMock()
        mock_df = MagicMock()
        mock_df.__getitem__.return_value = mock_df
        mock_df.tolist.return_value = ["600519", "000001", "002415"]
        mock_fetcher.get_stock_list.return_value = mock_df

        self.mock_data_manager._fetchers = [mock_fetcher]
        mock_result_df = MagicMock()
        mock_result_df.empty = False
        self.mock_data_manager.get_daily_data.return_value = (mock_result_df, "akshare")

        candidates = self.source.discover(top_n=5)
        self.assertIsInstance(candidates, list)

    def test_channel_type(self):
        self.assertIs(self.source.channel_type, ChannelType.TECHNICAL)


if __name__ == "__main__":
    unittest.main()
