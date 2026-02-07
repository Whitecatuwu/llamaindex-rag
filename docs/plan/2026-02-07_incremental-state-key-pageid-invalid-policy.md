# Incremental State Key Policy (pageid) + Invalid Page Handling

## Background
Incremental classification previously keyed state by `doc_id`. When `pageid` is missing and titles collide (or are empty), different pages can overwrite each other's state and be incorrectly skipped.

## Final Decision
1. State key MUST use `pageid` only:
   - `state_key = str(pageid)`
2. If `pageid` is missing:
   - Do not perform incremental state lookup/upsert.
   - Do not run normal rule-based classification.
   - Emit `entity_type=invalid`.
   - Write both label and review records.
   - Log warning with source path and parse warning context.

## Contract Impact
- Public label contract keeps `doc_id` unchanged for compatibility.
- `by_entity_type` now includes `invalid`.

## Determinism
- Invalid classification is deterministic for same input.
- Strategy version is bumped to reflect behavior change.

## Test Matrix
- Missing pageid => invalid + review.
- Missing pageid rerun => still classified (no incremental skip).
- Existing pageid rerun => incremental skip works.
- Corrupted state DB recovery still works.

## Acceptance Criteria
- No false incremental skip caused by non-unique doc_id.
- Missing pageid pages are always visible in artifacts and review queue.
- All unit tests pass.

## Risks and Rollback
- Risk: downstream consumers may treat the new `invalid` entity type as unexpected.
- Mitigation: keep `doc_id` contract unchanged and surface `invalid` in report counts for observability.
- Rollback: revert to prior pipeline behavior and state key lookup by `doc_id`; no DB schema migration is required.
