import re
from dataclasses import dataclass
from typing import Pattern

from src.classification.domain.types import EntityType

CLASSIFICATION_STRATEGY_VERSION = "1.1.0"
LOW_MARGIN_THRESHOLD = 0.15


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    target: EntityType
    weight: float
    source: str
    pattern: Pattern[str]


# Keep all primary rules centralized for deterministic classification.
PRIMARY_RULES: tuple[RuleSpec, ...] = (
    RuleSpec("update_category_versions", "update", 1.0, "category", re.compile(r"^category:versions$", re.I)),
    RuleSpec(
        "update_title_or_content",
        "update",
        0.85,
        "combined",
        re.compile(r"(version\s*\d+\.\d+|update|patch\s*notes?)", re.I),
    ),
    RuleSpec("cat_units", "cat", 1.0, "category", re.compile(r"^category:cat units$", re.I)),
    RuleSpec("cat_general", "cat", 0.8, "category", re.compile(r"^category:.*cats$", re.I)),
    RuleSpec("enemy_units", "enemy", 1.0, "category", re.compile(r"^category:enemy units$", re.I)),
    RuleSpec("enemy_general", "enemy", 0.8, "category", re.compile(r"^category:.*enemies$", re.I)),
    RuleSpec("stage_general", "stage", 0.95, "category", re.compile(r"^category:.*stages$", re.I)),
    RuleSpec(
        "list_title",
        "list",
        0.85,
        "title",
        re.compile(r"^(list of|.*(comparison|release order|drop table).*)$", re.I),
    ),
    RuleSpec(
        "list_content",
        "list",
        0.75,
        "content",
        re.compile(r"(==\s*list of|release order|drop table)", re.I),
    ),
    RuleSpec(
        "mechanic_title_or_category",
        "mechanic",
        0.7,
        "combined",
        re.compile(r"(mechanic|ability|trait|talent|damage|range)", re.I),
    ),
)


CAT_SUBTYPE_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    (re.compile(r"category:normal cats", re.I), "rarity:normal"),
    (re.compile(r"category:special cats", re.I), "rarity:special"),
    (re.compile(r"category:rare cats", re.I), "rarity:rare"),
    (re.compile(r"category:super rare cats", re.I), "rarity:super_rare"),
    (re.compile(r"category:uber rare cats", re.I), "rarity:uber_rare"),
    (re.compile(r"category:legend rare cats", re.I), "rarity:legend_rare"),
    (re.compile(r"category:anti-(.+) cats", re.I), "target_trait:{group1}"),
    (re.compile(r"category:(.+)-class cats", re.I), "role_class:{group1}"),
    (re.compile(r"category:single attack cats", re.I), "attack_type:single"),
    (re.compile(r"category:area attack cats", re.I), "attack_type:area"),
    (re.compile(r"category:long distance cats", re.I), "attack_type:long_distance"),
    (re.compile(r"category:omni strike cats", re.I), "attack_type:omni"),
    (re.compile(r"category:surge attack cats", re.I), "attack_type:surge"),
    (re.compile(r"category:wave attack cats", re.I), "attack_type:wave"),
    (re.compile(r"category:.*killer cats", re.I), "ability:killer"),
    (re.compile(r"category:.*slayer cats", re.I), "ability:slayer"),
    (re.compile(r"category:event capsule cats", re.I), "source:event_capsule"),
    (re.compile(r"category:gacha cats", re.I), "source:gacha"),
    (re.compile(r"category:collaboration event cats", re.I), "source:collaboration"),
)


ENEMY_SUBTYPE_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    (re.compile(r"category:(.+) enemies", re.I), "trait:{group1}"),
    (re.compile(r"category:enemies with (.+) ability", re.I), "ability:{group1}"),
    (re.compile(r"category:enemies with (.+)", re.I), "ability:{group1}"),
    (re.compile(r"category:event enemies", re.I), "campaign_scope:event"),
    (re.compile(r"category:empire of cats enemies", re.I), "campaign_scope:eoc"),
    (re.compile(r"category:into the future enemies", re.I), "campaign_scope:itf"),
    (re.compile(r"category:stories of legend enemies", re.I), "campaign_scope:sol"),
    (re.compile(r"category:uncanny legends enemies", re.I), "campaign_scope:ul"),
    (re.compile(r"category:zero legends enemies", re.I), "campaign_scope:zl"),
)


STAGE_SUBTYPE_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    (re.compile(r"category:(.+) stages", re.I), "stage_family:{group1}"),
    (re.compile(r"category:empire of cats stages", re.I), "progression:eoc"),
    (re.compile(r"category:into the future stages", re.I), "progression:itf"),
    (re.compile(r"category:stories of legend stages", re.I), "progression:sol"),
    (re.compile(r"category:uncanny legends stages", re.I), "progression:ul"),
    (re.compile(r"category:zero legends stages", re.I), "progression:zl"),
    (re.compile(r"category:sub-chapter (\d+) stages", re.I), "progression:subchapter_{group1}"),
    (re.compile(r"category:timed score stages", re.I), "modifier:timed_score"),
    (re.compile(r"category:no continue stages", re.I), "modifier:no_continue"),
    (re.compile(r"category:continuation stages", re.I), "modifier:continuation"),
)


UPDATE_SUBTYPE_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    (re.compile(r"version\s*(\d+\.\d+)", re.I), "version_line:{group1}"),
    (re.compile(r"patch\s*notes?", re.I), "content_kind:patch_notes"),
    (re.compile(r"balance", re.I), "content_kind:balance"),
)


MECHANIC_SUBTYPE_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    (re.compile(r"trait", re.I), "mechanic_domain:trait"),
    (re.compile(r"ability", re.I), "mechanic_domain:ability"),
    (re.compile(r"talent", re.I), "mechanic_domain:talent"),
    (re.compile(r"damage|range", re.I), "mechanic_domain:combat"),
)


LIST_SUBTYPE_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    (re.compile(r"list of enemies", re.I), "list_kind:enemy_list"),
    (re.compile(r"list of stages", re.I), "list_kind:stage_list"),
    (re.compile(r"drop table", re.I), "list_kind:drop_table"),
    (re.compile(r"release order", re.I), "list_kind:release_order"),
    (re.compile(r"comparison", re.I), "list_kind:comparison"),
)

