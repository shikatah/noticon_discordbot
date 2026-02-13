import logging
from datetime import datetime, timedelta, timezone

import discord

from models.message import MessageRecord

logger = logging.getLogger(__name__)


def _infer_channel_type(channel_name: str) -> str:
    lowered = channel_name.lower()
    if "question" in lowered or "質問" in channel_name:
        return "question"
    if "share" in lowered or "共有" in channel_name:
        return "share"
    if "intro" in lowered or "自己紹介" in channel_name:
        return "intro"
    if "announce" in lowered or "告知" in channel_name:
        return "announce"
    return "chat"


def _is_quiet_hours(now: datetime, quiet_start: int, quiet_end: int) -> bool:
    hour = now.hour
    if quiet_start == quiet_end:
        return True
    if quiet_start < quiet_end:
        return quiet_start <= hour < quiet_end
    return hour >= quiet_start or hour < quiet_end


def _recent_channel_activity_count(bot: discord.Client, channel_id: str, now: datetime) -> int:
    activity = bot.runtime.setdefault("channel_activity", {})
    timestamps = activity.setdefault(channel_id, [])

    now_ts = now.timestamp()
    one_hour_ago = now_ts - 3600
    timestamps.append(now_ts)
    while timestamps and timestamps[0] < one_hour_ago:
        timestamps.pop(0)
    return len(timestamps)


def register_event_handlers(bot: discord.Client) -> None:
    @bot.event
    async def on_ready() -> None:
        if bot.user is None:
            return
        logger.info("Logged in as %s (%s)", bot.user, bot.user.id)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        now = datetime.now(timezone.utc)
        bot.runtime["messages_seen"] = int(bot.runtime["messages_seen"]) + 1
        bot.runtime["last_message_at"] = now

        record = MessageRecord.from_discord(message)
        await bot.firestore.save_message(record)

        channel_name = getattr(message.channel, "name", "unknown")
        channel_type = _infer_channel_type(channel_name)

        joined_at = getattr(message.author, "joined_at", None)
        author_is_new = False
        if isinstance(joined_at, datetime):
            if joined_at.tzinfo is None:
                joined_at = joined_at.replace(tzinfo=timezone.utc)
            author_is_new = (now - joined_at) <= timedelta(days=7)

        recent_activity = _recent_channel_activity_count(bot, str(message.channel.id), now)
        in_quiet_hours = _is_quiet_hours(
            now.astimezone(),
            bot.settings.bot_quiet_hours_start,
            bot.settings.bot_quiet_hours_end,
        )

        primary_input = {
            "message_content": message.content,
            "channel_type": channel_type,
            "hours_since_post": 0.0,
            "has_reply": False,
            "has_reaction": len(message.reactions) > 0,
            "is_bot_mentioned": bool(bot.user and bot.user in message.mentions),
            "author_is_new": author_is_new,
            "recent_channel_activity": recent_activity,
            "in_quiet_hours": in_quiet_hours,
        }

        decision = await bot.primary_judge.judge(primary_input)
        await bot.firestore.save_primary_decision(record.message_id, primary_input, decision)
        if decision.needs_intervention:
            bot.runtime["primary_needs_intervention_count"] = int(
                bot.runtime["primary_needs_intervention_count"]
            ) + 1

        logger.info(
            "[#%s] %s: %s",
            channel_name,
            getattr(message.author, "display_name", message.author.name),
            message.content[:80],
        )
        logger.info(
            "PrimaryJudge => needs_intervention=%s priority=%s reason=%s",
            decision.needs_intervention,
            decision.priority,
            decision.reason,
        )

    @bot.event
    async def on_member_join(member: discord.Member) -> None:
        logger.info("Member joined: %s (%s)", member.display_name, member.id)
