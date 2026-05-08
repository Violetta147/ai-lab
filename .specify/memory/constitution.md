<!--
Sync Impact Report
- Version change: 1.1.0 -> 1.1.1
- Modified sections:
  - Delivery Workflow and Quality Gates: Updated to require speckit extension commands (/speckit-plan, /speckit-tasks) and the specs/ folder instead of an ad-hoc tmp/ directory.
- Modified principles:
  - I. Minimal, Goal-Driven Changes -> II. Minimal, Goal-Driven Changes
  - II. Type Safety and Functional Core -> III. Type Safety and Functional Core
  - III. Transparent Failure Handling -> IV. Transparent Failure Handling
  - IV. Verification Before Completion -> V. Verification Before Completion
  - V. Observability and Debug Traceability -> VI. Observability and Debug Traceability
- Added principles:
  - I. Commit Conventions
- Added sections:
  - Technology and Architecture Constraints
  - Delivery Workflow and Quality Gates
- Removed sections:
  - None
- Templates requiring updates:
  - ✅ reviewed (no change required): .specify/templates/plan-template.md
  - ✅ reviewed (no change required): .specify/templates/spec-template.md
  - ✅ reviewed (no change required): .specify/templates/tasks-template.md
  - ✅ reviewed (no files present): .specify/templates/commands/*.md
- Follow-up TODOs:
  - None
-->
# Final.yolov8 Constitution

## Core Principles

### I. Commit Conventions
All code contributions MUST adhere strictly to Conventional Commits standards.
- Use prefix categories such as `feat:`, `fix:`, `docs:`, `style:`, `refactor:`,
  `perf:`, `test:`, or `chore:`.
- The subject line MUST be concise (under 50 characters) and written in the
  imperative mood.
- Include related issue numbers or Jira tickets in the footer of the commit
  message when applicable.
Rationale: ensures a clean, predictable, and parseable history that aids in
automated changelog generation and easier debugging.

### II. Minimal, Goal-Driven Changes
Every code change MUST directly map to a stated requirement or verified defect.
Contributors MUST prefer the smallest viable change set, avoid speculative features,
and avoid unrelated refactors. If multiple approaches are possible, the chosen
approach MUST be justified in terms of lower complexity and clearer verification.
Rationale: constrained, traceable changes reduce regressions and review overhead.

### III. Type Safety and Functional Core
Business logic MUST be implemented as pure, explicit functions with strict typing.
Inputs MUST NOT be mutated. Classes SHOULD be limited to connectors and integration
boundaries with external systems. Generic escape hatches (for example `Any`) MUST be
avoided unless technically unavoidable and explicitly documented in-place.
Rationale: pure typed logic is easier to reason about, test, and maintain.

### IV. Transparent Failure Handling
Failures MUST raise explicit, specific errors with actionable context. Silent
failure paths, swallowed exceptions, and fallback behavior that hides root causes
are prohibited unless the fallback is an explicit product requirement. Debug signals
MUST identify what failed, where, and with which critical inputs.
Rationale: debugging speed and system correctness depend on visible root causes.

### V. Verification Before Completion
No task is complete until behavior is verified with appropriate checks. Changes that
affect logic MUST include or update tests when feasible within scope, and modified
areas MUST pass relevant lint or validation checks before handoff. Claims such as
"fixed", "done", or "passing" MUST be backed by executed evidence.
Rationale: evidence-based completion prevents false-positive readiness.

### VI. Observability and Debug Traceability
Execution-critical flows MUST emit meaningful diagnostics at the existing project
logging level so failures can be traced without invasive rework. Logging MUST be
concise, contextual, and non-noisy. Temporary diagnostics added for implementation
or debugging MUST be removed or reduced before completion unless explicitly retained.
Rationale: reliable operations require fast diagnosis with low telemetry noise.

## Technology and Architecture Constraints

- Python-first backend and analytics code MUST follow existing repository patterns and
  remain consistent with current deployment/runtime assumptions.
- New dependencies MUST be added through project configuration and MUST be justified
  by direct feature need; ad-hoc global installation is prohibited.
- Documentation files (`.md`) MUST NOT be added or modified unless explicitly
  requested by the user or required by a sanctioned planning workflow.

## Delivery Workflow and Quality Gates

- Work MUST start with requirement clarification and a short success criterion.
- For multi-step features, contributors MUST utilize the `speckit` extension commands (e.g., `/speckit-plan`, `/speckit-tasks`) and store artifacts in the designated `specs/` folder rather than an ad-hoc `tmp/` directory. This ensures strict adherence to project templates and workflow tracking.
- For `c2_center` Python backend changes, contributors MUST use `pytest`-based
  tests in `c2_center/backend/tests` and verify both failing-to-passing behavior
  for bug fixes or net-new behavior coverage for features.
- When the Superpowers bridge extension is available, contributors SHOULD run
  `speckit.superpowers.brainstorm` before major changes and MUST run
  `speckit.superpowers.review` before final handoff for spec-aligned review.
- Implementations MUST prefer incremental delivery with intermediate validation.
- Before final handoff, contributors MUST validate edited files for lint/type issues
  and resolve newly introduced diagnostics when reasonably possible.
- Git history operations MUST remain non-destructive unless explicitly requested.

## Governance

This constitution is the highest-priority engineering policy for this repository.
All plans, specs, tasks, implementation changes, and reviews MUST comply with these
principles.

Amendment process:
- Any amendment MUST include a clear rationale and explicit impact on templates and
  workflow artifacts under `.specify/`.
- The constitution update MUST include a Sync Impact Report at the top of the file.
- Ratification and amendment dates MUST use ISO format (`YYYY-MM-DD`).

Versioning policy:
- MAJOR: incompatible governance changes or principle removals/redefinitions.
- MINOR: new principle or materially expanded mandatory guidance.
- PATCH: clarifications, wording improvements, and non-semantic refinements.

Compliance review expectations:
- Planning and implementation reviews MUST include a constitution compliance check.
- Exceptions MUST be documented with explicit justification and a bounded scope.

**Version**: 1.1.1 | **Ratified**: 2026-05-08 | **Last Amended**: 2026-05-08
