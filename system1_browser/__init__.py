"""
system1-browser: Pluggable System-1 Fast Browser Navigation Coprocessor for AI Agents
Supports multiple fast decision backends: Julia-1 (540MB ultralight), Eikos-4B, or local heuristics.
"""
import asyncio
from typing import Optional, Literal
from system1_browser.cdp.client import CDPClient
from system1_browser.core.runner import SubgoalRunner
from system1_browser.core.types import (
    PageState, InteractiveElement, ActionDecision, StepRecord, SubgoalResult
)

class BrowserCoprocessor:
    """
    High-level entrypoint for executing autonomous browser sub-goals via System-1 models.
    """
    def __init__(
        self,
        backend: Literal["julia", "eikos", "auto", "mock"] = "julia",
        model_dir: Optional[str] = None
    ):
        self.cdp = CDPClient()
        self.runner = SubgoalRunner(cdp_client=self.cdp, backend=backend, model_dir=model_dir)

    def execute_subgoal(self, goal: str, max_steps: int = 8) -> SubgoalResult:
        """Synchronous wrapper for executing a sub-goal."""
        return asyncio.run(self.runner.run(goal=goal, max_steps=max_steps))

    async def execute_subgoal_async(self, goal: str, max_steps: int = 8) -> SubgoalResult:
        """Asynchronous execution of a sub-goal."""
        return await self.runner.run(goal=goal, max_steps=max_steps)

__all__ = [
    "BrowserCoprocessor",
    "CDPClient",
    "SubgoalRunner",
    "PageState",
    "InteractiveElement",
    "ActionDecision",
    "StepRecord",
    "SubgoalResult"
]
