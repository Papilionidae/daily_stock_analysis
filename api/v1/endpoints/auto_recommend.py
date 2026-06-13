# -*- coding: utf-8 -*-
"""
===================================
AI 自动荐股接口
===================================
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_config_dep
from api.v1.errors import api_error

logger = logging.getLogger(__name__)

router = APIRouter()

_last_result: Optional["AutoRecommendResponse"] = None

ENGINE_TIMEOUT = 600  # seconds


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


def _build_engine(mode: str, top_n: int, deep_analyze: int):
    from src.services.auto_recommend.engine import AutoRecommendEngine
    from src.services.auto_recommend.models import ChannelType

    if mode == "quick":
        return AutoRecommendEngine(
            top_n=5,
            deep_analyze_top_n=1,
            enabled_channels=[ChannelType.SECTOR, ChannelType.FACTOR],
        )
    return AutoRecommendEngine(top_n=top_n, deep_analyze_top_n=deep_analyze)


def _run_engine(engine) -> tuple:
    from src.services.auto_recommend.report import generate_recommend_report

    result = engine.run()
    report_md = generate_recommend_report(result)
    return result, report_md


def _build_response(result, report_md: str) -> "AutoRecommendResponse":
    if not result.success:
        return AutoRecommendResponse(
            success=False,
            candidates=[],
            recommendations=[],
            total_scanned=result.total_scanned,
            report_markdown=report_md,
        )
    recs = [
        AutoRecommendStock(
            stock_code=r.stock_code,
            stock_name=r.stock_name or r.stock_code,
            channel=r.channel.value,
            signal=r.signal.value,
            confidence=r.confidence,
            sector=r.sector,
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


@router.post(
    "/run",
    response_model=AutoRecommendResponse,
    summary="触发 AI 自动荐股",
    description="扫描全市场，通过多通道发现候选股并生成推荐报告。",
)
async def run_auto_recommend(
    request: AutoRecommendRequest,
    config=Depends(get_config_dep),
) -> "AutoRecommendResponse":
    engine = _build_engine(request.mode, request.top_n, request.deep_analyze)

    try:
        result, report_md = await asyncio.wait_for(
            asyncio.to_thread(_run_engine, engine),
            timeout=ENGINE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error("auto-recommend engine timed out after %ds", ENGINE_TIMEOUT)
        raise api_error(503, "engine_timeout", f"荐股引擎执行超时（{ENGINE_TIMEOUT}s）")

    resp = _build_response(result, report_md)

    global _last_result
    _last_result = resp

    if request.notify and result.success:
        try:
            from src.notification import get_notification_service

            svc = get_notification_service()
            await asyncio.to_thread(svc.send, report_md)
        except Exception as exc:
            logger.warning("auto-recommend notification failed: %s", exc)

    return resp


@router.get(
    "/last",
    response_model=AutoRecommendResponse,
    summary="获取最近一次推荐结果",
    description="返回最近一次自动荐股的结果（缓存优先，无缓存时执行一次默认扫描）。",
)
async def get_last_recommend() -> "AutoRecommendResponse":
    global _last_result
    if _last_result is not None:
        return _last_result

    try:
        engine = _build_engine("full", 10, 3)
        result, report_md = await asyncio.wait_for(
            asyncio.to_thread(_run_engine, engine),
            timeout=ENGINE_TIMEOUT,
        )

        resp = _build_response(result, report_md)
        _last_result = resp
        return resp
    except asyncio.TimeoutError:
        logger.error("auto-recommend engine timed out after %ds", ENGINE_TIMEOUT)
        raise api_error(503, "engine_timeout", f"荐股引擎执行超时（{ENGINE_TIMEOUT}s）")
    except Exception as exc:
        logger.error("get_last_recommend failed: %s", exc)
        raise api_error(500, "internal_error", f"获取推荐结果失败: {str(exc)[:100]}")
