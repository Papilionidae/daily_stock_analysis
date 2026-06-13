# -*- coding: utf-8 -*-
"""AutoRecommendEngine — orchestrator for the auto-recommend pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

from src.services.auto_recommend.models import (
    Candidate,
    ChannelType,
    MarketContext,
    MarketPhase,
    AnalysisMode,
    RecommendationRecord,
    RecommendationResult,
    SignalType,
)
from src.services.auto_recommend.scorer import Scorer
from src.services.auto_recommend.candidate_discovery import (
    DiscoveryChannel,
    SectorSource,
    ThemeSource,
    FactorSource,
    TechnicalSource,
)

logger = logging.getLogger(__name__)

# Market hours (A-share): 9:30-11:30, 13:00-15:00
PRE_MARKET_CUTOFF = 9.5   # 9:30
INTRADAY_START = 9.5
INTRADAY_END = 15.0
POST_MARKET_START = 15.0


class AutoRecommendEngine:
    """Main orchestrator for auto-recommend scans.

    Responsibilities:
      1. Detect time phase (pre-market / intraday / post-market).
      2. Collect market context (indices, sector rankings).
      3. Run all enabled discovery channels.
      4. Score, deduplicate, and rank candidates.
      5. Deep-analyze top N candidates → recommendation records.
      6. Return a RecommendationResult.
    """

    def __init__(
        self,
        top_n: int = 10,
        deep_analyze_top_n: int = 3,
        enabled_channels: Optional[List[ChannelType]] = None,
        sources: Optional[Dict[ChannelType, DiscoveryChannel]] = None,
        scorer: Optional[Scorer] = None,
    ):
        self.top_n = top_n
        self.deep_analyze_top_n = deep_analyze_top_n
        self.enabled_channels: Set[ChannelType] = set(
            enabled_channels or [ChannelType.SECTOR, ChannelType.THEME, ChannelType.FACTOR, ChannelType.TECHNICAL]
        )
        self._scorer = scorer or Scorer()
        self._sources = sources or self._default_sources()

    def _default_sources(self) -> Dict[ChannelType, DiscoveryChannel]:
        return {
            ChannelType.SECTOR: SectorSource(),
            ChannelType.THEME: ThemeSource(),
            ChannelType.FACTOR: FactorSource(),
            ChannelType.TECHNICAL: TechnicalSource(),
        }

    @property
    def scorer(self) -> Scorer:
        return self._scorer

    # ------------------------------------------------------------------
    # Phase & mode detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_phase(now: Optional[datetime] = None) -> MarketPhase:
        """Detect the current market phase based on Shanghai local time.

        Weekend / non-trading days → POSTMARKET.
        """
        if now is None:
            try:
                from zoneinfo import ZoneInfo
                now = datetime.now(ZoneInfo("Asia/Shanghai"))
            except ImportError:
                # Fallback: use UTC+8 fixed offset (Shanghai)
                now = datetime.now(timezone.utc).astimezone(
                    timezone(timedelta(hours=8))
                )
        # Saturday=5, Sunday=6 in Python weekday (Mon=0, Sun=6)
        if now.weekday() >= 5:
            return MarketPhase.POSTMARKET

        hour = now.hour + now.minute / 60.0
        if hour < PRE_MARKET_CUTOFF:
            return MarketPhase.PREMARKET
        if hour < POST_MARKET_START:
            return MarketPhase.INTRADAY
        return MarketPhase.POSTMARKET

    @staticmethod
    def detect_analysis_mode(phase: MarketPhase) -> AnalysisMode:
        """Map market phase → recommended analysis depth.

        - PREMARKET  → QUICK    (fast scan, few candidates)
        - INTRADAY   → PIPELINE (moderate depth, strategy execution)
        - POSTMARKET → AGENT    (full LLM agent deep-dive)
        """
        mapping = {
            MarketPhase.PREMARKET: AnalysisMode.QUICK,
            MarketPhase.INTRADAY: AnalysisMode.PIPELINE,
            MarketPhase.POSTMARKET: AnalysisMode.AGENT,
        }
        return mapping[phase]

    # ------------------------------------------------------------------
    # Market context collection
    # ------------------------------------------------------------------

    @staticmethod
    def collect_market_context() -> MarketContext:
        """Collect a MarketContext snapshot.

        Currently returns a lightweight default; can be extended to
        query DataFetcherManager for indices and sector rankings.
        """
        return MarketContext(
            market_state="unknown",
        )

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(self, now: Optional[datetime] = None) -> RecommendationResult:
        """Execute a full auto-recommend scan.

        Args:
            now: Override current time (used in tests).

        Returns:
            RecommendationResult with scored candidates and picks.
        """
        phase = self.detect_phase(now)
        analysis_mode = self.detect_analysis_mode(phase)
        context = self.collect_market_context()
        logger.info(
            "AutoRecommendEngine.run phase=%s mode=%s",
            phase.value, analysis_mode.value,
        )

        # 1. Collect candidates from all enabled channels
        all_candidates: List[Candidate] = []
        for ch in self.enabled_channels:
            source = self._sources.get(ch)
            if source is None:
                continue
            try:
                candidates = source.discover(top_n=self.top_n, context=context)
                all_candidates.extend(candidates)
                logger.debug(
                    "Channel %s returned %d candidates",
                    ch.value, len(candidates),
                )
            except Exception as exc:
                logger.error("Channel %s failed: %s", ch.value, exc)

        if not all_candidates:
            return RecommendationResult(
                success=False,
                error="No candidates found from any channel",
                total_scanned=0,
                market_context=context,
            )

        # 2. Score & rank
        ranked = self._scorer.rank(all_candidates, context)
        top = ranked[:self.top_n]
        logger.info(
            "Ranked %d candidates, top %d selected",
            len(ranked), len(top),
        )

        # 3. Deep-analyze top N
        deep = top[:self.deep_analyze_top_n]
        recommendations = self._deep_analyze(deep, context, analysis_mode)

        return RecommendationResult(
            success=True,
            candidates=[c.stock_code for c in top],
            recommendations=recommendations,
            total_scanned=len(all_candidates),
            market_context=context,
        )

    def _deep_analyze(
        self,
        candidates: List[Candidate],
        context: MarketContext,
        mode: AnalysisMode,
    ) -> List[RecommendationRecord]:
        """Perform deep analysis on top-ranked candidates.

        Fetches realtime prices and produces lightweight recommendation
        records.  Will be expanded to run full strategy evaluations
        via SkillRouter in later steps.
        """
        records: List[RecommendationRecord] = []
        now = datetime.now(timezone.utc)
        dm = self._get_data_manager()

        for c in candidates:
            composite = c.extra.get("composite_score", c.channel_score or 50.0)
            confidence = min(1.0, composite / 100.0)
            price = self._fetch_price(dm, c.stock_code)
            record = RecommendationRecord(
                stock_code=c.stock_code,
                channel=c.channel,
                signal=self._infer_signal(confidence),
                confidence=round(confidence, 4),
                recommended_price=price,
                recommended_at=now,
                stock_name=c.stock_name,
                strategy_tags=[f"auto:{mode.value}"],
                sector=c.sector,
                summary=f"From {c.channel.value} score={composite:.1f}",
            )
            records.append(record)

        return records

    def _get_data_manager(self):
        """Lazy-init a DataFetcherManager for price lookups."""
        try:
            from data_provider.base import DataFetcherManager
            return DataFetcherManager()
        except Exception:
            return None

    def _fetch_price(self, dm, stock_code: str) -> float:
        """Fetch current price from realtime quote; returns 0.0 on failure."""
        if dm is None:
            return 0.0
        try:
            quote = dm.get_realtime_quote(stock_code)
            if quote and hasattr(quote, "latest_price"):
                return float(quote.latest_price or 0.0)
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _infer_signal(confidence: float) -> SignalType:
        """Infer a trading signal from confidence level."""
        if confidence >= 0.75:
            return SignalType.BUY
        if confidence >= 0.55:
            return SignalType.WATCH
        return SignalType.HOLD
