# -*- coding: utf-8 -*-
"""T+1 validator and adaptive weight decay for auto-recommend engine."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, date
from typing import Dict, List, Optional

from src.services.auto_recommend.models import (
    ChannelType,
    RecommendationRecord,
)
from src.services.auto_recommend.scorer import Scorer

logger = logging.getLogger(__name__)


class TPlus1Validator:
    """Tracks recommendation records and performs T+1 verification.

    Each stored record is checked for the next trading day's close price.
    Channels with high failure rates (>60%) have their weights decayed
    and redistributed via the Scorer.
    """

    def __init__(self, scorer: Optional[Scorer] = None):
        self._records: List[RecommendationRecord] = []
        self._t1_cache: Dict[str, Optional[float]] = {}
        self._scorer = scorer or Scorer()

    # ------------------------------------------------------------------
    # Record management
    # ------------------------------------------------------------------

    def store(self, record: RecommendationRecord) -> None:
        """Persist a recommendation record for later T+1 verification."""
        self._records.append(record)

    def get_pending(self) -> List[RecommendationRecord]:
        """Return records from a previous calendar day (ready for T+1)."""
        today = date.today()
        return [
            r for r in self._records
            if not r.verified
            and r.recommended_at.date() < today
        ]

    def get_all(self) -> List[RecommendationRecord]:
        """Return all stored records."""
        return list(self._records)

    # ------------------------------------------------------------------
    # T+1 price fetching
    # ------------------------------------------------------------------

    def _fetch_t1_price(self, stock_code: str) -> Optional[float]:
        """Fetch latest close price for a stock code.

        Uses the DataFetcherManager to get the latest daily close.
        Results are cached per stock code.
        """
        if stock_code in self._t1_cache:
            return self._t1_cache[stock_code]

        try:
            from data_provider.base import DataFetcherManager
            dm = DataFetcherManager()
            df, source = dm.get_daily_data(stock_code=stock_code, days=5)
            if df is not None and not df.empty:
                price = float(df.iloc[-1]["close"])
                self._t1_cache[stock_code] = price
                return price
        except Exception as exc:
            logger.warning("T+1 fetch failed for %s: %s", stock_code, exc)

        self._t1_cache[stock_code] = None
        return None

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_pending(self) -> List[RecommendationRecord]:
        """Verify all pending recommendation records.

        Fetches T+1 prices and updates each record's verified/success
        fields.

        Returns:
            List of newly verified records.
        """
        pending = self.get_pending()
        verified: List[RecommendationRecord] = []

        for rec in pending:
            t1_price = self._fetch_t1_price(rec.stock_code)
            if t1_price is None:
                continue

            rec.t1_price = t1_price
            if rec.recommended_price > 0:
                rec.t1_return = round(
                    (t1_price - rec.recommended_price) / rec.recommended_price,
                    4,
                )
            rec.verified = True
            rec.success = rec.t1_return is not None and rec.t1_return >= 0
            verified.append(rec)

        if verified:
            logger.info("T+1 verified %d records", len(verified))

        return verified

    # ------------------------------------------------------------------
    # Adaptive weights
    # ------------------------------------------------------------------

    def get_channel_failure_rate(self, channel: ChannelType) -> float:
        """Compute the failure rate for a given channel.

        Failure rate = verified failures / total verified records.

        Returns:
            0.0 if no verified records, otherwise 0-1.
        """
        verified = [
            r for r in self._records
            if r.channel == channel and r.verified
        ]
        if not verified:
            return 0.0
        failures = sum(1 for r in verified if not r.success)
        return failures / len(verified)

    def get_adaptive_weights(self) -> Dict[ChannelType, float]:
        """Compute adaptive weights based on channel-level failure rates.

        Uses the Scorer instance passed at construction (or default).

        Returns:
            Adjusted weight dict per channel.
        """
        failures: Dict[ChannelType, float] = {}
        for ch in ChannelType:
            rate = self.get_channel_failure_rate(ch)
            if rate > 0:
                failures[ch] = rate

        return self._scorer.get_adaptive_weights(failures)
