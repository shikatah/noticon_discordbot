import logging

from bot.client import CommunityBot
from config.settings import get_settings
from services.claude import ClaudeClient
from services.firestore import FirestoreService
from services.gemini import GeminiClient
from services.member_profile import MemberProfileService
from services.outreach import OutreachService
from services.primary_judge import PrimaryJudgeService
from services.scheduler import SchedulerService
from services.secondary_judge import SecondaryJudgeService
from services.topic_generator import TopicGeneratorService
from services.welcome import WelcomeService


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
    welcome_service = WelcomeService(
        claude=claude_client,
        timezone_name=settings.bot_timezone,
    )
    topic_generator_service = TopicGeneratorService(claude=claude_client)
    outreach_service = OutreachService(claude=claude_client)
    scheduler_service = SchedulerService()

    bot = CommunityBot(
        settings=settings,
        firestore=firestore_service,
        primary_judge=primary_judge_service,
        secondary_judge=secondary_judge_service,
        member_profile=member_profile_service,
        welcome=welcome_service,
        topic_generator=topic_generator_service,
        outreach=outreach_service,
        scheduler=scheduler_service,
    )
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
