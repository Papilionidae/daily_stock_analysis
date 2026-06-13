# -*- coding: utf-8 -*-
"""Candidate discovery channels for auto-recommend engine."""

from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Mapping, Optional

from data_provider.base import DataFetcherManager

from src.services.auto_recommend.models import (
    Candidate,
    ChannelType,
    MarketContext,
)

logger = logging.getLogger(__name__)

# Default screening factors for factor channel
# Keys must match _SUPPORTED_FACTORS in src/agent/tools/factor_tools.py
DEFAULT_SCREEN_FACTORS: Dict[str, float] = {
    "value": 0.20,
    "quality": 0.20,
    "momentum": 0.20,
    "volatility": 0.20,
    "liquidity": 0.20,
}


class DiscoveryChannel(ABC):
    """Abstract discovery channel for generating candidates."""

    def __init__(self, data_manager: Optional[DataFetcherManager] = None):
        self._data_manager = data_manager or DataFetcherManager()

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        ...

    @abstractmethod
    def discover(self, top_n: int = 30,
                 context: Optional[MarketContext] = None) -> List[Candidate]:
        ...


class SectorSource(DiscoveryChannel):
    """Discovers candidates from sector rotation rankings.

    Uses top-ranked sectors to score hot stocks that belong to those
    sectors.  Scores are derived from the sector's change percentage.
    """

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.SECTOR

    def discover(self, top_n: int = 30,
                 context: Optional[MarketContext] = None) -> List[Candidate]:
        candidates: List[Candidate] = []
        try:
            top_sectors, _ = self._data_manager.get_sector_rankings(n=top_n)
        except Exception as exc:
            logger.warning("SectorSource: get_sector_rankings failed: %s", exc)
            return candidates

        sector_scores: Dict[str, float] = {}
        for s in (top_sectors or []):
            name = s.get("name", "")
            change = s.get("change_pct", 0.0)
            if name:
                sector_scores[name] = self._to_score(change)

        if not sector_scores:
            return candidates

        hot_stocks = self._get_hot_stocks(top_n * 10)
        for stock in hot_stocks:
            code = stock.get("code", "")
            name = stock.get("name", "")
            sector_name = self._resolve_stock_sector(code)
            if sector_name and sector_name in sector_scores:
                candidates.append(Candidate(
                    stock_code=code,
                    stock_name=name,
                    channel=ChannelType.SECTOR,
                    channel_score=sector_scores[sector_name],
                    sector=sector_name,
                    source_tags=["sector_top"],
                    extra={"sector_change_pct": sector_scores[sector_name]},
                ))

        return candidates[:top_n]

    def _get_hot_stocks(self, n: int) -> List[Dict]:
        try:
            return self._data_manager.get_hot_stocks(n=n) or []
        except Exception:
            return []

    def _resolve_stock_sector(self, stock_code: str) -> Optional[str]:
        """Resolve the sector/industry for a stock code.

        Uses get_belong_boards and returns the first industry board name.
        """
        try:
            boards = self._data_manager.get_belong_boards(stock_code)
            for b in boards or []:
                btype = b.get("type") or ""
                if "行业" in btype or not btype:
                    return b.get("name")
            return None
        except Exception:
            return None

    @staticmethod
    def _to_score(change_pct: float) -> float:
        return max(0.0, min(100.0, 50.0 + change_pct * 10.0))


class ThemeSource(DiscoveryChannel):
    """Discovers candidates from concept/theme rankings.

    Uses top-ranked concepts to score hot stocks that belong to those
    concepts (themes).
    """

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.THEME

    def discover(self, top_n: int = 30,
                 context: Optional[MarketContext] = None) -> List[Candidate]:
        candidates: List[Candidate] = []
        try:
            top_concepts, _ = self._data_manager.get_concept_rankings(n=top_n)
        except Exception as exc:
            logger.warning("ThemeSource: get_concept_rankings failed: %s", exc)
            return candidates

        concept_scores: Dict[str, float] = {}
        for c in (top_concepts or []):
            name = c.get("name", "")
            change = c.get("change_pct", 0.0)
            if name:
                concept_scores[name] = self._to_score(change)

        if not concept_scores:
            return candidates

        hot_stocks = self._get_hot_stocks(top_n * 10)
        for stock in hot_stocks:
            code = stock.get("code", "")
            name = stock.get("name", "")
            theme = self._resolve_stock_theme(code, concept_scores)
            if theme:
                candidates.append(Candidate(
                    stock_code=code,
                    stock_name=name,
                    channel=ChannelType.THEME,
                    channel_score=concept_scores[theme],
                    sector=theme,
                    source_tags=["theme_top"],
                    extra={"theme_change_pct": concept_scores[theme]},
                ))

        return candidates[:top_n]

    def _get_hot_stocks(self, n: int) -> List[Dict]:
        try:
            return self._data_manager.get_hot_stocks(n=n) or []
        except Exception:
            return []

    def _resolve_stock_theme(self, stock_code: str,
                             known_themes: Mapping[str, float]) -> Optional[str]:
        """Check if a stock belongs to any of the known hot themes."""
        try:
            boards = self._data_manager.get_belong_boards(stock_code)
            for b in boards or []:
                name = b.get("name", "")
                if name in known_themes:
                    return name
            return None
        except Exception:
            return None

    @staticmethod
    def _to_score(change_pct: float) -> float:
        return max(0.0, min(100.0, 50.0 + change_pct * 10.0))


class FactorSource(DiscoveryChannel):
    """Discovers candidates via multi-factor composite screening.

    Wraps the get_universe_screen tool to score the full A-share
    universe on value/quality/momentum/growth/low-volatility factors.
    """

    def __init__(self, data_manager: Optional[DataFetcherManager] = None,
                 factors: Optional[Dict[str, float]] = None):
        super().__init__(data_manager)
        self._factors = factors or dict(DEFAULT_SCREEN_FACTORS)

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.FACTOR

    def discover(self, top_n: int = 30,
                 context: Optional[MarketContext] = None) -> List[Candidate]:
        candidates: List[Candidate] = []
        try:
            from src.agent.tools.factor_tools import get_universe_screen_tool
            result = get_universe_screen_tool.handler(
                factors=self._factors,
                top_n=top_n,
                industry_limit=5,
            )
        except Exception as exc:
            logger.warning("FactorSource: get_universe_screen failed: %s", exc)
            return candidates

        if "error" in result:
            logger.warning("FactorSource error: %s", result["error"])
            return candidates

        for s in result.get("selected_stocks", []):
            score = s.get("composite_score", 0.5) * 100.0
            code = s.get("code", "")
            name = s.get("name") or self._resolve_name(code)
            c = Candidate(
                stock_code=code,
                stock_name=name,
                channel=ChannelType.FACTOR,
                channel_score=round(score, 2),
                sector=s.get("industry"),
                source_tags=["factor_screen"],
                extra={"factor_composite": s.get("composite_score")},
            )
            if c.stock_code:
                candidates.append(c)

        return candidates

    def _resolve_name(self, code: str) -> str:
        try:
            return self._data_manager.get_stock_name(code) or code
        except Exception:
            return code


class TechnicalSource(DiscoveryChannel):
    """Discovers candidates via technical breakout signals.

    Scans A-share stocks looking for recent technical patterns
    (e.g. volume surge, MA crossover) using per-stock daily K-line
    data.  The universe is sampled from the stock list to avoid
    always scanning the same subset.
    """

    TECHNICAL_SCAN_LIMIT = 100

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.TECHNICAL

    def discover(self, top_n: int = 30,
                 context: Optional[MarketContext] = None) -> List[Candidate]:
        candidates: List[Candidate] = []
        stock_codes = self._get_universe()
        random.shuffle(stock_codes)

        scanned = 0
        for code in stock_codes:
            if scanned >= self.TECHNICAL_SCAN_LIMIT:
                break
            try:
                df, source = self._data_manager.get_daily_data(
                    stock_code=code, days=60
                )
                if df is None or df.empty:
                    continue
                score = self._score_technical(df)
                if score and score >= 70.0:
                    name = self._resolve_name(code)
                    candidates.append(Candidate(
                        stock_code=code,
                        stock_name=name,
                        channel=ChannelType.TECHNICAL,
                        channel_score=round(score, 2),
                        source_tags=["technical_breakout"],
                        extra={"tech_source": source},
                    ))
                scanned += 1
            except Exception:
                continue

        return candidates[:top_n]

    def _get_universe(self) -> List[str]:
        """Get A-share stock codes from internal fetchers."""
        codes: List[str] = []
        try:
            for fetcher in self._data_manager._get_fetchers_snapshot():
                if hasattr(fetcher, "get_stock_list"):
                    df = fetcher.get_stock_list()
                    if df is not None:
                        codes.extend(df["code"].tolist())
            return codes
        except Exception:
            return []

    def _resolve_name(self, code: str) -> str:
        try:
            return self._data_manager.get_stock_name(code) or code
        except Exception:
            return code

    @staticmethod
    def _score_technical(df) -> Optional[float]:
        """Score a single stock's technical setup.

        Heuristic-based scoring using volume ratio and MA alignment.
        Returns 0-100 or None if no signal.
        """
        try:
            row = df.iloc[-1]
            score = 50.0

            volume_ratio = getattr(row, "volume_ratio", None) or (
                row.get("volume_ratio") if hasattr(row, "get") else None
            )
            if volume_ratio and volume_ratio > 1.5:
                score += 15.0
            elif volume_ratio and volume_ratio < 0.5:
                score -= 10.0

            close = row.get("close") if hasattr(row, "get") else row.close
            ma5 = row.get("ma5") if hasattr(row, "get") else getattr(row, "ma5", None)
            if ma5 and close > ma5:
                score += 10.0
            elif ma5 and close < ma5:
                score -= 10.0

            if hasattr(row, "get"):
                pct_chg = row.get("pct_chg", 0.0)
            else:
                pct_chg = getattr(row, "pct_chg", 0.0)
            if pct_chg and pct_chg > 2.0:
                score += 10.0
            elif pct_chg and pct_chg < -2.0:
                score -= 10.0

            return max(0.0, min(100.0, score))
        except Exception:
            return None
