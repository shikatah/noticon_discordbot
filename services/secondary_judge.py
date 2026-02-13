import json
import logging
import re
from pathlib import Path

from models.decision import SecondaryDecision
from services.claude import ClaudeClient

logger = logging.getLogger(__name__)

CHANNEL_PROMPT_SUFFIX = {
    "question": (
        "質問チャンネルです。短く具体的に。まず相手の要点を1点引用し、"
        "回答または次の一手を提示。質問は最大1つ。"
    ),
    "share": (
        "共有チャンネルです。称賛＋具体的な深掘りを優先。押しつけない。質問は最大1つ。"
    ),
    "chat": (
        "雑談チャンネルです。会話が進行中なら無理に割り込まない。介入は軽め・短め。"
    ),
    "intro": (
        "自己紹介チャンネルです。歓迎感を優先し、安心感のある短文にする。"
    ),
    "announce": (
        "告知チャンネルです。原則silent。必要な場合でもreact_onlyを優先。"
    ),
}

QUALITY_SYSTEM_PROMPT = """
あなたはDiscord投稿文の品質検査官です。
出力は必ずJSONのみ:
{
  "quality_score": 0.0-1.0,
  "issues": ["問題点"],
  "needs_regeneration": true/false
}
評価軸:
- 押しつけ感がない
- 冗長でない（短い）
- 文脈への言及がある
- 失礼/上から目線がない
- 質問は最大1つ
""".strip()

NG_PATTERNS = [
    "べきです",
    "絶対",
    "必ず〜してください",
    "普通は",
    "常識",
]


class SecondaryJudgeService:
    def __init__(self, claude: ClaudeClient, prompt_path: str = "prompts/secondary_judge.txt") -> None:
        self.claude = claude
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")

    async def judge(self, payload: dict[str, object]) -> SecondaryDecision:
        if self.claude.enabled:
            try:
                first = await self._generate_once(payload, retry=False)
                final = await self._quality_gate(payload, first)
                return final
            except Exception:
                logger.exception("Secondary judge parse/generate failed. Falling back.")

        return SecondaryDecision(
            intervention_type="silent",
            tone="warm",
            content="",
            mention_users=[],
            reaction_emoji=None,
            confidence=0.0,
            silence_confidence=1.0,
            quality_score=0.0,
            reasoning="Claude未設定またはエラーのため見守り",
            model="fallback-rule",
        )

    async def _generate_once(self, payload: dict[str, object], retry: bool) -> SecondaryDecision:
        channel_type = str(payload.get("channel_type", "chat"))
        suffix = CHANNEL_PROMPT_SUFFIX.get(channel_type, CHANNEL_PROMPT_SUFFIX["chat"])
        system_prompt = self.prompt + "\n\n## 追加ルール\n" + suffix
        if retry:
            system_prompt += (
                "\nさらに、押しつけ感のある表現を避け、"
                "文脈を1点引用し、質問は最大1つ、120文字程度に収めること。"
            )

        raw = await self.claude.generate_json(system_prompt, payload)
        parsed = self._parse_json(raw)
        decision = SecondaryDecision(
            intervention_type=str(parsed.get("intervention_type", "silent")),
            tone=str(parsed.get("tone", "warm")),
            content=str(parsed.get("content", "")),
            mention_users=self._to_str_list(parsed.get("mention_users")),
            reaction_emoji=self._to_optional_str(parsed.get("reaction_emoji")),
            confidence=self._clamp_score(parsed.get("confidence")),
            silence_confidence=self._clamp_score(parsed.get("silence_confidence")),
            quality_score=self._clamp_score(parsed.get("quality_score")),
            reasoning=str(parsed.get("reasoning", "二次判断")),
            model=self.claude.model_name,
            raw_response=raw,
        )
        return self._sanitize_output(payload, decision)

    async def _quality_gate(
        self,
        payload: dict[str, object],
        decision: SecondaryDecision,
    ) -> SecondaryDecision:
        if decision.intervention_type in {"silent", "react_only"}:
            decision.quality_score = max(decision.quality_score, 0.9)
            return decision

        if self._contains_ng_pattern(decision.content):
            retry_decision = await self._generate_once(payload, retry=True)
            if not self._contains_ng_pattern(retry_decision.content):
                retry_decision.quality_score = max(retry_decision.quality_score, 0.75)
                return retry_decision
            decision.intervention_type = "silent"
            decision.silence_confidence = max(decision.silence_confidence, 0.8)
            decision.quality_score = min(decision.quality_score, 0.4)
            decision.reasoning += " / NG表現検出のためsilent"
            return decision

        eval_result = await self._evaluate_quality(payload, decision)
        qscore = self._clamp_score(eval_result.get("quality_score"))
        needs_regen = bool(eval_result.get("needs_regeneration", False))
        decision.quality_score = max(decision.quality_score, qscore)
        if needs_regen or qscore < 0.7:
            retry_decision = await self._generate_once(payload, retry=True)
            retry_eval = await self._evaluate_quality(payload, retry_decision)
            retry_score = self._clamp_score(retry_eval.get("quality_score"))
            retry_decision.quality_score = max(retry_decision.quality_score, retry_score)
            if retry_score >= qscore:
                return retry_decision
        return decision

    async def _evaluate_quality(
        self,
        payload: dict[str, object],
        decision: SecondaryDecision,
    ) -> dict[str, object]:
        if not self.claude.enabled:
            return {"quality_score": decision.quality_score, "needs_regeneration": False}
        raw = await self.claude.generate_json(
            QUALITY_SYSTEM_PROMPT,
            {
                "message_content": payload.get("message_content", ""),
                "channel_type": payload.get("channel_type", ""),
                "generated_intervention_type": decision.intervention_type,
                "generated_content": decision.content,
                "generated_tone": decision.tone,
            },
        )
        return self._parse_json(raw)

    def _sanitize_output(self, payload: dict[str, object], decision: SecondaryDecision) -> SecondaryDecision:
        if decision.intervention_type in {"silent", "react_only"}:
            return decision
        content = decision.content.strip().replace("\n\n", "\n")
        if len(content) > 180:
            content = content[:180].rstrip() + "…"

        # Ensure one question maximum.
        question_count = content.count("?") + content.count("？")
        if question_count > 1:
            parts = re.split(r"(?<=[?？])", content)
            kept = []
            seen_q = 0
            for part in parts:
                if "?" in part or "？" in part:
                    seen_q += 1
                    if seen_q > 1:
                        part = part.replace("?", "。").replace("？", "。")
                kept.append(part)
            content = "".join(kept)

        # Force one contextual quote if missing.
        if "「" not in content:
            source = str(payload.get("message_content", "")).strip()
            if source:
                snippet = source[:24].replace("\n", " ")
                content = f"「{snippet}」の話、いいですね。{content}"

        decision.content = content
        return decision

    def _contains_ng_pattern(self, text: str) -> bool:
        compact = text.replace(" ", "")
        return any(pattern.replace(" ", "") in compact for pattern in NG_PATTERNS)

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

    def _clamp_score(self, value: object) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))
