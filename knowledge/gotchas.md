# Gotchas & Surprises

> This file tracks unexpected behaviors, edge cases, and non-obvious insights. Things that made you go "Wait, what?"

## How to Add Gotchas

When you discover something surprising:
1. Document the surprise immediately
2. Explain why it's non-obvious
3. Include how to handle it
4. Auto-promote to patterns.md if it appears 3+ times

---

## Gotcha Template

```markdown
## Gotcha: [Brief Description]
**Discovered:** YYYY-MM-DD
**Occurrences:** X times
**Context:** [When does this happen?]
**Surprise:** [What's unexpected about it?]
**Why it happens:** [Underlying reason]
**How to handle:** [Solution/workaround]
**Watch out:** [Related scenarios where this might occur]
**Related:** [Links to patterns.md, failures.md]
```

---

<!-- Gotchas will be added below this line -->

## Gotcha: Auto-extractor promotes knowledge on idle
**Discovered:** 2026-02-02
**Occurrences:** 1 time
**Context:** Auto-extracted from active/context.md
**Surprise:** Idle extraction now auto-promotes discoveries/decisions into knowledge/*.md
Source: Internal test run (session-orchestrator idle)
Relevance: Confirms knowledge base can grow without manual copy/paste
**Why it happens:** (fill in)
**How to handle:** (fill in)
**Watch out:** (fill in)
**Related:**
