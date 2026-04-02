# Design: cron-test-loop Observe-and-Escalate

**Date:** 2026-04-02
**Status:** Draft
**Target file:** `dev-loop/cron-test-loop.md`

## Problem

Current `cron-test-loop.md` Phase 3 requires the executing session to directly modify skill files, create branches, commit, and merge PRs for P0 issues. This leads to:

- Chaotic file changes across rounds, hard to track what changed and why
- Modifications made under time pressure in automated loops are error-prone
- No human review before changes land in the skill

## Goal

Change the test loop from "find-and-fix" to "observe-and-escalate":

1. Each round only **observes** and **records** findings to backlog files
2. After recording, **summarize** all backlog entries and detect escalation patterns
3. When high-priority patterns are detected, **notify** the user via openclaw with problem + recommendation + backlog reference
4. User decides whether and how to fix

## Design

### Phase 3 (revised): Record findings only

Replace the current Phase 3 with observation-only behavior:

- Write all findings (phenomena, problems, impacts) to `dev-loop/backlog/{YYYYMMDD-HHmm}-{summary}.md`
- Backlog file format unchanged from current convention:
  ```markdown
  # {Level}: {Title}

  ## Problem level
  {P0/P1/P2} (assessment only, no action difference)

  ## Observed behavior
  {What happened}

  ## Evidence
  {Specific data: round numbers, issue numbers, log excerpts}

  ## Impact
  {What this blocks or degrades}
  ```
- **No file modifications** to skill files, scripts, or any code
- **No branch creation, commits, or PRs**
- P0/P1/P2 levels are recorded as assessments but all receive the same treatment (backlog entry only)

### Phase 3.5 (new): Backlog summary + escalation

After writing the current round's backlog entry, scan all existing backlog files in `dev-loop/backlog/` and check for escalation triggers.

#### Escalation triggers

**Count-based** (catches unknown failure modes):

| Pattern | Threshold | Priority |
|---------|-----------|----------|
| Same issue appears in backlog across N+ consecutive rounds | 3 rounds | P0 escalation |
| Same issue in same state (label unchanged) with no new comments/PR/commit | 3 rounds | P0 escalation |

**Pattern-based shortcuts** (catches known failure modes faster):

| Pattern | Threshold | Priority |
|---------|-----------|----------|
| `dispatch=failed` in consecutive rounds | 2 rounds | P0 escalation |
| Worker unreachable after dispatch | 2 rounds | P0 escalation |
| Dispatch succeeds but no worker output | 3 rounds | P0 escalation |

#### Escalation notification

When any trigger fires, send notification via:

```bash
openclaw message send --channel feishu --target "ou_c5bd4c88f78cbf338f76dbb5e8f64fed" -m "notification content"
```

Notification format:

```
【测试循环告警 {datetime}】

问题：{problem description}
持续：连续 {N} 轮
影响：{impact analysis}
建议：{recommended action}
详情：{backlog file path}
```

#### No-escalation behavior

- If no escalation trigger fires, **do not send a notification** — avoid noise
- The regular Phase 3 output (progress report + feishu notification from the dev-loop skill itself) still happens as normal; this escalation is an additional alert only when patterns are detected

### Phase 4 (unchanged)

Update `docs/superpowers/plans/2026-04-01-coding-team-loop-test-optimization.md` with round results.

## Changes to cron-test-loop.md

### Remove

- Phase 3 "P0 问题额外执行" section (direct file modification, branch creation, PR, merge)
- P0/P1/P2 differentiated treatment logic

### Add

- Phase 3.5 "Backlog summary + escalation" section with triggers table and notification format

### Modify

- Phase 3 description: change from "问题处理" to "记录发现" — all findings written to backlog only
- Simplify Phase 3 to a single action: write backlog file

## Edge cases

1. **First round (no prior backlog)**: No escalation possible, just record findings
2. **Multiple triggers fire in same round**: Send one consolidated notification covering all triggered issues
3. **Issue already escalated in prior round**: Do not re-notify for the same issue unless the situation has worsened (e.g., round count increased)
4. **Backlog file naming collision** (same minute): Append `-2`, `-3` suffix

## Out of scope

- Automated fixing of any kind
- Backlog cleanup or archival (manual for now)
- Dashboard or web UI for backlog viewing
