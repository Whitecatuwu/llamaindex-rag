import unittest

from src.classification.domain.classifier import RuleBasedClassifier
from src.classification.domain.entities import WikiPage


def _page(title: str, categories: tuple[str, ...], content: str = "") -> WikiPage:
    return WikiPage(
        pageid=1,
        title=title,
        revid=100,
        timestamp="2025-01-01T00:00:00Z",
        canonical_url="https://example.com",
        categories=categories,
        content=content,
        is_redirect=False,
    )


class RuleClassifierTests(unittest.TestCase):
    def test_cat_rule_match(self):
        result = RuleBasedClassifier().classify(_page("Cat A", ("Category:Cat Units",)))
        self.assertEqual(result.entity_type, "cat")

    def test_enemy_rule_match(self):
        result = RuleBasedClassifier().classify(_page("Enemy A", ("Category:Enemy Units",)))
        self.assertEqual(result.entity_type, "enemy")

    def test_stage_rule_match(self):
        result = RuleBasedClassifier().classify(_page("Stage A", ("Category:Event Stages",)))
        self.assertEqual(result.entity_type, "stage")

    def test_update_rule_match(self):
        result = RuleBasedClassifier().classify(_page("Version 13.7 Update", ("Category:Versions",)))
        self.assertEqual(result.entity_type, "update")

    def test_conflict_tie_break_to_misc(self):
        page = _page("Ambiguous", ("Category:Cat Units", "Category:Enemy Units"))
        result = RuleBasedClassifier(low_margin_threshold=0.9).classify(page)
        self.assertEqual(result.entity_type, "misc")
        self.assertTrue(any("low_margin_conflict" in reason for reason in result.reasons))

    def test_priority_prefers_update_on_equal_score(self):
        page = _page("Mixed Signals", ("Category:Versions", "Category:Cat Units"))
        result = RuleBasedClassifier(low_margin_threshold=0.0).classify(page)
        self.assertEqual(result.entity_type, "update")
