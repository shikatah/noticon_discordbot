from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class PrimaryDecision:
    needs_intervention: bool
    reason: str
    priority: int
    model: str
    judged_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_response: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "needs_intervention": self.needs_intervention,
            "reason": self.reason,
            "priority": self.priority,
            "model": self.model,
            "judged_at": self.judged_at,
            "raw_response": self.raw_response,
        }


@dataclass(slots=True)
class SecondaryDecision:
    intervention_type: str
    tone: str
    content: str
    mention_users: list[str]
    reaction_emoji: str | None
    confidence: float
    reasoning: str
    model: str
    judged_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_response: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "intervention_type": self.intervention_type,
            "tone": self.tone,
            "content": self.content,
            "mention_users": self.mention_users,
            "reaction_emoji": self.reaction_emoji,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "model": self.model,
            "judged_at": self.judged_at,
            "raw_response": self.raw_response,
        }
