import logging
from datetime import datetime, timezone

import discord

from models.message import MessageRecord

logger = logging.getLogger(__name__)


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

        bot.runtime["messages_seen"] = int(bot.runtime["messages_seen"]) + 1
        bot.runtime["last_message_at"] = datetime.now(timezone.utc)

        record = MessageRecord.from_discord(message)
        await bot.firestore.save_message(record)

        logger.info(
            "[#%s] %s: %s",
            getattr(message.channel, "name", "unknown"),
            getattr(message.author, "display_name", message.author.name),
            message.content[:80],
        )

    @bot.event
    async def on_member_join(member: discord.Member) -> None:
        logger.info("Member joined: %s (%s)", member.display_name, member.id)
