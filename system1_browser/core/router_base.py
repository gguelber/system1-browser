"""
Base Action Router for system1-browser.
Provides a clean, pluggable abstract base class allowing any developer
to connect their own custom System-1 decision model in under 10 lines of code.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from system1_browser.core.types import PageState, ActionDecision

class BaseActionRouter(ABC):
    """
    Abstract Base Class for System-1 Browser Routers.
    
    Implement this class to plug any local classifier (Julia-1, FastText,
    custom fine-tuned models, ONNX runtime, or heuristics) into system1-browser.
    """
    @abstractmethod
    def predict(self, state: PageState, goal: str) -> ActionDecision:
        """
        Receives the pruned page state (~250 tokens) and the high-level sub-goal,
        and returns a deterministic, low-latency mechanical action decision.
        
        Args:
            state: Pruned representation of interactive elements currently visible on page.
            goal: The high-level instruction provided by the user or cloud LLM.
            
        Returns:
            ActionDecision indicating action_type ('click', 'type', 'wait', 'finish', 'escalate'),
            target_id, optional input_text, and confidence score.
        """
        pass

    def warmup(self):
        """Optional hook to pre-load weights or warm up the inference engine."""
        pass
