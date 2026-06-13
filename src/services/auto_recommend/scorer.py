# -*- coding: utf-8 -*-
"""Scorer — composite scoring and ranking for auto-recommend candidates."""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from src.services.auto_recommend.models import (
    Candidate,
    ChannelType,
    MarketContext,
)

# Fixed default weights (sum ~100).
# These represent the relative confidence in each channel.
DEFAULT_WEIGHTS: Dict[ChannelType, float] = {
    ChannelType.THEME: 20.0,
    ChannelType.SECTOR: 25.0,
    ChannelType.FACTOR: 25.0,
    ChannelType.TECHNICAL: 20.0,
    ChannelType.ALPHASIFT: 10.0,
}

# Sector ranking bonus: applied as a multiplier when the candidate's sector
# ranks within the top N.
SECTOR_TOP_N_BONUS = 1.10           # +10% bonus for rank <= 5
SECTOR_MID_BONUS = 1.03             # +3%  bonus for rank 6-15
SECTOR_LOW_PENALTY = 0.95           # -5%  penalty for rank > 30

# Market-state multiplier
MARKET_STATE_UP_MULTIPLIER = 1.05
MARKET_STATE_DOWN_MULTIPLIER = 0.95

# Adaptive-weight decay factor per 10pp above threshold
DECAY_PER_10PP = 0.85


def _sector_rank_score(sector_name: Optional[str],
                       sector_rankings: List[tuple]) -> float:
    """Return a multiplier based on sector ranking.

    Args:
        sector_name: Sector name of the candidate.
        sector_rankings: Ordered list of (name, rank).

    Returns:
        Multiplier >= ~0.95 to ~1.10.
    """
    if not sector_name or not sector_rankings:
        return 1.0
    for name, rank in sector_rankings:
        if name == sector_name:
            if rank <= 5:
                return SECTOR_TOP_N_BONUS
            if rank <= 15:
                return SECTOR_MID_BONUS
            if rank > 30:
                return SECTOR_LOW_PENALTY
            return 1.0
    return 1.0


def _market_state_multiplier(state: str) -> float:
    """Return a multiplier based on overall market state."""
    s = state.lower()
    if "up" in s or "bull" in s:
        return MARKET_STATE_UP_MULTIPLIER
    if "down" in s or "bear" in s:
        return MARKET_STATE_DOWN_MULTIPLIER
    return 1.0


class Scorer:
    """Composite scorer for auto-recommend candidates.

    Handles per-candidate scoring with context adjustments,
    deduplication across channels, and adaptive weight calculation.
    """

    def __init__(self, weights: Optional[Dict[ChannelType, float]] = None):
        self._weights = weights or dict(DEFAULT_WEIGHTS)

    @property
    def weights(self) -> Dict[ChannelType, float]:
        return dict(self._weights)

    def score_candidate(self, candidate: Candidate,
                        context: Optional[MarketContext] = None) -> float:
        """Compute the composite score for a single candidate.

        The base score is the channel_score.  If market context is provided
        we apply sector-ranking and market-state multipliers.
        """
        base = candidate.channel_score or 50.0
        if not context:
            return base

        sector_mul = _sector_rank_score(candidate.sector,
                                        context.sector_rankings)
        market_mul = _market_state_multiplier(context.market_state)
        return base * sector_mul * market_mul

    def dedup(self, candidates: List[Candidate]) -> List[Candidate]:
        """Remove cross-channel duplicates, keeping the highest-scored copy.

        Args:
            candidates: Raw candidate list (may contain duplicates).

        Returns:
            Deduplicated list with only the highest-channel_score per stock.
        """
        best: Dict[str, Candidate] = {}
        for c in candidates:
            key = c.dedup_key
            if key not in best:
                best[key] = c
            else:
                existing = best[key].channel_score or 0
                incoming = c.channel_score or 0
                if incoming > existing:
                    best[key] = c
        return list(best.values())

    def rank(self, candidates: List[Candidate],
             context: Optional[MarketContext] = None) -> List[Candidate]:
        """Score, deduplicate, and sort candidates by composite score.

        Args:
            candidates: Raw candidate list.
            context: Optional market context for adjustments.

        Returns:
            Candidates sorted descending by composite score.
        """
        scored = []
        for c in candidates:
            composite = self.score_candidate(c, context)
            # Embed composite score into extra for traceability
            c.extra["composite_score"] = round(composite, 2)
            scored.append(c)
        deduped = self.dedup(scored)
        deduped.sort(key=lambda x: x.extra.get("composite_score", 0),
                     reverse=True)
        return deduped

    def get_adaptive_weights(
        self,
        channel_failures: Dict[ChannelType, float],
    ) -> Dict[ChannelType, float]:
        """Compute adaptive weights from channel-level T+1 failure rates.

        Channels with high failure rate (>60%) have their weight decayed.
        Decayed weight is redistributed proportionally to remaining channels.

        Args:
            channel_failures: Failure rate (0-1) per channel.

        Returns:
            Adjusted weight dict (sum ~100).
        """
        threshold = 0.6
        new_weights: Dict[ChannelType, float] = {}
        total_decay = 0.0

        for ch in ChannelType:
            failure = channel_failures.get(ch, 0.0)
            orig = self._weights[ch]
            if failure > threshold:
                excess = failure - threshold
                decay_factor = DECAY_PER_10PP ** math.ceil(excess / 0.1)
                new_w = orig * decay_factor
                total_decay += orig - new_w
                new_weights[ch] = new_w
            else:
                new_weights[ch] = orig

        # Redistribute decayed weight proportionally to non-decayed channels
        if total_decay > 0.001:
            non_decayed_total = sum(
                w for ch, w in new_weights.items()
                if channel_failures.get(ch, 0.0) <= threshold
            )
            if non_decayed_total > 0:
                ratio = (non_decayed_total + total_decay) / non_decayed_total
                for ch in new_weights:
                    if channel_failures.get(ch, 0.0) <= threshold:
                        new_weights[ch] *= ratio

        # Round to 2 decimals
        return {ch: round(w, 2) for ch, w in new_weights.items()}
