# -*- coding: utf-8 -*-
"""Scheduler integration for auto-recommend engine.

Provides the task factory used by src/scheduler.py to register
daily auto-recommend scans alongside the existing analysis schedule.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from src.services.auto_recommend.engine import AutoRecommendEngine
from src.services.auto_recommend.models import ChannelType
from src.services.auto_recommend.report import generate_recommend_report
from src.notification import get_notification_service

logger = logging.getLogger(__name__)

# Default config key names (matching src/config.py field names)
CONFIG_PREFIX = "auto_recommend_"


def get_recommend_config() -> Dict[str, Any]:
    """Read auto-recommend config from the global Config singleton.

    Returns a flat dict with keys: enabled, top_n, deep_analyze, channels.
    Missing keys fall back to engine defaults.
    """
    from src.config import get_config

    cfg = get_config()
    result: Dict[str, Any] = {
        "enabled": getattr(cfg, f"{CONFIG_PREFIX}enabled", False),
        "top_n": getattr(cfg, f"{CONFIG_PREFIX}top_n", 10),
        "deep_analyze": getattr(cfg, f"{CONFIG_PREFIX}deep_analyze", 3),
        "channels": None,  # None = use all
    }
    return result


def build_auto_recommend_task() -> Callable[[], Optional[str]]:
    """Build the scheduled task callable for auto-recommend scans.

    Returns:
        A no-arg callable that runs the engine and returns a short
        result summary (or None if disabled).
    """
    rec_cfg = get_recommend_config()
    if not rec_cfg["enabled"]:
        logger.info("auto_recommend is disabled — skipping scheduled task")
        return lambda: None

    engine = AutoRecommendEngine(
        top_n=rec_cfg["top_n"],
        deep_analyze_top_n=rec_cfg["deep_analyze"],
    )

    def task() -> str:
        logger.info("Auto-recommend scheduled task starting...")
        result = engine.run()
        if not result.success:
            logger.warning("Auto-recommend task failed: %s", result.error)
            return f"FAILED: {result.error}"
        picks = len(result.recommendations)
        scanned = result.total_scanned
        logger.info("Auto-recommend done: %d picks from %d stocks", picks, scanned)

        # Send notification with the report
        try:
            report = generate_recommend_report(result)
            svc = get_notification_service()
            svc.send(report)
        except Exception as exc:
            logger.warning("Auto-recommend notification failed: %s", exc)

        return f"OK: {picks} picks from {scanned} stocks"

    return task
