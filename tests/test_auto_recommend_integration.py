# -*- coding: utf-8 -*-
"""Tests for auto-recommend config + CLI + scheduler integration."""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from src.services.auto_recommend.models import (
    ChannelType,
    MarketPhase,
    AnalysisMode,
)
from src.services.auto_recommend.engine import AutoRecommendEngine
from src.services.auto_recommend.scheduler_integration import (
    build_auto_recommend_task,
    get_recommend_config,
)


class TestGetRecommendConfig(unittest.TestCase):
    @patch("src.config.get_config")
    def test_defaults_from_config(self, mock_get_config):
        mock_cfg = MagicMock()
        mock_cfg.auto_recommend_enabled = True
        mock_cfg.auto_recommend_top_n = 15
        mock_cfg.auto_recommend_deep_analyze = 5
        mock_get_config.return_value = mock_cfg

        cfg = get_recommend_config()
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["top_n"], 15)
        self.assertEqual(cfg["deep_analyze"], 5)

    @patch("src.config.get_config")
    def test_defaults_fallback(self, mock_get_config):
        mock_cfg = MagicMock(spec=[])
        # Don't set auto_recommend_* fields -> not present in mock_cfg
        mock_get_config.return_value = mock_cfg

        cfg = get_recommend_config()
        # Should fall back to defaults
        self.assertEqual(cfg["top_n"], 10)
        self.assertEqual(cfg["deep_analyze"], 3)


class TestBuildTask(unittest.TestCase):
    @patch("src.services.auto_recommend.scheduler_integration.get_notification_service")
    @patch("src.services.auto_recommend.scheduler_integration.generate_recommend_report")
    @patch("src.services.auto_recommend.scheduler_integration.AutoRecommendEngine")
    @patch("src.config.get_config")
    def test_task_uses_engine(self, mock_get_config, mock_engine_cls,
                              mock_report, mock_notify):
        mock_cfg = MagicMock()
        mock_cfg.auto_recommend_enabled = True
        mock_get_config.return_value = mock_cfg

        mock_engine = MagicMock()
        mock_engine.run.return_value.success = True
        mock_engine_cls.return_value = mock_engine
        mock_report.return_value = "report"

        task_fn = build_auto_recommend_task()
        task_fn()

        mock_engine.run.assert_called_once()
        mock_notify.return_value.send.assert_called_once_with("report")

    @patch("src.config.get_config")
    def test_disabled_returns_noop(self, mock_get_config):
        mock_cfg = MagicMock()
        mock_cfg.auto_recommend_enabled = False
        mock_get_config.return_value = mock_cfg

        task_fn = build_auto_recommend_task()
        result = task_fn()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
