# -*- coding: utf-8 -*-
"""Data models for the auto-recommend engine."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


class ChannelType(enum.Enum):
    """Candidate discovery channel."""
    THEME = "theme"
    SECTOR = "sector"
    FACTOR = "factor"
    TECHNICAL = "technical"
    ALPHASIFT = "alphasift"


class MarketPhase(enum.Enum):
    """Time-of-day phase for scheduled scans."""
    PREMARKET = "premarket"
    INTRADAY = "intraday"
    POSTMARKET = "postmarket"


class AnalysisMode(enum.Enum):
    """Depth of analysis to apply to candidates."""
    QUICK = "quick"
    PIPELINE = "pipeline"
    AGENT = "agent"


class SignalType(enum.Enum):
    """Trading signal type."""
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    WATCH = "watch"


@dataclass
class Candidate:
    """A stock candidate discovered by a channel.

    Attributes:
        stock_code: Stock code (e.g. "600519").
        stock_name: Stock display name.
        channel: Which channel discovered this candidate.
        channel_score: Raw score from the discovery channel (0-100).
        sector: Sector/industry name.
        source_tags: Tags from the discovery process.
        extra: Arbitrary extra data from the channel.
    """

    stock_code: str
    stock_name: str
    channel: ChannelType
    channel_score: Optional[float] = None
    sector: Optional[str] = None
    source_tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        """Key used for deduplication across channels."""
        return f"{self.stock_code}"


@dataclass
class MarketContext:
    """Market context snapshot collected before candidate discovery.

    Attributes:
        indices: Market indices by name (e.g. {"SH": 3200}).
        sector_rankings: Ordered sector rankings (name, rank).
        market_state: Detected market regime state.
        hot_themes: List of hot theme keywords.
    """

    indices: Dict[str, float] = field(default_factory=dict)
    sector_rankings: List[tuple] = field(default_factory=list)
    market_state: str = "unknown"
    hot_themes: Optional[List[str]] = None


@dataclass
class RecommendationRecord:
    """A validated recommendation record for T+1 tracking.

    Attributes:
        stock_code: Stock code.
        channel: Source channel.
        signal: Trading signal.
        confidence: Confidence score (0-1).
        recommended_price: Price at recommendation time.
        recommended_at: When recommended.
        strategy_tags: Strategy/skill tags.
        summary: Brief analysis summary.
        verified: Whether T+1 verification has been done.
        t1_price: T+1 close price.
        t1_return: T+1 return.
        success: Whether T+1 outcome was positive.
    """

    stock_code: str
    channel: ChannelType
    signal: SignalType
    confidence: float
    recommended_price: float
    recommended_at: datetime
    strategy_tags: List[str] = field(default_factory=list)
    summary: str = ""
    verified: bool = False
    t1_price: Optional[float] = None
    t1_return: Optional[float] = None
    success: bool = False


@dataclass
class RecommendationResult:
    """Final output from a recommendation run.

    Attributes:
        success: Whether the run completed successfully.
        candidates: List of candidate stock codes that passed initial score.
        recommendations: Deep-analyzed recommendation records.
        total_scanned: Total number of stocks scanned across all channels.
        market_context: Market context used.
        error: Error message if any.
    """

    success: bool = False
    candidates: Optional[List[str]] = None
    recommendations: List[RecommendationRecord] = field(default_factory=list)
    total_scanned: int = 0
    market_context: Optional[MarketContext] = None
    error: Optional[str] = None
