"""
Type definitions for eikos-browser.
"""
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class InteractiveElement(BaseModel):
    id: int
    tag: str
    type: Optional[str] = ""
    label: str
    name: Optional[str] = ""
    dom_id: Optional[str] = ""
    role: Optional[str] = ""
    disabled: bool = False
    x: int
    y: int
    selector: str

class PageState(BaseModel):
    url: str
    title: str
    alerts: List[str] = Field(default_factory=list)
    isLoading: Optional[bool] = False
    loadingReason: Optional[str] = ""
    elementCount: int
    elements: List[InteractiveElement]

class ActionDecision(BaseModel):
    action_type: Literal["click", "type", "select", "wait", "finish", "escalate"]
    target_id: Optional[int] = None
    target_element: Optional[InteractiveElement] = None
    input_text: Optional[str] = None
    confidence: float = 1.0
    rationale: str = ""

class StepRecord(BaseModel):
    step_num: int
    action: ActionDecision
    page_title_before: str
    page_title_after: str
    url_after: str
    alerts_after: List[str] = Field(default_factory=list)
    duration_ms: float

class SubgoalResult(BaseModel):
    goal: str
    status: Literal["COMPLETED", "ESCALATED", "MAX_STEPS_REACHED"]
    steps_count: int
    message: str
    history: List[StepRecord] = Field(default_factory=list)
    total_time_ms: float
