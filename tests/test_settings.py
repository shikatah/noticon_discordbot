import os
import unittest
from unittest.mock import patch

from config.settings import get_settings


class SettingsTest(unittest.TestCase):
    def test_phase5_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DISCORD_TOKEN": "dummy",
            },
            clear=True,
        ):
            settings = get_settings()

        self.assertTrue(settings.bot_enabled_default)
        self.assertEqual(settings.bot_timezone, "Asia/Tokyo")
        self.assertEqual(settings.topic_hour, 9)
        self.assertEqual(settings.topic_minute, 0)
        self.assertEqual(settings.inactive_threshold_days, 14)
        self.assertTrue(settings.inactive_dm_dry_run)

    def test_phase5_override_values(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DISCORD_TOKEN": "dummy",
                "BOT_ENABLED_DEFAULT": "false",
                "WELCOME_CHANNEL_ID": "100",
                "TOPIC_CHANNEL_ID": "200",
                "BOT_TIMEZONE": "UTC",
                "TOPIC_WEEKDAYS": "MON,WED",
                "TOPIC_HOUR": "8",
                "TOPIC_MINUTE": "30",
                "INACTIVE_THRESHOLD_DAYS": "21",
                "INACTIVE_CHECK_WEEKDAY": "FRI",
                "INACTIVE_CHECK_HOUR": "11",
                "INACTIVE_DM_DRY_RUN": "false",
            },
            clear=True,
        ):
            settings = get_settings()

        self.assertFalse(settings.bot_enabled_default)
        self.assertEqual(settings.welcome_channel_id, 100)
        self.assertEqual(settings.topic_channel_id, 200)
        self.assertEqual(settings.bot_timezone, "UTC")
        self.assertEqual(settings.topic_weekdays, "MON,WED")
        self.assertEqual(settings.topic_hour, 8)
        self.assertEqual(settings.topic_minute, 30)
        self.assertEqual(settings.inactive_threshold_days, 21)
        self.assertEqual(settings.inactive_check_weekday, "FRI")
        self.assertEqual(settings.inactive_check_hour, 11)
        self.assertFalse(settings.inactive_dm_dry_run)


if __name__ == "__main__":
    unittest.main()
