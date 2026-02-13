import asyncio
import logging

from models.message import MessageRecord

try:
    from google.cloud import firestore
except Exception:  # pragma: no cover
    firestore = None

logger = logging.getLogger(__name__)


class FirestoreService:
    def __init__(self, project_id: str | None) -> None:
        self.project_id = project_id
        self.enabled = False
        self._client = None

        if firestore is None:
            logger.warning("google-cloud-firestore is unavailable. Firestore disabled.")
            return

        if not project_id:
            logger.warning("GOOGLE_CLOUD_PROJECT is not set. Firestore disabled.")
            return

        try:
            self._client = firestore.Client(project=project_id)
            self.enabled = True
            logger.info("Firestore enabled for project: %s", project_id)
        except Exception:
            logger.exception("Failed to initialize Firestore. Firestore disabled.")

    async def save_message(self, record: MessageRecord) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(self._save_message_sync, record)

    def _save_message_sync(self, record: MessageRecord) -> None:
        assert self._client is not None
        doc_ref = (
            self._client.collection("community_bot")
            .document("messages")
            .collection("items")
            .document(record.message_id)
        )
        doc_ref.set(record.to_dict())
