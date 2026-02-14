import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import discord
from discord.ext import tasks

logger = logging.getLogger(__name__)


def _is_quiet_hours(now_local: datetime, quiet_start: int, quiet_end: int) -> bool:
    hour = now_local.hour
    if quiet_start == quiet_end:
        return True
    if quiet_start < quiet_end:
        return quiet_start <= hour < quiet_end
    return hour >= quiet_start or hour < quiet_end


def _weekday_token(value: str) -> str:
    return value.strip().upper()[:3]


def _count_recent_channel_history_messages(
    channel_history: list[dict[str, object]],
    now_utc: datetime,
    within_minutes: int = 60,
) -> int:
    threshold = now_utc - timedelta(minutes=within_minutes)
    count = 0
    for item in channel_history:
        timestamp_text = item.get("timestamp")
        if not isinstance(timestamp_text, str):
            continue
        try:
            ts = datetime.fromisoformat(timestamp_text)
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= threshold:
            count += 1
    return count


class SchedulerService:
    def __init__(self) -> None:
        self.bot: discord.Client | None = None
        self.timezone = ZoneInfo("Asia/Tokyo")
        self._warned_missing_topic_channel = False

    async def start(self, bot: discord.Client) -> None:
        self.bot = bot
        self.timezone = ZoneInfo(bot.settings.bot_timezone)
        if not self.topic_tick_loop.is_running():
            self.topic_tick_loop.start()
        if not self.inactive_tick_loop.is_running():
            self.inactive_tick_loop.start()
        bot.runtime["scheduler_running"] = True
        logger.info("Scheduler started.")

    async def stop(self) -> None:
        if self.topic_tick_loop.is_running():
            self.topic_tick_loop.cancel()
        if self.inactive_tick_loop.is_running():
            self.inactive_tick_loop.cancel()
        if self.bot is not None:
            self.bot.runtime["scheduler_running"] = False
        logger.info("Scheduler stopped.")

    @tasks.loop(minutes=1)
    async def topic_tick_loop(self) -> None:
        assert self.bot is not None
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(self.timezone)
        self.bot.runtime["scheduler_last_tick"] = now_utc
        self.bot.runtime["scheduler_next_topic_at"] = self._next_topic_run(now_local).isoformat()

        if not self.bot.runtime.get("bot_enabled", True):
            return
        channel_ids = self._topic_channel_ids()
        if not channel_ids:
            if not self._warned_missing_topic_channel:
                logger.warning(
                    "TOPIC_CHANNEL_ID(S) is not set. Topic scheduler is skipped."
                )
                self._warned_missing_topic_channel = True
            return
        if _is_quiet_hours(
            now_local, self.bot.settings.bot_quiet_hours_start, self.bot.settings.bot_quiet_hours_end
        ):
            return

        if not self._should_run_atmosphere_check(now_local):
            return

        date_key = now_local.date().isoformat()
        hour_key = self._hour_key(now_local)
        daily_count = await self.bot.firestore.count_topics_for_date(date_key)
        recent_topics_data = await self.bot.firestore.list_recent_topics(limit=10)
        recent_topics = [str(item.get("content", "")) for item in recent_topics_data]
        for channel_id in channel_ids:
            if daily_count >= self.bot.settings.bot_daily_topic_limit:
                logger.info("Daily topic limit reached: %s", daily_count)
                break

            channel_key = str(channel_id)
            last_hour_key = self.bot.runtime.setdefault(
                "atmosphere_last_run_key_by_channel", {}
            ).get(channel_key)
            if last_hour_key == hour_key:
                continue
            if await self.bot.firestore.has_topic_for_channel_hour(channel_key, hour_key):
                self.bot.runtime["atmosphere_last_run_key_by_channel"][channel_key] = hour_key
                continue

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    logger.exception("Failed to resolve topic channel: %s", channel_id)
                    continue
            if not isinstance(channel, discord.TextChannel):
                logger.warning("Configured topic channel is not a text channel: %s", channel_id)
                continue

            channel_history = self.bot.runtime.get("channel_history", {}).get(channel_key, [])
            recent_activity = _count_recent_channel_history_messages(
                channel_history,
                now_utc,
                within_minutes=60,
            )
            history_texts = [str(item.get("content", "")) for item in channel_history[-10:]]
            channel_summary = " / ".join(history_texts)[:500]

            # If members are actively chatting in the last hour, observe only.
            if recent_activity >= 8:
                self.bot.runtime["atmosphere_last_run_key_by_channel"][channel_key] = hour_key
                await self.bot.firestore.save_bot_action(
                    action_id=f"atmosphere-observe-{uuid4().hex[:8]}",
                    payload={
                        "type": "atmosphere_check",
                        "channel_id": channel_key,
                        "target_message_id": None,
                        "content": "",
                        "reasoning": "active_conversation_observe_only",
                        "confidence": 1.0,
                        "timestamp": now_utc,
                        "model": "scheduler",
                        "outcome": {
                            "status": "observed_no_action",
                            "action_ref": hour_key,
                        },
                    },
                )
                continue

            try:
                content, topic_type = await self.bot.topic_generator.generate_topic(
                    recent_topics=recent_topics,
                    channel_type="chat",
                    recent_channel_summary=channel_summary,
                )
                sent = await channel.send(content)
                topic_id = str(sent.id)
                await self.bot.firestore.save_topic_post(
                    topic_id=topic_id,
                    payload={
                        "channel_id": channel_key,
                        "content": content,
                        "topic_type": topic_type,
                        "timestamp": now_utc,
                        "date_key": date_key,
                        "hour_key": hour_key,
                        "recent_activity_count": recent_activity,
                        "engagement": {
                            "reply_count": 0,
                            "reactions": {},
                        },
                    },
                )
                await self.bot.firestore.save_bot_action(
                    action_id=f"{topic_id}-{uuid4().hex[:8]}",
                    payload={
                        "type": "topic_post",
                        "channel_id": channel_key,
                        "target_message_id": topic_id,
                        "content": content,
                        "reasoning": "scheduled_topic_post",
                        "confidence": 1.0,
                        "timestamp": now_utc,
                        "model": "scheduler",
                        "outcome": {
                            "status": "posted",
                            "action_ref": topic_id,
                        },
                    },
                )
                self.bot.runtime["topic_last_posted_date_by_channel"][channel_key] = date_key
                self.bot.runtime["atmosphere_last_run_key_by_channel"][channel_key] = hour_key
                self.bot.runtime["last_action_at"] = now_utc
                daily_count += 1
                logger.info("Scheduled topic posted to channel %s", channel_key)
            except Exception:
                logger.exception("Scheduled topic post failed.")
                await self.bot.firestore.save_bot_action(
                    action_id=f"topic-failed-{uuid4().hex[:8]}",
                    payload={
                        "type": "topic_post",
                        "channel_id": channel_key,
                        "target_message_id": None,
                        "content": "",
                        "reasoning": "topic_post_failed",
                        "confidence": 0.0,
                        "timestamp": now_utc,
                        "model": "scheduler",
                        "outcome": {
                            "status": "failed",
                            "action_ref": None,
                        },
                    },
                )

    @topic_tick_loop.before_loop
    async def _wait_until_ready_for_topic(self) -> None:
        assert self.bot is not None
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def inactive_tick_loop(self) -> None:
        assert self.bot is not None
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(self.timezone)
        self.bot.runtime["scheduler_next_inactive_at"] = self._next_inactive_run(now_local).isoformat()

        if not self.bot.runtime.get("bot_enabled", True):
            return

        weekday = _weekday_token(now_local.strftime("%a"))
        if weekday != _weekday_token(self.bot.settings.inactive_check_weekday):
            return
        if now_local.hour != self.bot.settings.inactive_check_hour:
            return

        run_key = now_local.date().isoformat()
        if self.bot.runtime.get("inactive_last_run_key") == run_key:
            return

        members = await self.bot.firestore.list_inactive_members(
            threshold_days=self.bot.settings.inactive_threshold_days
        )
        if not members:
            self.bot.runtime["inactive_last_run_key"] = run_key
            return

        recent_topics_data = await self.bot.firestore.list_recent_topics(limit=5)
        recent_summary = " / ".join(
            str(item.get("content", "")) for item in recent_topics_data if item.get("content")
        )[:500]
        guild = self._resolve_guild()
        if guild is None:
            logger.warning("Guild not found for inactive outreach.")
            return

        for member_doc in members:
            member_id = str(member_doc.get("discord_user_id", "")).strip()
            if not member_id:
                continue
            if not await self._is_member_active_in_guild(guild, member_id):
                continue
            if self._was_outreached_recently(member_doc, now_utc):
                continue

            member_name = str(member_doc.get("display_name", f"user-{member_id}"))
            interests = (
                member_doc.get("interests", {}).get("topics", [])
                if isinstance(member_doc.get("interests"), dict)
                else []
            )
            if not isinstance(interests, list):
                interests = []
            dm_text = await self.bot.outreach.generate_dm(
                member_name=member_name,
                interest_topics=[str(item) for item in interests],
                recent_topics_summary=recent_summary or "Notion活用",
            )

            dry_run = self.bot.settings.inactive_dm_dry_run
            status = "dry_run"
            action_type = "outreach_dry_run"
            send_error: str | None = None

            if not dry_run:
                try:
                    member = guild.get_member(int(member_id))
                    if member is None:
                        member = await guild.fetch_member(int(member_id))
                    await member.send(dm_text)
                    status = "sent"
                    action_type = "outreach_dm"
                    await self.bot.firestore.update_member_outreach(
                        member_id=member_id,
                        payload={
                            "last_outreach_at": now_utc,
                            "outreach_count_increment": 1,
                        },
                    )
                except discord.Forbidden:
                    status = "cannot_dm"
                    action_type = "outreach_failed"
                    send_error = "cannot_dm"
                except Exception:
                    status = "failed"
                    action_type = "outreach_failed"
                    send_error = "send_failed"

            log_id = f"{run_key}-{member_id}"
            await self.bot.firestore.save_outreach_log(
                log_id=log_id,
                payload={
                    "member_id": member_id,
                    "member_name": member_name,
                    "status": status,
                    "content": dm_text,
                    "timestamp": now_utc,
                    "dry_run": dry_run,
                    "error": send_error,
                },
            )
            await self.bot.firestore.save_bot_action(
                action_id=f"{log_id}-{uuid4().hex[:8]}",
                payload={
                    "type": action_type,
                    "channel_id": "dm",
                    "target_message_id": None,
                    "content": dm_text,
                    "reasoning": "inactive_outreach",
                    "confidence": 1.0 if status in {"dry_run", "sent"} else 0.0,
                    "timestamp": now_utc,
                    "model": "scheduler",
                    "outcome": {
                        "status": status,
                        "action_ref": member_id,
                    },
                },
            )
        self.bot.runtime["inactive_last_run_key"] = run_key

    @inactive_tick_loop.before_loop
    async def _wait_until_ready_for_inactive(self) -> None:
        assert self.bot is not None
        await self.bot.wait_until_ready()

    def _resolve_guild(self) -> discord.Guild | None:
        assert self.bot is not None
        if self.bot.settings.discord_guild_id is not None:
            guild = self.bot.get_guild(self.bot.settings.discord_guild_id)
            if guild is not None:
                return guild
        if self.bot.guilds:
            return self.bot.guilds[0]
        return None

    async def _is_member_active_in_guild(self, guild: discord.Guild, member_id: str) -> bool:
        try:
            member = guild.get_member(int(member_id))
            if member is not None:
                return True
            await guild.fetch_member(int(member_id))
            return True
        except Exception:
            return False

    def _was_outreached_recently(self, member_doc: dict[str, object], now_utc: datetime) -> bool:
        outreach = member_doc.get("outreach", {})
        if not isinstance(outreach, dict):
            return False
        last_outreach_at = outreach.get("last_outreach_at")
        if not isinstance(last_outreach_at, datetime):
            return False
        if last_outreach_at.tzinfo is None:
            last_outreach_at = last_outreach_at.replace(tzinfo=timezone.utc)
        return (now_utc - last_outreach_at) < timedelta(days=30)

    def _next_topic_run(self, now_local: datetime) -> datetime:
        interval = max(1, int(self.bot.settings.atmosphere_check_interval_hours))  # type: ignore[union-attr]
        candidate = now_local.replace(minute=0, second=0, microsecond=0)
        if now_local.minute > 0 or now_local.second > 0 or now_local.microsecond > 0:
            candidate = candidate + timedelta(hours=1)

        for _ in range(0, 24 * 8):
            if self._should_run_atmosphere_check(candidate):
                return candidate
            candidate = candidate + timedelta(hours=interval)
        return (now_local + timedelta(days=1)).replace(second=0, microsecond=0)

    def _next_inactive_run(self, now_local: datetime) -> datetime:
        target_weekday = _weekday_token(self.bot.settings.inactive_check_weekday)  # type: ignore[union-attr]
        target_hour = self.bot.settings.inactive_check_hour  # type: ignore[union-attr]
        for day_offset in range(0, 8):
            candidate = (now_local + timedelta(days=day_offset)).replace(
                hour=target_hour,
                minute=0,
                second=0,
                microsecond=0,
            )
            weekday = _weekday_token(candidate.strftime("%a"))
            if weekday != target_weekday:
                continue
            if candidate <= now_local:
                continue
            return candidate
        return (now_local + timedelta(days=1)).replace(second=0, microsecond=0)

    def _should_run_atmosphere_check(self, now_local: datetime) -> bool:
        weekdays = {
            _weekday_token(token)
            for token in self.bot.settings.topic_weekdays.split(",")  # type: ignore[union-attr]
            if token.strip()
        }
        if not weekdays:
            weekdays = {"MON", "TUE", "WED", "THU", "FRI"}
        weekday = _weekday_token(now_local.strftime("%a"))
        if weekday not in weekdays:
            return False

        start_hour = int(self.bot.settings.atmosphere_check_start_hour)  # type: ignore[union-attr]
        end_hour = int(self.bot.settings.atmosphere_check_end_hour)  # type: ignore[union-attr]
        interval = max(1, int(self.bot.settings.atmosphere_check_interval_hours))  # type: ignore[union-attr]

        if not (start_hour <= now_local.hour <= end_hour):
            return False
        if now_local.minute != 0:
            return False
        return ((now_local.hour - start_hour) % interval) == 0

    def _hour_key(self, now_local: datetime) -> str:
        return now_local.strftime("%Y-%m-%d-%H")

    def _topic_channel_ids(self) -> list[int]:
        raw_ids = list(getattr(self.bot.settings, "topic_channel_ids", []))  # type: ignore[union-attr]
        if not raw_ids:
            fallback_id = getattr(self.bot.settings, "topic_channel_id", None)  # type: ignore[union-attr]
            if isinstance(fallback_id, int):
                raw_ids = [fallback_id]
        deduped: list[int] = []
        seen: set[int] = set()
        for channel_id in raw_ids:
            if not isinstance(channel_id, int):
                continue
            if channel_id in seen:
                continue
            seen.add(channel_id)
            deduped.append(channel_id)
        return deduped
