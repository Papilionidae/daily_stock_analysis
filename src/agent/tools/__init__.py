# -*- coding: utf-8 -*-
"""
Agent tools package.

Provides ToolRegistry, @tool decorator, and wrapped tools
for the stock analysis agent.
"""

from src.agent.tools.registry import ToolRegistry, ToolDefinition, ToolParameter, tool
from src.agent.tools.factor_tools import (
    ALL_FACTOR_TOOLS,
    get_factor_universe_tool,
    get_factor_scores_tool,
    get_universe_screen_tool,
)

__all__ = [
    "ToolRegistry",
    "ToolDefinition",
    "ToolParameter",
    "tool",
    "ALL_FACTOR_TOOLS",
    "get_factor_universe_tool",
    "get_factor_scores_tool",
    "get_universe_screen_tool",
]
