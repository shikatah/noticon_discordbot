import asyncio
import logging

from models.decision import PrimaryDecision
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

    async def save_primary_decision(
        self,
        message_id: str,
        input_payload: dict[str, object],
        decision: PrimaryDecision,
    ) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(
            self._save_primary_decision_sync,
            message_id,
            input_payload,
            decision,
        )

    async def save_bot_action(self, action_id: str, payload: dict[str, object]) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(self._save_bot_action_sync, action_id, payload)

    async def update_message_bot_action(
        self,
        message_id: str,
        action_type: str,
        action_at: object,
    ) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(
            self._update_message_bot_action_sync,
            message_id,
            action_type,
            action_at,
        )

    def _save_message_sync(self, record: MessageRecord) -> None:
        assert self._client is not None
        doc_ref = (
            self._client.collection("community_bot")
            .document("messages")
            .collection("items")
            .document(record.message_id)
        )
        doc_ref.set(record.to_dict())

    def _save_primary_decision_sync(
        self,
        message_id: str,
        input_payload: dict[str, object],
        decision: PrimaryDecision,
    ) -> None:
        assert self._client is not None
        doc_ref = (
            self._client.collection("community_bot")
            .document("decision_logs")
            .collection("items")
            .document(message_id)
        )
        doc_ref.set(
            {
                "message_id": message_id,
                "input": input_payload,
                "decision": decision.to_dict(),
            },
            merge=True,
        )

    def _save_bot_action_sync(self, action_id: str, payload: dict[str, object]) -> None:
        assert self._client is not None
        doc_ref = (
            self._client.collection("community_bot")
            .document("bot_actions")
            .collection("items")
            .document(action_id)
        )
        doc_ref.set(payload, merge=True)

    def _update_message_bot_action_sync(
        self,
        message_id: str,
        action_type: str,
        action_at: object,
    ) -> None:
        assert self._client is not None
        doc_ref = (
            self._client.collection("community_bot")
            .document("messages")
            .collection("items")
            .document(message_id)
        )
        doc_ref.set(
            {
                "bot_action": action_type,
                "bot_action_at": action_at,
            },
            merge=True,
        )
