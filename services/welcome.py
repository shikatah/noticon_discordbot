import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from services.claude import ClaudeClient

logger = logging.getLogger(__name__)


class WelcomeService:
    def __init__(
        self,
        claude: ClaudeClient,
        timezone_name: str,
        prompt_path: str = "prompts/welcome_message.txt",
    ) -> None:
        self.claude = claude
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")
        self.timezone = ZoneInfo(timezone_name)

    async def generate_message(self, member_name: str, now_utc: datetime) -> str:
        if self.claude.enabled:
            try:
                local_now = now_utc.astimezone(self.timezone)
                text = await self.claude.generate_text(
                    system_prompt=self.prompt,
                    payload={
                        "member_name": member_name,
                        "current_time": local_now.isoformat(),
                    },
                    max_tokens=220,
                )
                if text.strip():
                    return text.strip()
            except Exception:
                logger.exception("Welcome message generation failed. Using fallback.")

        return self._fallback(member_name, now_utc)

    def _fallback(self, member_name: str, now_utc: datetime) -> str:
        hour = now_utc.astimezone(self.timezone).hour
        if 5 <= hour < 11:
            greeting = "おはようございます"
        elif 11 <= hour < 18:
            greeting = "こんにちは"
        else:
            greeting = "こんばんは"
        return (
            f"{greeting}、{member_name}さん。ノチコンへようこそ！\n"
            "Notionの学びを気軽に共有できるコミュニティです。\n"
            "まずは #自己紹介 で簡単に自己紹介してもらえると嬉しいです。\n"
            "困ったことがあればいつでも声をかけてください。"
        )
