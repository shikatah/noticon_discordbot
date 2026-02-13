import logging
from pathlib import Path

from services.claude import ClaudeClient

logger = logging.getLogger(__name__)


class OutreachService:
    def __init__(self, claude: ClaudeClient, prompt_path: str = "prompts/inactive_outreach.txt") -> None:
        self.claude = claude
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")

    async def generate_dm(
        self,
        member_name: str,
        interest_topics: list[str],
        recent_topics_summary: str,
    ) -> str:
        if self.claude.enabled:
            try:
                text = await self.claude.generate_text(
                    system_prompt=self.prompt,
                    payload={
                        "member_name": member_name,
                        "member_interest_topics": interest_topics,
                        "recent_community_topics_summary": recent_topics_summary,
                    },
                    max_tokens=260,
                )
                if text.strip():
                    return text.strip()
            except Exception:
                logger.exception("Outreach DM generation failed. Using fallback.")

        topics = "、".join(interest_topics[:3]) if interest_topics else "Notion活用"
        return (
            f"{member_name}さん、お久しぶりです。\n"
            f"最近のノチコンでは {recent_topics_summary} の話題が出ていました。\n"
            f"{topics} が好きな方にも役立つ内容だったので、時間があるときにぜひ覗いてみてください。"
        )
