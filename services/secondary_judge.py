import json
import logging
import re
from pathlib import Path

from models.decision import SecondaryDecision
from services.claude import ClaudeClient

logger = logging.getLogger(__name__)


class SecondaryJudgeService:
    def __init__(self, claude: ClaudeClient, prompt_path: str = "prompts/secondary_judge.txt") -> None:
        self.claude = claude
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")

    async def judge(self, payload: dict[str, object]) -> SecondaryDecision:
        if self.claude.enabled:
            try:
                raw = await self.claude.generate_json(self.prompt, payload)
                parsed = self._parse_json(raw)
                return SecondaryDecision(
                    intervention_type=str(parsed.get("intervention_type", "silent")),
                    tone=str(parsed.get("tone", "warm")),
                    content=str(parsed.get("content", "")),
                    mention_users=self._to_str_list(parsed.get("mention_users")),
                    reaction_emoji=self._to_optional_str(parsed.get("reaction_emoji")),
                    confidence=self._clamp_confidence(parsed.get("confidence")),
                    reasoning=str(parsed.get("reasoning", "二次判断")),
                    model=self.claude.model_name,
                    raw_response=raw,
                )
            except Exception:
                logger.exception("Secondary judge parse/generate failed. Falling back.")

        return SecondaryDecision(
            intervention_type="silent",
            tone="warm",
            content="",
            mention_users=[],
            reaction_emoji=None,
            confidence=0.0,
            reasoning="Claude未設定またはエラーのため見守り",
            model="fallback-rule",
        )

    def _parse_json(self, raw: str) -> dict[str, object]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)

        if cleaned.startswith("{") and cleaned.endswith("}"):
            return json.loads(cleaned)

        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise ValueError("No JSON object found in model output.")
        return json.loads(match.group(0))

    def _to_optional_str(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _to_str_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        results: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                results.append(text)
        return results

    def _clamp_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, confidence))
