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
