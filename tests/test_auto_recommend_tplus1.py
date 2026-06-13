# -*- coding: utf-8 -*-
"""Tests for T+1 verification and adaptive weight decay."""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta

from src.services.auto_recommend.models import (
    ChannelType, SignalType, RecommendationRecord,
)
from src.services.auto_recommend.tplus1_validator import TPlus1Validator


class TestTPlus1Validator(unittest.TestCase):
    def setUp(self):
        self.validator = TPlus1Validator()

    def test_empty_store_returns_empty(self):
        results = self.validator.verify_pending()
        self.assertEqual(results, [])

    def test_successful_t1_marks_success(self):
        now = datetime.now(timezone.utc)
        rec = RecommendationRecord(
            stock_code="600519",
            channel=ChannelType.SECTOR,
            signal=SignalType.BUY,
            confidence=0.85,
            recommended_price=100.0,
            recommended_at=now - timedelta(days=1),
        )
        self.validator.store(rec)

        # Mock T+1 price higher -> success
        with patch.object(self.validator, "_fetch_t1_price", return_value=105.0):
            results = self.validator.verify_pending()

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertTrue(r.verified)
        self.assertTrue(r.success)
        self.assertIsNotNone(r.t1_return)
        self.assertGreater(r.t1_return, 0)

    def test_failed_t1_marks_not_success(self):
        now = datetime.now(timezone.utc)
        rec = RecommendationRecord(
            stock_code="600519",
            channel=ChannelType.SECTOR,
            signal=SignalType.BUY,
            confidence=0.85,
            recommended_price=100.0,
            recommended_at=now - timedelta(days=1),
        )
        self.validator.store(rec)

        with patch.object(self.validator, "_fetch_t1_price", return_value=95.0):
            results = self.validator.verify_pending()

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertTrue(r.verified)
        self.assertFalse(r.success)

    def test_not_ready_records_not_verified(self):
        now = datetime.now(timezone.utc)
        rec = RecommendationRecord(
            stock_code="600519",
            channel=ChannelType.SECTOR,
            signal=SignalType.BUY,
            confidence=0.85,
            recommended_price=100.0,
            recommended_at=now,  # same day — not ready for T+1
        )
        self.validator.store(rec)

        results = self.validator.verify_pending()
        self.assertEqual(results, [])

    def test_channel_failure_rate(self):
        now = datetime.now(timezone.utc)
        # Store 3 SECTOR records, 2 will fail
        for i in range(3):
            rec = RecommendationRecord(
                stock_code=f"6005{i:02d}",
                channel=ChannelType.SECTOR,
                signal=SignalType.BUY,
                confidence=0.85,
                recommended_price=100.0,
                recommended_at=now - timedelta(days=1),
            )
            self.validator.store(rec)
            with patch.object(self.validator, "_fetch_t1_price",
                              return_value=95.0 if i < 2 else 105.0):
                self.validator.verify_pending()

        rate = self.validator.get_channel_failure_rate(ChannelType.SECTOR)
        self.assertAlmostEqual(rate, 2 / 3, places=2)

    def test_failure_rate_decay_weights(self):
        now = datetime.now(timezone.utc)
        # Sector high failure, Theme low
        for ch, fail_count, tot_count in [
            (ChannelType.SECTOR, 5, 6),
            (ChannelType.THEME, 1, 6),
        ]:
            for i in range(tot_count):
                rec = RecommendationRecord(
                    stock_code=f"000{i:02d}",
                    channel=ch,
                    signal=SignalType.BUY,
                    confidence=0.8,
                    recommended_price=100.0,
                    recommended_at=now - timedelta(days=1),
                )
                self.validator.store(rec)
                price = 95.0 if i < fail_count else 105.0
                with patch.object(self.validator, "_fetch_t1_price",
                                  return_value=price):
                    self.validator.verify_pending()

        weights = self.validator.get_adaptive_weights()
        from src.services.auto_recommend.scorer import DEFAULT_WEIGHTS
        self.assertLess(
            weights[ChannelType.SECTOR],
            DEFAULT_WEIGHTS[ChannelType.SECTOR]
        )


if __name__ == "__main__":
    unittest.main()
