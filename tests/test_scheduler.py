import unittest
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from services.scheduler import SchedulerService, _is_quiet_hours


class SchedulerServiceTest(unittest.TestCase):
    def test_is_quiet_hours_wraparound(self) -> None:
        tz = ZoneInfo("Asia/Tokyo")
        at_midnight = datetime(2026, 2, 13, 0, 0, tzinfo=tz)
        at_noon = datetime(2026, 2, 13, 12, 0, tzinfo=tz)
        self.assertTrue(_is_quiet_hours(at_midnight, 23, 7))
        self.assertFalse(_is_quiet_hours(at_noon, 23, 7))

    def test_next_topic_run(self) -> None:
        scheduler = SchedulerService()
        scheduler.bot = SimpleNamespace(
            settings=SimpleNamespace(
                topic_weekdays="MON,TUE,WED,THU,FRI",
                topic_hour=9,
                topic_minute=0,
                inactive_check_weekday="MON",
                inactive_check_hour=10,
            )
        )
        tz = ZoneInfo("Asia/Tokyo")
        now_local = datetime(2026, 2, 13, 8, 0, tzinfo=tz)  # Friday
        next_run = scheduler._next_topic_run(now_local)
        self.assertEqual(next_run.hour, 9)
        self.assertEqual(next_run.minute, 0)
        self.assertEqual(next_run.date(), now_local.date())

    def test_next_inactive_run(self) -> None:
        scheduler = SchedulerService()
        scheduler.bot = SimpleNamespace(
            settings=SimpleNamespace(
                topic_weekdays="MON,TUE,WED,THU,FRI",
                topic_hour=9,
                topic_minute=0,
                inactive_check_weekday="MON",
                inactive_check_hour=10,
            )
        )
        tz = ZoneInfo("Asia/Tokyo")
        now_local = datetime(2026, 2, 13, 8, 0, tzinfo=tz)  # Friday
        next_run = scheduler._next_inactive_run(now_local)
        self.assertEqual(next_run.strftime("%a").upper()[:3], "MON")
        self.assertEqual(next_run.hour, 10)


if __name__ == "__main__":
    unittest.main()
