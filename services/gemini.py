import asyncio
import json
import logging

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, api_key: str | None, model_name: str = "gemini-2.0-flash") -> None:
        self.model_name = model_name
        self.enabled = False
        self._model = None

        if genai is None:
            logger.warning("google-generativeai is unavailable. Gemini disabled.")
            return
        if not api_key:
            logger.warning("GEMINI_API_KEY is not set. Gemini disabled.")
            return

        try:
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(model_name=model_name)
            self.enabled = True
            logger.info("Gemini enabled with model: %s", model_name)
        except Exception:
            logger.exception("Failed to initialize Gemini client. Gemini disabled.")

    async def generate_json(self, system_prompt: str, payload: dict[str, object]) -> str:
        if not self.enabled or self._model is None:
            raise RuntimeError("Gemini is disabled.")

        prompt = (
            f"{system_prompt}\n\n"
            "## 入力データ\n"
            f"{json.dumps(payload, ensure_ascii=False)}\n\n"
            "JSONのみを返してください。"
        )
        response = await asyncio.to_thread(self._model.generate_content, prompt)
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        # Fallback for SDK responses where `text` may be empty.
        candidates = getattr(response, "candidates", None)
        if not candidates:
            return ""

        parts: list[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            for part in getattr(content, "parts", []):
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str):
                    parts.append(part_text)
        return "\n".join(parts).strip()
