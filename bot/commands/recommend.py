# -*- coding: utf-8 -*-
"""
===================================
AI 自动荐股命令
===================================

扫描全市场，发现候选股并生成推荐报告。
"""

import logging
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class RecommendCommand(BotCommand):
    """
    AI 自动荐股命令

    扫描全市场，通过多通道发现候选股，评分排序后生成推荐报告。

    用法：
        /recommend          - 完整推荐（扫描全部通道）
        /recommend 快速     - 快速推荐（仅板块+因子通道，top3）
    """

    @property
    def name(self) -> str:
        return "recommend"

    @property
    def aliases(self) -> List[str]:
        return ["荐股", "推荐"]

    @property
    def description(self) -> str:
        return "AI 自动荐股"

    @property
    def usage(self) -> str:
        return "/recommend [快速]"

    def validate_args(self, args: List[str]) -> Optional[str]:
        if args and args[0] not in ("快速", "quick", "full", "完整"):
            return f"未知参数: {args[0]}，用法: {self.usage}"
        return None

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        is_quick = args and args[0] in ("快速", "quick")
        mode_label = "快速推荐" if is_quick else "完整推荐"

        try:
            from src.services.auto_recommend.engine import AutoRecommendEngine
            from src.services.auto_recommend.report import generate_recommend_report
            from src.services.auto_recommend.models import ChannelType

            if is_quick:
                engine = AutoRecommendEngine(
                    top_n=5,
                    deep_analyze_top_n=1,
                    enabled_channels=[ChannelType.SECTOR, ChannelType.FACTOR],
                )
            else:
                from src.config import get_config
                config = get_config()
                engine = AutoRecommendEngine(
                    top_n=config.auto_recommend_top_n,
                    deep_analyze_top_n=config.auto_recommend_deep_analyze,
                )

            result = engine.run()

            if not result.success:
                return BotResponse.markdown_response(
                    f"ℹ️ **{mode_label}**\n\n{result.error or '未找到符合条件的标的'}"
                )

            report = generate_recommend_report(result)

            return BotResponse.markdown_response(report)

        except Exception as e:
            logger.error("[RecommendCommand] 执行失败: %s", e)
            return BotResponse.error_response(f"荐股失败: {str(e)[:100]}")
