import logging
from datetime import datetime, timezone
from typing import Any

import discord
from discord.ext import commands

from bot.commands import register_commands
from bot.events import register_event_handlers
from config.settings import Settings
from services.firestore import FirestoreService
from services.member_profile import MemberProfileService
from services.outreach import OutreachService
from services.primary_judge import PrimaryJudgeService
from services.scheduler import SchedulerService
from services.secondary_judge import SecondaryJudgeService
from services.topic_generator import TopicGeneratorService
from services.welcome import WelcomeService

logger = logging.getLogger(__name__)


class CommunityBot(commands.Bot):
    def __init__(
        self,
        settings: Settings,
        firestore: FirestoreService,
        primary_judge: PrimaryJudgeService,
        secondary_judge: SecondaryJudgeService,
        member_profile: MemberProfileService,
        welcome: WelcomeService,
        topic_generator: TopicGeneratorService,
        outreach: OutreachService,
        scheduler: SchedulerService,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.firestore = firestore
        self.primary_judge = primary_judge
        self.secondary_judge = secondary_judge
        self.member_profile = member_profile
        self.welcome = welcome
        self.topic_generator = topic_generator
        self.outreach = outreach
        self.scheduler = scheduler
        self.runtime: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc),
            "day_key": datetime.now(timezone.utc).date().isoformat(),
            "bot_enabled": settings.bot_enabled_default,
            "messages_seen": 0,
            "interventions_today": 0,
            "primary_needs_intervention_count": 0,
            "member_profiles_updated": 0,
            "last_message_at": None,
            "last_action_at": None,
            "channel_activity": {},
            "channel_history": {},
            "member_stats": {},
            "bot_recent_actions": [],
            "topic_last_posted_date_by_channel": {},
            "scheduler_last_tick": None,
            "scheduler_running": False,
            "scheduler_next_topic_at": None,
            "scheduler_next_inactive_at": None,
            "inactive_last_run_key": None,
        }

    async def setup_hook(self) -> None:
        loaded_config = await self.firestore.load_config()
        if loaded_config:
            bot_enabled = loaded_config.get("bot_enabled")
            if isinstance(bot_enabled, bool):
                self.runtime["bot_enabled"] = bot_enabled
            logger.info("Loaded bot config from Firestore.")

        register_event_handlers(self)
        register_commands(self)
        await self.scheduler.start(self)

        if self.settings.discord_guild_id is not None:
            guild = discord.Object(id=self.settings.discord_guild_id)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} command(s) to guild {guild.id}")
            return

        synced = await self.tree.sync()
        print(f"Synced {len(synced)} global command(s)")

    async def close(self) -> None:
        await self.scheduler.stop()
        await super().close()
