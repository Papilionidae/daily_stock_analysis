# -*- coding: utf-8 -*-
"""
===================================
AI 自动荐股接口
===================================
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_config_dep
from api.v1.errors import api_error

logger = logging.getLogger(__name__)

router = APIRouter()


class AutoRecommendRequest(BaseModel):
    mode: str = Field("full", description="推荐模式: full | quick")
    top_n: int = Field(10, ge=1, le=50, description="候选股 top N 数量")
    deep_analyze: int = Field(3, ge=1, le=20, description="深度分析 top N 数量")
    notify: bool = Field(False, description="是否推送到通知渠道")


class AutoRecommendStock(BaseModel):
    stock_code: str
    stock_name: str
    channel: str
    signal: str
    confidence: float
    sector: Optional[str] = None
    summary: str


class AutoRecommendResponse(BaseModel):
    success: bool
    candidates: list[str]
    recommendations: list[AutoRecommendStock]
    total_scanned: int
    report_markdown: str


@router.post(
    "/run",
    response_model=AutoRecommendResponse,
    summary="触发 AI 自动荐股",
    description="扫描全市场，通过多通道发现候选股并生成推荐报告。",
)
def run_auto_recommend(
    request: AutoRecommendRequest,
    config=Depends(get_config_dep),
) -> AutoRecommendResponse:
    from src.services.auto_recommend.engine import AutoRecommendEngine
    from src.services.auto_recommend.report import generate_recommend_report
    from src.services.auto_recommend.models import ChannelType

    if request.mode == "quick":
        engine = AutoRecommendEngine(
            top_n=5,
            deep_analyze_top_n=1,
            enabled_channels=[ChannelType.SECTOR, ChannelType.FACTOR],
        )
    else:
        engine = AutoRecommendEngine(
            top_n=request.top_n,
            deep_analyze_top_n=request.deep_analyze,
        )

    result = engine.run()
    report_md = generate_recommend_report(result)

    if request.notify and result.success:
        try:
            from src.notification import get_notification_service
            svc = get_notification_service()
            svc.send(report_md)
        except Exception as exc:
            logger.warning("auto-recommend notification failed: %s", exc)

    if not result.success:
        raise api_error(500, "recommend_failed", result.error or "推荐失败")

    recs = [
        AutoRecommendStock(
            stock_code=r.stock_code,
            stock_name=r.stock_code,
            channel=r.channel.value,
            signal=r.signal.value,
            confidence=r.confidence,
            sector=None,
            summary=r.summary,
        )
        for r in result.recommendations
    ]

    return AutoRecommendResponse(
        success=True,
        candidates=result.candidates or [],
        recommendations=recs,
        total_scanned=result.total_scanned,
        report_markdown=report_md,
    )


@router.get(
    "/last",
    summary="获取最近一次推荐结果",
    description="返回最近一次自动荐股的报告 Markdown。",
)
def get_last_recommend() -> Dict[str, Any]:
    try:
        from src.services.auto_recommend.engine import AutoRecommendEngine
        from src.services.auto_recommend.report import generate_recommend_report

        engine = AutoRecommendEngine()
        result = engine.run()

        if not result.success:
            return {"success": False, "report_markdown": "", "error": result.error}

        report_md = generate_recommend_report(result)
        return {
            "success": True,
            "total_scanned": result.total_scanned,
            "pick_count": len(result.recommendations),
            "report_markdown": report_md,
        }
    except Exception as exc:
        logger.error("get_last_recommend failed: %s", exc)
        raise api_error(500, "internal_error", f"获取推荐结果失败: {str(exc)[:100]}")
