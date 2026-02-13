import asyncio
import json
import logging

try:
    from anthropic import Anthropic
except Exception:  # pragma: no cover
    Anthropic = None

logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(
        self,
        api_key: str | None,
        model_name: str = "claude-3-5-sonnet-latest",
    ) -> None:
        self.model_name = model_name
        self.enabled = False
        self._client = None

        if Anthropic is None:
            logger.warning("anthropic SDK is unavailable. Claude disabled.")
            return
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY is not set. Claude disabled.")
            return

        try:
            self._client = Anthropic(api_key=api_key)
            self.enabled = True
            logger.info("Claude enabled with model: %s", model_name)
        except Exception:
            logger.exception("Failed to initialize Claude client. Claude disabled.")

    async def generate_json(self, system_prompt: str, payload: dict[str, object]) -> str:
        if not self.enabled or self._client is None:
            raise RuntimeError("Claude is disabled.")

        user_text = (
            "次の情報を元に、指定フォーマットのJSONだけを返してください。\n\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        response = await asyncio.to_thread(
            self._client.messages.create,
            model=self.model_name,
            max_tokens=700,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )

        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts).strip()
