# -*- coding: utf-8 -*-
"""Tests for auto-recommend scorer."""

import unittest
from src.services.auto_recommend.models import (
    ChannelType,
    MarketContext,
    Candidate,
)
from src.services.auto_recommend.scorer import Scorer, DEFAULT_WEIGHTS


class TestScorerDefaults(unittest.TestCase):
    def setUp(self):
        self.scorer = Scorer()

    def test_default_weights_are_positive(self):
        for ch in ChannelType:
            self.assertGreater(DEFAULT_WEIGHTS[ch], 0)

    def test_default_weights_sum_to_100(self):
        total = sum(DEFAULT_WEIGHTS.values())
        self.assertAlmostEqual(total, 100.0, places=2)

    def test_score_single_candidate_no_context(self):
        c = Candidate("600519", "茅台", ChannelType.SECTOR, channel_score=80.0)
        s = self.scorer.score_candidate(c)
        self.assertAlmostEqual(s, 80.0)

    def test_score_with_market_context_boost(self):
        c = Candidate("600519", "茅台", ChannelType.SECTOR,
                       channel_score=80.0, sector="白酒")
        ctx = MarketContext(
            sector_rankings=[("白酒", 1), ("银行", 5)],
            market_state="trending_up",
        )
        s = self.scorer.score_candidate(c, ctx)
        self.assertGreater(s, 80.0)

    def test_score_with_market_context_penalty(self):
        c = Candidate("002456", "欧菲光", ChannelType.SECTOR,
                       channel_score=80.0, sector="消费电子")
        ctx = MarketContext(
            sector_rankings=[("白酒", 1), ("消费电子", 40)],
            market_state="trending_down",
        )
        s = self.scorer.score_candidate(c, ctx)
        self.assertLess(s, 80.0)

    def test_rank_candidates(self):
        cs = [
            Candidate("600519", "茅台", ChannelType.SECTOR, channel_score=80.0),
            Candidate("000001", "平安", ChannelType.FACTOR, channel_score=90.0),
            Candidate("002415", "海康", ChannelType.THEME, channel_score=70.0),
        ]
        ranked = self.scorer.rank(cs)
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[0].stock_code, "000001")  # highest first
        self.assertEqual(ranked[2].stock_code, "002415")  # lowest last

    def test_dedup_higher_score_wins(self):
        cs = [
            Candidate("600519", "茅台", ChannelType.SECTOR, channel_score=80.0),
            Candidate("600519", "茅台", ChannelType.THEME, channel_score=95.0),
        ]
        deduped = self.scorer.dedup(cs)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].channel_score, 95.0)
        self.assertIs(deduped[0].channel, ChannelType.THEME)

    def test_dedup_multiple_stocks(self):
        cs = [
            Candidate("600519", "茅台", ChannelType.SECTOR, channel_score=80.0),
            Candidate("000001", "平安", ChannelType.FACTOR, channel_score=75.0),
            Candidate("600519", "茅台", ChannelType.THEME, channel_score=95.0),
        ]
        deduped = self.scorer.dedup(cs)
        self.assertEqual(len(deduped), 2)
        codes = {c.stock_code for c in deduped}
        self.assertIn("600519", codes)
        self.assertIn("000001", codes)


class TestScorerAdaptiveWeights(unittest.TestCase):
    def setUp(self):
        self.scorer = Scorer()

    def test_adaptive_weights_decay_high_failure(self):
        channel_failures = {
            ChannelType.SECTOR: 0.8,    # 80% failure rate
            ChannelType.FACTOR: 0.2,
        }
        weights = self.scorer.get_adaptive_weights(channel_failures)
        self.assertLess(weights[ChannelType.SECTOR], DEFAULT_WEIGHTS[ChannelType.SECTOR])

    def test_adaptive_weights_sum_to_100(self):
        channel_failures = {
            ChannelType.SECTOR: 0.8,
            ChannelType.FACTOR: 0.6,
        }
        weights = self.scorer.get_adaptive_weights(channel_failures)
        total = sum(weights.values())
        self.assertAlmostEqual(total, 100.0, places=2)


if __name__ == "__main__":
    unittest.main()
