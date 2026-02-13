from dataclasses import dataclass
from datetime import datetime, timezone

import discord


@dataclass(slots=True)
class MessageRecord:
    message_id: str
    channel_id: str
    channel_name: str
    author_id: str
    author_name: str
    content: str
    timestamp: datetime
    is_reply: bool
    reply_to_id: str | None
    reply_count: int
    reactions: dict[str, int]
    bot_action: str | None = None
    bot_action_at: datetime | None = None

    @classmethod
    def from_discord(cls, message: discord.Message) -> "MessageRecord":
        reply_to_id = None
        if message.reference and message.reference.message_id:
            reply_to_id = str(message.reference.message_id)

        reactions: dict[str, int] = {}
        for reaction in message.reactions:
            reactions[str(reaction.emoji)] = reaction.count

        author_name = getattr(message.author, "display_name", message.author.name)
        channel_name = getattr(message.channel, "name", str(message.channel))

        created_at = message.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        return cls(
            message_id=str(message.id),
            channel_id=str(message.channel.id),
            channel_name=channel_name,
            author_id=str(message.author.id),
            author_name=author_name,
            content=message.content,
            timestamp=created_at,
            is_reply=reply_to_id is not None,
            reply_to_id=reply_to_id,
            reply_count=0,
            reactions=reactions,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "content": self.content,
            "timestamp": self.timestamp,
            "is_reply": self.is_reply,
            "reply_to_id": self.reply_to_id,
            "reply_count": self.reply_count,
            "reactions": self.reactions,
            "bot_action": self.bot_action,
            "bot_action_at": self.bot_action_at,
        }
