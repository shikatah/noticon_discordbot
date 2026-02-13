import logging

from bot.client import CommunityBot
from config.settings import get_settings
from services.claude import ClaudeClient
from services.firestore import FirestoreService
from services.gemini import GeminiClient
from services.member_profile import MemberProfileService
from services.primary_judge import PrimaryJudgeService
from services.secondary_judge import SecondaryJudgeService


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = get_settings()
    firestore_service = FirestoreService(project_id=settings.google_cloud_project)
    gemini_client = GeminiClient(api_key=settings.gemini_api_key)
    primary_judge_service = PrimaryJudgeService(gemini=gemini_client)
    claude_client = ClaudeClient(api_key=settings.anthropic_api_key)
    secondary_judge_service = SecondaryJudgeService(claude=claude_client)
    member_profile_service = MemberProfileService()

    bot = CommunityBot(
        settings=settings,
        firestore=firestore_service,
        primary_judge=primary_judge_service,
        secondary_judge=secondary_judge_service,
        member_profile=member_profile_service,
    )
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
