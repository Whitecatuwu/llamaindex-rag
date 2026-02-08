import unittest

from src.classification.domain.incremental_policy import (
    PageFingerprint,
    StateFingerprint,
    evaluate_incremental_decision,
)


class IncrementalPolicyTests(unittest.TestCase):
    def test_state_miss(self):
        decision = evaluate_incremental_decision(
            existing=None,
            current=PageFingerprint("html", 1, "h1", "1.0.0"),
        )
        self.assertTrue(decision.should_classify)
        self.assertEqual(decision.reason, "state_miss")

    def test_strategy_changed(self):
        decision = evaluate_incremental_decision(
            existing=StateFingerprint("html", 1, "h1", "1.0.0"),
            current=PageFingerprint("html", 1, "h1", "2.0.0"),
        )
        self.assertTrue(decision.should_classify)
        self.assertEqual(decision.reason, "strategy_version_changed")

    def test_revid_and_hash_hit(self):
        decision = evaluate_incremental_decision(
            existing=StateFingerprint("html", 10, "same", "1.0.0"),
            current=PageFingerprint("html", 10, "same", "1.0.0"),
        )
        self.assertFalse(decision.should_classify)
        self.assertEqual(decision.reason, "revid_and_hash_hit")

    def test_same_revid_but_hash_changed(self):
        decision = evaluate_incremental_decision(
            existing=StateFingerprint("html", 10, "old", "1.0.0"),
            current=PageFingerprint("html", 10, "new", "1.0.0"),
        )
        self.assertTrue(decision.should_classify)
        self.assertEqual(decision.reason, "content_hash_changed_same_revid")

    def test_hash_only_mode_hit(self):
        decision = evaluate_incremental_decision(
            existing=StateFingerprint("html", None, "same", "1.0.0"),
            current=PageFingerprint("html", None, "same", "1.0.0"),
        )
        self.assertFalse(decision.should_classify)
        self.assertEqual(decision.reason, "content_hash_hit")

    def test_hash_only_mode_changed(self):
        decision = evaluate_incremental_decision(
            existing=StateFingerprint("html", None, "old", "1.0.0"),
            current=PageFingerprint("html", None, "new", "1.0.0"),
        )
        self.assertTrue(decision.should_classify)
        self.assertEqual(decision.reason, "content_hash_changed")
