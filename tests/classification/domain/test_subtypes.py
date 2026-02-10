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

    def test_update_subtypes_collect_multiple_version_tags_from_content(self):
        page = _page(
            "Version 13.0 Update",
            ("Category:Versions",),
            content="Version 13.0 patch notes. Version 13.1 balance changes.",
        )
        result = RuleBasedClassifier().classify(page)
        self.assertEqual(result.entity_type, "update")
        self.assertIn("version_line:13.0", result.subtypes)
        self.assertIn("version_line:13.1", result.subtypes)
        self.assertEqual(tuple(sorted(result.subtypes)), result.subtypes)

    def test_enemy_trait_pattern_does_not_swallow_campaign_categories(self):
        page = _page(
            "Enemy A",
            ("Category:Enemy Units", "Category:Empire of Cats Enemies"),
        )
        result = RuleBasedClassifier().classify(page)
        self.assertEqual(result.entity_type, "enemy")
        self.assertIn("campaign_scope:eoc", result.subtypes)
        self.assertNotIn("trait:empire_of_cats", result.subtypes)

    def test_stage_family_pattern_skips_specific_progression_categories(self):
        page = _page(
            "Stage A",
            ("Category:Zero Legends Stages", "Category:Sub-chapter 106 Stages"),
        )
        result = RuleBasedClassifier().classify(page)
        self.assertEqual(result.entity_type, "stage")
        self.assertIn("progression:zl", result.subtypes)
        self.assertIn("progression:subchapter_106", result.subtypes)
        self.assertNotIn("stage_family:zero_legends", result.subtypes)
