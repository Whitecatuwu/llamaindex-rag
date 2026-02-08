Feature: Classification pipeline documentation acceptance
  As a team maintaining Battle Cats Wiki RAG
  I want plan and diagram documentation plus BDD acceptance spec to be stored in repository
  So that implementation and validation are consistent and auditable

  Scenario: A1 Plan document exists with required sections
    Given the repository root path
    When I check file "docs/plan/2026-02-07_classification-ddd-pipeline-plan.md"
    Then the file should exist
    And the file should include sections "Summary" and "Architecture"
    And the file should include sections "UseCase Contract" and "Pipeline Steps"
    And the file should include sections "Rule Strategy" and "Acceptance Criteria"

  Scenario: A2 Diagram document exists with workflow and data flow
    Given the repository root path
    When I check file "docs/plan/2026-02-07_classification-diagrams.md"
    Then the file should exist
    And the file should include at least 2 fenced mermaid blocks

  Scenario: B1 Workflow diagram covers entrypoints and pipeline stages
    Given the diagram markdown file
    When I inspect the workflow diagram block
    Then it should mention ingestion adapter entrypoint
    And it should include discover, load, classify, persist, and report stages

  Scenario: B2 Data flow diagram covers core objects and artifacts
    Given the diagram markdown file
    When I inspect the data flow diagram block
    Then it should include objects PageRef, WikiPage, and Classification
    And it should include outputs page labels, review queue, and report artifacts

  Scenario: C1 Acceptance standards are documented consistently
    Given plan and feature files
    When I compare acceptance statements
    Then both should require html and db source support
    And both should require misc fallback with reason for low confidence or conflict
    And both should require deterministic outputs for same input and strategy version

  Scenario: D1 Trigger and artifact expectations are explicit
    Given the plan and diagrams documentation
    When I review trigger methods
    Then ingestion adapter should be documented as valid trigger
    And output artifacts should include labels, review queue, and report
    And output artifacts should include classified json copies grouped by entity type
