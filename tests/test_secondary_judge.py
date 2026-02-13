import unittest
from types import SimpleNamespace

from models.decision import SecondaryDecision
from services.secondary_judge import SecondaryJudgeService


class SecondaryJudgeServiceTest(unittest.TestCase):
    def test_sanitize_limits_questions_and_adds_context_quote(self) -> None:
        fake_claude = SimpleNamespace(enabled=False, model_name="fake")
        service = SecondaryJudgeService(claude=fake_claude)
        decision = SecondaryDecision(
            intervention_type="clarify",
            tone="helpful",
            content="まずはこれを試してください？ その後どうですか？",
            mention_users=[],
            reaction_emoji=None,
            confidence=0.8,
            silence_confidence=0.2,
            quality_score=0.5,
            reasoning="test",
            model="fake",
        )
        result = service._sanitize_output(
            {"message_content": "リレーションがうまく動きません"},
            decision,
        )
        self.assertIn("「", result.content)
        question_count = result.content.count("?") + result.content.count("？")
        self.assertLessEqual(question_count, 1)

    def test_detect_ng_pattern(self) -> None:
        fake_claude = SimpleNamespace(enabled=False, model_name="fake")
        service = SecondaryJudgeService(claude=fake_claude)
        self.assertTrue(service._contains_ng_pattern("こうするべきです。"))
        self.assertFalse(service._contains_ng_pattern("こうすると試しやすいです。"))


if __name__ == "__main__":
    unittest.main()
