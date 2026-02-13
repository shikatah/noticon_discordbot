import logging

from bot.client import CommunityBot
from config.settings import get_settings
from services.firestore import FirestoreService


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = get_settings()
    firestore_service = FirestoreService(project_id=settings.google_cloud_project)

    bot = CommunityBot(settings=settings, firestore=firestore_service)
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
