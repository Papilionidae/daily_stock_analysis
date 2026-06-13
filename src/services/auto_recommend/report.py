# -*- coding: utf-8 -*-
"""Report generation for auto-recommend engine output."""

from __future__ import annotations

from datetime import datetime
from typing import List

from src.services.auto_recommend.models import (
    RecommendationRecord,
    RecommendationResult,
)

HEADER_TEMPLATE = (
    "# 📊 AI 自动荐股报告\n"
    "> 生成时间: {timestamp}\n"
    "> 扫描股票: {total_scanned} 只 | 推荐: {rec_count} 只\n"
    "\n"
)

NO_RESULT = "今日暂无推荐。\n\n原因: {reason}"

EMPTY_RESULT = "当日扫描无符合条件标的。\n"


def _format_recommendation(rec: RecommendationRecord, rank: int) -> str:
    """Format a single recommendation record as markdown."""
    signal_icon = {
        "buy": "🟢",
        "watch": "🟡",
        "hold": "⚪",
        "sell": "🔴",
    }.get(rec.signal.value, "⚪")

    tags = ", ".join(rec.strategy_tags) if rec.strategy_tags else "—"
    summary = rec.summary or "—"

    return (
        f"### {rank}. {rec.stock_code} {signal_icon}\n"
        f"- **信号**: {rec.signal.value.upper()} | "
        f"**置信度**: {rec.confidence:.0%}\n"
        f"- **来源通道**: {rec.channel.value}\n"
        f"- **策略标签**: {tags}\n"
        f"- **简评**: {summary}\n"
    )


def generate_recommend_report(result: RecommendationResult) -> str:
    """Generate a markdown report from a RecommendationResult.

    Args:
        result: The recommendation result from the engine.

    Returns:
        Markdown-formatted report string.
    """
    if not result.success:
        reason = result.error or "未知错误"
        return NO_RESULT.format(reason=reason)

    recs = result.recommendations
    if not recs:
        return EMPTY_RESULT

    # Sort by confidence descending
    sorted_recs = sorted(recs, key=lambda r: r.confidence, reverse=True)

    parts = [
        HEADER_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            total_scanned=result.total_scanned,
            rec_count=len(sorted_recs),
        )
    ]

    # Channel breakdown
    channel_counts: dict = {}
    for r in sorted_recs:
        ch = r.channel.value
        channel_counts[ch] = channel_counts.get(ch, 0) + 1
    parts.append("**通道分布**: " + ", ".join(
        f"{ch}: {cnt}只" for ch, cnt in channel_counts.items()
    ))
    parts.append("")

    # Market context summary
    ctx = result.market_context
    if ctx:
        ctx_lines = []
        if ctx.indices:
            idx_str = " | ".join(f"{k}: {v}" for k, v in ctx.indices.items())
            ctx_lines.append(f"**指数**: {idx_str}")
        if ctx.market_state != "unknown":
            ctx_lines.append(f"**市场状态**: {ctx.market_state}")
        if ctx_lines:
            parts.extend(ctx_lines)
            parts.append("")

    # Per-recommendation details
    for i, rec in enumerate(sorted_recs, 1):
        parts.append(_format_recommendation(rec, i))

    parts.append("---")
    parts.append("*🤖 由 AI 自动荐股引擎生成 | 仅供参考，不构成投资建议*")

    return "\n".join(parts)
