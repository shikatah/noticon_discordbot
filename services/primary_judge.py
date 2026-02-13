import json
import logging
import re
from pathlib import Path

from models.decision import PrimaryDecision
from services.gemini import GeminiClient

logger = logging.getLogger(__name__)


class PrimaryJudgeService:
    def __init__(self, gemini: GeminiClient, prompt_path: str = "prompts/primary_judge.txt") -> None:
        self.gemini = gemini
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")

    async def judge(self, payload: dict[str, object]) -> PrimaryDecision:
        if self.gemini.enabled:
            try:
                raw = await self.gemini.generate_json(self.prompt, payload)
                parsed = self._parse_json(raw)
                return PrimaryDecision(
                    needs_intervention=bool(parsed.get("needs_intervention", False)),
                    reason=str(parsed.get("reason", "一次判断で介入不要")),
                    priority=self._clamp_priority(parsed.get("priority")),
                    model=self.gemini.model_name,
                    raw_response=raw,
                )
            except Exception:
                logger.exception("Primary judge parse/generate failed. Falling back.")

        return self._fallback_decision(payload)

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

    def _clamp_priority(self, value: object) -> int:
        try:
            priority = int(value)
        except (TypeError, ValueError):
            return 1
        return max(1, min(5, priority))

    def _fallback_decision(self, payload: dict[str, object]) -> PrimaryDecision:
        is_bot_mentioned = bool(payload.get("is_bot_mentioned", False))
        in_quiet_hours = bool(payload.get("in_quiet_hours", False))
        has_reply = bool(payload.get("has_reply", False))
        has_reaction = bool(payload.get("has_reaction", False))
        author_is_new = bool(payload.get("author_is_new", False))
        recent_channel_activity = int(payload.get("recent_channel_activity", 0) or 0)
        hours_since_post = float(payload.get("hours_since_post", 0.0) or 0.0)
        text = str(payload.get("message_content", ""))

        if is_bot_mentioned:
            return PrimaryDecision(
                needs_intervention=True,
                reason="Botへのメンションのため即時介入",
                priority=5,
                model="fallback-rule",
            )
        if in_quiet_hours:
            return PrimaryDecision(
                needs_intervention=False,
                reason="深夜帯のため見守り",
                priority=1,
                model="fallback-rule",
            )
        if recent_channel_activity >= 3:
            return PrimaryDecision(
                needs_intervention=False,
                reason="会話が進行中のため見守り",
                priority=1,
                model="fallback-rule",
            )
        if has_reply or has_reaction:
            return PrimaryDecision(
                needs_intervention=False,
                reason="既に反応があるため介入不要",
                priority=1,
                model="fallback-rule",
            )

        looks_like_question = ("?" in text) or ("？" in text) or text.strip().endswith("か")
        if author_is_new:
            return PrimaryDecision(
                needs_intervention=True,
                reason="新規メンバー投稿のため優先確認",
                priority=4,
                model="fallback-rule",
            )
        if looks_like_question and hours_since_post >= 2.0:
            return PrimaryDecision(
                needs_intervention=True,
                reason="質問投稿が放置されている可能性",
                priority=4,
                model="fallback-rule",
            )
        return PrimaryDecision(
            needs_intervention=False,
            reason="ルール上、現時点では見守り",
            priority=1,
            model="fallback-rule",
        )
