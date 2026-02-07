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
        source_path="memory://page",
    )


class SubtypeMappingTests(unittest.TestCase):
    def test_cat_subtypes_are_multivalued(self):
        page = _page(
            "Cat A",
            ("Category:Cat Units", "Category:Uber Rare Cats", "Category:Anti-Red Cats", "Category:Area Attack Cats"),
        )
        result = RuleBasedClassifier().classify(page)
        self.assertEqual(result.entity_type, "cat")
        self.assertIn("rarity:uber_rare", result.subtypes)
        self.assertIn("target_trait:red", result.subtypes)
        self.assertIn("attack_type:area", result.subtypes)

    def test_stage_subtypes(self):
        page = _page(
            "Some Stage",
            ("Category:Event Stages", "Category:Timed Score Stages"),
        )
        result = RuleBasedClassifier().classify(page)
        self.assertEqual(result.entity_type, "stage")
        self.assertIn("modifier:timed_score", result.subtypes)
