from collections import defaultdict
from re import Pattern

from src.classification.domain.entities import Classification, WikiPage
from src.classification.domain.rules import (
    CAT_SUBTYPE_PATTERNS,
    CLASSIFICATION_STRATEGY_VERSION,
    ENEMY_SUBTYPE_PATTERNS,
    LIST_SUBTYPE_PATTERNS,
    LOW_MARGIN_THRESHOLD,
    MECHANIC_SUBTYPE_PATTERNS,
    PRIMARY_RULES,
    STAGE_SUBTYPE_PATTERNS,
    UPDATE_SUBTYPE_PATTERNS,
)
from src.classification.domain.types import EntityType


class RuleBasedClassifier:
    # Deterministic tie-break priority when two entity types share the same score.
    _ENTITY_PRIORITY: dict[EntityType, int] = {
        "update": 0,
        "cat": 1,
        "enemy": 2,
        "stage": 3,
        "list": 4,
        "mechanic": 5,
        "misc": 6,
    }

    def __init__(self, low_margin_threshold: float = LOW_MARGIN_THRESHOLD):
        self.low_margin_threshold = low_margin_threshold

    def classify(self, page: WikiPage) -> Classification:
        normalized_categories = tuple(c.lower().strip() for c in page.categories)
        title = page.title or ""
        content = page.content or ""

        scores: dict[EntityType, float] = defaultdict(float)
        matched: dict[EntityType, list[str]] = defaultdict(list)

        for rule in PRIMARY_RULES:
            if self._rule_matches(rule.pattern, rule.source, normalized_categories, title, content):
                scores[rule.target] += rule.weight
                matched[rule.target].append(rule.rule_id)

        for entity in ("update", "cat", "enemy", "stage", "list", "mechanic"):
            if entity not in scores:
                scores[entity] = 0.0
        scores["misc"] = 0.0

        best, second, margin = self._top_two(scores)
        reasons: list[str] = []

        if best == "misc" or scores[best] <= 0.0:
            # No positive signal from rules -> force misc with explicit reason.
            reasons.append("no_rule_match")
            return Classification(
                entity_type="misc",
                subtypes=(),
                confidence=0.0,
                reasons=tuple(reasons),
                matched_rules=(),
                strategy_version=CLASSIFICATION_STRATEGY_VERSION,
            )

        confidence = scores[best] / max(scores[best] + scores[second], 1e-6)

        if margin < self.low_margin_threshold:
            # Low margin means ambiguous top classes; downgrade to misc for safety.
            reasons.append(f"low_margin_conflict:{best}_vs_{second}")
            return Classification(
                entity_type="misc",
                subtypes=(),
                confidence=confidence,
                reasons=tuple(reasons),
                matched_rules=tuple(sorted(set(matched.get(best, []) + matched.get(second, [])))),
                strategy_version=CLASSIFICATION_STRATEGY_VERSION,
            )

        subtypes = tuple(self._extract_subtypes(best, normalized_categories, title, content))
        return Classification(
            entity_type=best,
            subtypes=subtypes,
            confidence=confidence,
            reasons=tuple(reasons),
            matched_rules=tuple(sorted(set(matched.get(best, [])))),
            strategy_version=CLASSIFICATION_STRATEGY_VERSION,
        )

    @staticmethod
    def _rule_matches(
        pattern: Pattern[str],
        source: str,
        categories: tuple[str, ...],
        title: str,
        content: str,
    ) -> bool:
        if source == "category":
            return any(pattern.search(c) for c in categories)
        if source == "title":
            return bool(pattern.search(title))
        if source == "content":
            return bool(pattern.search(content))
        combined_text = f"{title}\n{content}\n" + "\n".join(categories)
        return bool(pattern.search(combined_text))

    @staticmethod
    def _top_two(scores: dict[EntityType, float]) -> tuple[EntityType, EntityType, float]:
        ordered = sorted(scores.items(), key=lambda item: (-item[1], RuleBasedClassifier._ENTITY_PRIORITY[item[0]]))
        best = ordered[0][0]
        second = ordered[1][0]
        margin = ordered[0][1] - ordered[1][1]
        return best, second, margin

    def _extract_subtypes(
        self,
        entity_type: EntityType,
        categories: tuple[str, ...],
        title: str,
        content: str,
    ) -> list[str]:
        tags: set[str] = set()

        category_patterns: tuple[tuple[Pattern[str], str], ...] = ()
        combined_patterns: tuple[tuple[Pattern[str], str], ...] = ()
        if entity_type == "cat":
            category_patterns = CAT_SUBTYPE_PATTERNS
        elif entity_type == "enemy":
            category_patterns = ENEMY_SUBTYPE_PATTERNS
        elif entity_type == "stage":
            category_patterns = STAGE_SUBTYPE_PATTERNS
        elif entity_type == "update":
            combined_patterns = UPDATE_SUBTYPE_PATTERNS
        elif entity_type == "mechanic":
            combined_patterns = MECHANIC_SUBTYPE_PATTERNS
        elif entity_type == "list":
            combined_patterns = LIST_SUBTYPE_PATTERNS

        for category in categories:
            tags.update(self._extract_from_patterns(category, category_patterns))

        combined_text = f"{title}\n{content}"
        tags.update(self._extract_from_patterns(combined_text, combined_patterns))
        return sorted(tags)

    @staticmethod
    def _extract_from_patterns(text: str, patterns: tuple[tuple[Pattern[str], str], ...]) -> set[str]:
        tags: set[str] = set()
        for pattern, template in patterns:
            match = pattern.search(text)
            if not match:
                continue
            tag = template
            for idx, value in enumerate(match.groups(), start=1):
                tag = tag.replace(f"{{group{idx}}}", RuleBasedClassifier._slugify(value))
            tags.add(tag)
        return tags

    @staticmethod
    def _slugify(value: str) -> str:
        out = value.lower().strip()
        for old, new in ((" ", "_"), ("-", "_"), ("/", "_"), ("'", "")):
            out = out.replace(old, new)
        return out
