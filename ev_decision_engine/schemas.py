from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Action(Enum):
    SUPPRESS = "SUPPRESS"
    VERIFY = "VERIFY"
    SEND = "SEND"
    ESCALATE = "ESCALATE"
    BROADCAST = "BROADCAST"
    PROPOSE_REMEDIATION = "PROPOSE_REMEDIATION"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"


class Event(BaseModel):
    event_type: str
    region: str
    severity: float
    timestamp: datetime
    correlation_id: str


class TrustMetadata(BaseModel):
    source_agent: str
    confidence: float
    historical_false_positive_rate: float
    is_directly_observed: bool
    corroborating_source_count: int
    ttl_seconds: int
    asset_criticality: float


class Message(BaseModel):
    event: Event
    trust: TrustMetadata


class Decision(BaseModel):
    chosen_action: Action
    action_scores: dict[Action, float]
    explanation: str
