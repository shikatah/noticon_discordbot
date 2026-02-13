import logging
from pathlib import Path

from services.claude import ClaudeClient

logger = logging.getLogger(__name__)


class TopicGeneratorService:
    def __init__(self, claude: ClaudeClient, prompt_path: str = "prompts/topic_generator.txt") -> None:
        self.claude = claude
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")
        self._fallback_index = 0
        self._fallback_topics = [
            ("question", "今週、Notionで一番うまくいった使い方は何でしたか？"),
            ("poll", "Notionのタスク管理は、データベース派ですか？ページ派ですか？"),
            ("tip", "小ワザ共有: 最近気づいたNotionの便利機能があれば1つ教えてください。"),
            ("challenge", "今週のミニチャレンジ: 不要ページを3つ整理してみませんか？"),
            ("experience", "Notionと他ツール連携で『これは助かった』体験があれば聞きたいです。"),
        ]

    async def generate_topic(
        self,
        recent_topics: list[str],
        channel_type: str,
        recent_channel_summary: str,
    ) -> tuple[str, str]:
        if self.claude.enabled:
            try:
                content = await self.claude.generate_text(
                    system_prompt=self.prompt,
                    payload={
                        "recent_bot_topics": recent_topics[-10:],
                        "channel_type": channel_type,
                        "recent_channel_summary": recent_channel_summary,
                    },
                    max_tokens=220,
                )
                content = content.strip()
                if content:
                    return self._dedupe_if_needed(content, recent_topics), self._infer_topic_type(content)
            except Exception:
                logger.exception("Topic generation failed. Using fallback.")

        fallback_type, fallback_text = self._next_fallback()
        return self._dedupe_if_needed(fallback_text, recent_topics), fallback_type

    def _next_fallback(self) -> tuple[str, str]:
        topic = self._fallback_topics[self._fallback_index % len(self._fallback_topics)]
        self._fallback_index += 1
        return topic

    def _infer_topic_type(self, text: str) -> str:
        lowered = text.lower()
        if "どっち" in text or "vs" in lowered or "派" in text:
            return "poll"
        if "チャレンジ" in text:
            return "challenge"
        if "小ワザ" in text or "tips" in lowered or "便利" in text:
            return "tip"
        if "?" in text or "？" in text:
            return "question"
        return "question"

    def _dedupe_if_needed(self, content: str, recent_topics: list[str]) -> str:
        normalized = content.strip()
        for old in recent_topics[-5:]:
            if normalized == old.strip():
                return normalized + "\n（前回と少し視点を変えて、みなさんの工夫もぜひ聞かせてください）"
        return normalized
