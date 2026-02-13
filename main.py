import logging

from bot.client import CommunityBot
from config.settings import get_settings
from services.firestore import FirestoreService
from services.gemini import GeminiClient
from services.primary_judge import PrimaryJudgeService


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = get_settings()
    firestore_service = FirestoreService(project_id=settings.google_cloud_project)
    gemini_client = GeminiClient(api_key=settings.gemini_api_key)
    primary_judge_service = PrimaryJudgeService(gemini=gemini_client)

    bot = CommunityBot(
        settings=settings,
        firestore=firestore_service,
        primary_judge=primary_judge_service,
    )
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
