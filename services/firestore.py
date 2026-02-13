import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

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

    async def save_member_profile(self, member_id: str, payload: dict[str, object]) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(self._save_member_profile_sync, member_id, payload)

    async def save_topic_post(self, topic_id: str, payload: dict[str, object]) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(self._save_topic_post_sync, topic_id, payload)

    async def save_outreach_log(self, log_id: str, payload: dict[str, object]) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(self._save_outreach_log_sync, log_id, payload)

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

    async def load_config(self) -> dict[str, object]:
        if not self.enabled or self._client is None:
            return {}
        return await asyncio.to_thread(self._load_config_sync)

    async def save_config_partial(self, payload: dict[str, object]) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(self._save_config_partial_sync, payload)

    async def list_recent_topics(self, limit: int = 10) -> list[dict[str, object]]:
        if not self.enabled or self._client is None:
            return []
        return await asyncio.to_thread(self._list_recent_topics_sync, limit)

    async def count_topics_for_date(self, date_key: str) -> int:
        if not self.enabled or self._client is None:
            return 0
        return await asyncio.to_thread(self._count_topics_for_date_sync, date_key)

    async def has_topic_for_channel_date(self, channel_id: str, date_key: str) -> bool:
        if not self.enabled or self._client is None:
            return False
        return await asyncio.to_thread(
            self._has_topic_for_channel_date_sync,
            channel_id,
            date_key,
        )

    async def has_topic_for_channel_hour(self, channel_id: str, hour_key: str) -> bool:
        if not self.enabled or self._client is None:
            return False
        return await asyncio.to_thread(
            self._has_topic_for_channel_hour_sync,
            channel_id,
            hour_key,
        )

    async def list_inactive_members(self, threshold_days: int) -> list[dict[str, object]]:
        if not self.enabled or self._client is None:
            return []
        return await asyncio.to_thread(self._list_inactive_members_sync, threshold_days)

    async def update_member_outreach(self, member_id: str, payload: dict[str, object]) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(self._update_member_outreach_sync, member_id, payload)

    async def update_member_intervention_preference(
        self,
        member_id: str,
        preferences: dict[str, object],
    ) -> None:
        if not self.enabled or self._client is None:
            return
        await asyncio.to_thread(
            self._update_member_intervention_preference_sync,
            member_id,
            preferences,
        )

    def _collection(self, name: str):
        assert self._client is not None
        return self._client.collection("community_bot").document("data").collection(name)

    def _save_message_sync(self, record: MessageRecord) -> None:
        self._collection("messages").document(record.message_id).set(record.to_dict())

    def _save_primary_decision_sync(
        self,
        message_id: str,
        input_payload: dict[str, object],
        decision: PrimaryDecision,
    ) -> None:
        self._collection("decision_logs").document(message_id).set(
            {
                "message_id": message_id,
                "input": input_payload,
                "decision": decision.to_dict(),
            },
            merge=True,
        )

    def _save_bot_action_sync(self, action_id: str, payload: dict[str, object]) -> None:
        self._collection("bot_actions").document(action_id).set(payload, merge=True)

    def _save_member_profile_sync(self, member_id: str, payload: dict[str, object]) -> None:
        self._collection("members").document(member_id).set(payload, merge=True)

    def _save_topic_post_sync(self, topic_id: str, payload: dict[str, object]) -> None:
        self._collection("bot_topics").document(topic_id).set(payload, merge=True)

    def _save_outreach_log_sync(self, log_id: str, payload: dict[str, object]) -> None:
        self._collection("outreach_logs").document(log_id).set(payload, merge=True)

    def _update_message_bot_action_sync(
        self,
        message_id: str,
        action_type: str,
        action_at: object,
    ) -> None:
        self._collection("messages").document(message_id).set(
            {
                "bot_action": action_type,
                "bot_action_at": action_at,
            },
            merge=True,
        )

    def _load_config_sync(self) -> dict[str, object]:
        doc = self._collection("config").document("settings").get()
        if not doc.exists:
            return {}
        data = doc.to_dict() or {}
        if not isinstance(data, dict):
            return {}
        return data

    def _save_config_partial_sync(self, payload: dict[str, object]) -> None:
        clean_payload = dict(payload)
        clean_payload["updated_at"] = datetime.now(timezone.utc)
        self._collection("config").document("settings").set(clean_payload, merge=True)

    def _list_recent_topics_sync(self, limit: int) -> list[dict[str, object]]:
        docs = (
            self._collection("bot_topics")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        results: list[dict[str, object]] = []
        for doc in docs:
            data = doc.to_dict() or {}
            if not isinstance(data, dict):
                continue
            data["topic_id"] = doc.id
            results.append(data)
        return results

    def _count_topics_for_date_sync(self, date_key: str) -> int:
        docs = self._collection("bot_topics").where("date_key", "==", date_key).stream()
        return sum(1 for _ in docs)

    def _has_topic_for_channel_date_sync(self, channel_id: str, date_key: str) -> bool:
        docs = self._collection("bot_topics").where("date_key", "==", date_key).stream()
        for doc in docs:
            data = doc.to_dict() or {}
            if str(data.get("channel_id", "")) == str(channel_id):
                return True
        return False

    def _has_topic_for_channel_hour_sync(self, channel_id: str, hour_key: str) -> bool:
        docs = self._collection("bot_topics").where("hour_key", "==", hour_key).stream()
        for doc in docs:
            data = doc.to_dict() or {}
            if str(data.get("channel_id", "")) == str(channel_id):
                return True
        return False

    def _list_inactive_members_sync(self, threshold_days: int) -> list[dict[str, object]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
        results: list[dict[str, object]] = []
        collection_ref = self._collection("members")

        try:
            docs = collection_ref.where("context.last_active_at", "<=", cutoff).stream()
            for doc in docs:
                data = doc.to_dict() or {}
                if not isinstance(data, dict):
                    continue
                data["discord_user_id"] = doc.id
                results.append(data)
            return results
        except Exception:
            logger.exception("Inactive query failed; fallback to full scan.")

        docs = collection_ref.stream()
        for doc in docs:
            data = doc.to_dict() or {}
            if not isinstance(data, dict):
                continue
            context = data.get("context", {})
            if not isinstance(context, dict):
                continue
            last_active_at = context.get("last_active_at")
            if isinstance(last_active_at, datetime):
                if last_active_at.tzinfo is None:
                    last_active_at = last_active_at.replace(tzinfo=timezone.utc)
                if last_active_at <= cutoff:
                    data["discord_user_id"] = doc.id
                    results.append(data)
        return results

    def _update_member_outreach_sync(self, member_id: str, payload: dict[str, object]) -> None:
        doc_ref = self._collection("members").document(member_id)
        snapshot = doc_ref.get()
        base = snapshot.to_dict() if snapshot.exists else {}
        if not isinstance(base, dict):
            base = {}
        outreach = base.get("outreach", {})
        if not isinstance(outreach, dict):
            outreach = {}

        increment = int(payload.get("outreach_count_increment", 0) or 0)
        current_count = int(outreach.get("outreach_count", 0) or 0)
        new_count = current_count + increment

        update_payload = {
            "outreach": {
                "last_outreach_at": payload.get("last_outreach_at"),
                "outreach_count": new_count,
            },
            "updated_at": datetime.now(timezone.utc),
        }
        doc_ref.set(update_payload, merge=True)

    def _update_member_intervention_preference_sync(
        self,
        member_id: str,
        preferences: dict[str, object],
    ) -> None:
        doc_ref = self._collection("members").document(member_id)
        doc_ref.set(
            {
                "intervention_preferences": preferences,
                "updated_at": datetime.now(timezone.utc),
            },
            merge=True,
        )
